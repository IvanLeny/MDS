"""Recherche hybride : BM25 (avec lexique métier) + dense, fusion par rangs réciproques.

Trois configurations comparées (2.4.1) : « lexicale », « dense », « hybride ».
Les filtres (statut de diffusion, exercice, type) sont appliqués AVANT le
classement : chaque voie ne calcule de score que sur les passages autorisés.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .. import config
from ..store import bm25_index, db, encodeur as encmod, faiss_index
from ..texte import normaliser, tokens


@dataclass
class Resultat:
    passage_id: int
    score: float                    # score de la configuration (RRF, BM25 ou cosinus)
    rang_bm25: int | None = None
    score_bm25: float | None = None
    rang_dense: int | None = None
    score_dense: float | None = None


@dataclass
class Lexique:
    familles: list[list[str]] = field(default_factory=list)

    @classmethod
    def charger(cls, chemin: Path) -> "Lexique":
        with open(chemin, encoding="utf-8") as f:
            brut = yaml.safe_load(f) or {}
        fam = [[normaliser(str(t)).replace("_", " ") for t in f] for f in brut.get("familles", [])]
        return cls(fam)

    def etendre(self, question: str, max_par_terme: int = 4) -> list[str]:
        """Tokens ajoutés à la SEULE requête lexicale (jamais aux passages ni au dense)."""
        q = f" {' '.join(normaliser(question).split())} "
        qtok = set(tokens(question))
        ajout: list[str] = []
        for fam in self.familles:
            present = any((f" {t} " in q) if " " in t else (t in qtok or tokens(t) and tokens(t)[0] in qtok)
                          for t in fam)
            if not present:
                continue
            n = 0
            for t in fam:
                for tk in tokens(t):
                    if tk not in qtok and tk not in ajout and n < max_par_terme:
                        ajout.append(tk)
                        n += 1
        return ajout


class Moteur:
    """Moteur de recherche chargé depuis la base (un dossier sur disque)."""

    def __init__(self, dossier: Path | None = None):
        self.cfg = config.charger()
        self.dossier = dossier or config.chemin("base")
        self.con = db.connecter(self.dossier)
        self.bm25 = bm25_index.IndexBM25.charger(self.dossier)
        self.dense = faiss_index.charger(self.dossier)
        rapport = json.loads((self.dossier / "build_rapport.json").read_text(encoding="utf-8"))
        self.nom_encodeur = rapport["encodeur"]
        self.encodeur = encmod.charger(self.dossier, self.nom_encodeur)
        self.lexique = Lexique.charger(config.chemin("lexique"))

    def autorises(self, statut: str = "publie", exercice_max: int | None = None,
                  types: tuple[str, ...] | None = None, exclure_tests: bool = False) -> list[int]:
        return db.ids_passages_autorises(self.con, statut, exercice_max, types, exclure_tests)

    def requete_lexicale(self, question: str, expansion: bool | None = None) -> list[str]:
        c = self.cfg["consultation"]
        expansion = c["expansion_lexique"] if expansion is None else expansion
        tk = tokens(question)
        if expansion:
            tk += self.lexique.etendre(question, c["max_synonymes_par_terme"])
        return tk

    def rechercher(self, question: str, autorises: list[int], mode: str = "hybride",
                   k: int | None = None, rrf_k: int | None = None,
                   expansion: bool | None = None) -> list[Resultat]:
        c = self.cfg["consultation"]
        k = k or c["top_n"]
        rrf_k = rrf_k or c["rrf_k"]
        lex = self.recherche_lexicale(question, autorises, c["k_bm25"], expansion) \
            if mode in ("hybride", "lexicale") else []
        den = faiss_index.rechercher(self.dense, self.encodeur.encoder_requete(question), autorises, c["k_dense"]) \
            if mode in ("hybride", "dense") else []
        if mode == "lexicale":
            return [Resultat(p, s, i + 1, s) for i, (p, s) in enumerate(lex[:k])]
        if mode == "dense":
            return [Resultat(p, s, rang_dense=i + 1, score_dense=s) for i, (p, s) in enumerate(den[:k])]
        return fusion_rrf(lex, den, rrf_k)[:k]

    def recherche_lexicale(self, question: str, autorises: list[int], k: int,
                           expansion: bool | None = None) -> list[tuple[int, float]]:
        """BM25 de la question + poids_expansion x BM25 des seuls termes ajoutés
        par le lexique (les synonymes complètent la requête sans la noyer)."""
        c = self.cfg["consultation"]
        expansion = c["expansion_lexique"] if expansion is None else expansion
        base = dict(self.bm25.rechercher(tokens(question), autorises, len(autorises)))
        if expansion:
            ajout = self.lexique.etendre(question, c["max_synonymes_par_terme"])
            if ajout:
                w = c["poids_expansion"]
                for p, s in self.bm25.rechercher(ajout, autorises, len(autorises)):
                    base[p] = base.get(p, 0.0) + w * s
        return sorted(base.items(), key=lambda x: (-x[1], x[0]))[:k]

    def signal_confiance(self, question: str, autorises: list[int], signal: str | None = None) -> float:
        """Signal d'abstention : meilleur score BM25 de la question (sans expansion)
        ou meilleur cosinus de la voie dense, selon config.yaml."""
        signal = signal or self.cfg["consultation"]["signal_abstention"]
        if signal == "dense_max":
            r = faiss_index.rechercher(self.dense, self.encodeur.encoder_requete(question), autorises, 1)
        else:
            r = self.bm25.rechercher(tokens(question), autorises, 1)
        return r[0][1] if r else 0.0


def fusion_rrf(lex: list[tuple[int, float]], den: list[tuple[int, float]], k: int) -> list[Resultat]:
    """Fusion par rangs réciproques : score = somme des 1 / (k + rang)."""
    res: dict[int, Resultat] = {}
    for i, (p, s) in enumerate(lex):
        r = res.setdefault(p, Resultat(p, 0.0))
        r.score += 1.0 / (k + i + 1)
        r.rang_bm25, r.score_bm25 = i + 1, s
    for i, (p, s) in enumerate(den):
        r = res.setdefault(p, Resultat(p, 0.0))
        r.score += 1.0 / (k + i + 1)
        r.rang_dense, r.score_dense = i + 1, s
    return sorted(res.values(), key=lambda r: (-r.score, r.passage_id))


@lru_cache(maxsize=2)
def moteur(dossier: str | None = None) -> Moteur:
    return Moteur(Path(dossier) if dossier else None)
