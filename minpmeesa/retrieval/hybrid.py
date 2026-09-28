"""Recherche hybride : BM25 (requête étendue par le lexique) + dense, fusion
par rangs réciproques (RRF), section 3.2.5.

Les deux index ne contiennent que les passages des documents « publie » : le
filtre de statut est appliqué dans la requête SQL qui les alimente, donc
AVANT tout classement. Les filtres de métadonnées optionnels (type, exercice
maximal) sont eux aussi appliqués avant la fusion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .. import config
from ..store.bm25_index import IndexBM25
from .text import etendre, tokens


@dataclass
class Resultat:
    passage_id: int
    score: float                  # score RRF (ou score brut en voie seule)
    rang_lexical: Optional[int]
    rang_dense: Optional[int]


def rrf(listes: List[List[int]], k: int) -> List[Tuple[int, float]]:
    """Fusion par rangs réciproques : score(d) = Σ 1 / (k + rang)."""
    s: Dict[int, float] = {}
    for l in listes:
        for r, pid in enumerate(l, start=1):
            s[pid] = s.get(pid, 0.0) + 1.0 / (k + r)
    return sorted(s.items(), key=lambda kv: -kv[1])


class Recherche:
    def __init__(self, base, bm25: IndexBM25, dense=None):
        self.base, self.bm25, self.dense = base, bm25, dense
        self.cfg = config.get("recherche")
        self._meta = {r["passage_id"]: r for r in base.passages_publies()}

    def _filtrer(self, ids: List[int], filtres: Optional[dict]) -> List[int]:
        if not filtres:
            return [i for i in ids if i in self._meta]
        out = []
        for i in ids:
            m = self._meta.get(i)
            if m is None:
                continue
            if "types" in filtres and m["type"] not in filtres["types"]:
                continue
            if "exercice_max" in filtres and m["exercice"] > filtres["exercice_max"]:
                continue
            if "exercice_min" in filtres and m["exercice"] < filtres["exercice_min"]:
                continue
            out.append(i)
        return out

    def lexical(self, question: str, k: int, expansion: Optional[bool] = None) -> List[Tuple[int, float]]:
        """BM25 ; l'expansion par le lexique ne touche que cette requête lexicale."""
        exp = self.cfg["expansion_lexique"] if expansion is None else expansion
        q = tokens(question)
        if not exp:
            return self.bm25.chercher(q, k)
        etendue = etendre(question, str(config.chemin("lexique")), self.cfg["expansions_max_par_terme"])
        ajouts = [t for t in etendue if t not in q]
        return self.bm25.chercher(q, k, ajouts, float(self.cfg.get("poids_expansion", 1.0)))

    def score_bm25_brut(self, question: str) -> float:
        """Signal d'abstention : meilleur score BM25 de la requête NON étendue."""
        r = self.bm25.chercher(tokens(question), 1)
        return r[0][1] if r else 0.0

    def chercher(self, question: str, mode: str = "hybride", n: Optional[int] = None,
                 rrf_k: Optional[int] = None, filtres: Optional[dict] = None) -> List[Resultat]:
        """mode ∈ {lexicale, dense, hybride}."""
        n = n or self.cfg["top_n"]
        k = rrf_k or self.cfg["rrf_k"]
        lex = self._filtrer([i for i, _ in self.lexical(question, self.cfg["k_lexical"])], filtres) \
            if mode in ("lexicale", "hybride") else []
        den: List[int] = []
        if mode in ("dense", "hybride"):
            if self.dense is None:
                if mode == "dense":
                    raise RuntimeError("index dense indisponible")
            else:
                den = self._filtrer([i for i, _ in self.dense.chercher(question, self.cfg["k_dense"])], filtres)
        rl = {pid: r for r, pid in enumerate(lex, start=1)}
        rd = {pid: r for r, pid in enumerate(den, start=1)}
        if mode == "lexicale":
            fus = [(pid, 1.0 / r) for pid, r in rl.items()]
        elif mode == "dense":
            fus = [(pid, 1.0 / r) for pid, r in rd.items()]
        else:
            fus = rrf([lex, den], k)
        fus.sort(key=lambda x: -x[1])
        return [Resultat(pid, s, rl.get(pid), rd.get(pid)) for pid, s in fus[:n]]


def charger_recherche(base, nom_dense: Optional[str] = None) -> Recherche:
    from ..store.bm25_index import charger_bm25
    try:
        from ..store.faiss_index import charger_faiss
        dense = charger_faiss(nom_dense)
    except Exception:
        dense = None
    return Recherche(base, charger_bm25(), dense)
