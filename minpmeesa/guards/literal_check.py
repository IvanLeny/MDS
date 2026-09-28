"""Contrôle de citation littérale (Tableau 3.5, règles R0 à R3).

R0 : harmoniser les écritures (normalize.py).
R1 : chaque valeur de CHAQUE énoncé (constat comme perspective) est recherchée
     dans les valeurs autorisées ou les variations calculées par le programme.
R2 : une valeur retrouvée est conservée et rattachée à sa source.
R3 : une valeur non retrouvée est écartée ; l'énoncé est reformulé sans elle
     (retrait de la parenthèse, de la proposition ou de la phrase qui la porte)
     ou supprimé. L'écart est journalisé.

Seules les deux premières rubriques du contexte (valeurs de l'exercice traité et
variations calculées) alimentent la liste des valeurs autorisées : un chiffre
repris d'un modèle de rédaction antérieur n'y figure pas et il est écarté.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .normalize import NombreTrouve, cles, cles_valeur, extraire_nombres


@dataclass
class ValeurAutorisee:
    """Une valeur que le texte a le droit de citer, avec sa source."""
    texte: str                       # écriture de référence (« 7,8 »)
    source: dict                     # {genre, valeur_id(s), doc_id, page, tableau_n, ligne, colonne}

    @property
    def cles(self) -> set:
        return cles_valeur(self.texte)


@dataclass
class ValeurEcartee:
    valeur: str
    enonce_original: str
    enonce_type: str
    action: str                      # "reformule" | "supprime"


@dataclass
class EnonceControle:
    type: str
    texte: str
    texte_original: str
    valeurs: List[dict] = field(default_factory=list)      # [{valeur, source}]
    ecartees: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"type": self.type, "texte": self.texte, "texte_original": self.texte_original,
                "valeurs": self.valeurs, "ecartees": self.ecartees}


@dataclass
class ResultatControle:
    enonces: List[EnonceControle] = field(default_factory=list)
    ecartees: List[ValeurEcartee] = field(default_factory=list)
    n_valeurs_citees: int = 0        # valeurs présentes dans la sortie brute
    n_valeurs_soutenues: int = 0     # valeurs retrouvées (R2)

    @property
    def n_ecartees(self) -> int:
        return len(self.ecartees)

    def to_dict(self) -> dict:
        return {"enonces": [e.to_dict() for e in self.enonces],
                "ecartees": [e.__dict__ for e in self.ecartees],
                "n_valeurs_citees": self.n_valeurs_citees,
                "n_valeurs_soutenues": self.n_valeurs_soutenues}


def index_autorise(autorisees: List[ValeurAutorisee]) -> Dict[str, List[dict]]:
    idx: Dict[str, List[dict]] = {}
    for v in autorisees:
        for k in v.cles:
            idx.setdefault(k, []).append(v.source)
    return idx


def chercher(n: NombreTrouve, idx: Dict[str, List[dict]]) -> Optional[dict]:
    """R1 : première source dont une clé coïncide avec une lecture du nombre."""
    for k in sorted(cles(n)):
        if k in idx:
            return idx[k][0]
    return None


# ---------------------------------------------------------------------------
#  R3 : reformulation sans la valeur
# ---------------------------------------------------------------------------
_PHRASES = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«])")


def _retirer(phrase: str, deb: int, fin: int) -> Optional[str]:
    """Retire la plus petite unité grammaticale qui porte la valeur [deb, fin).
    Renvoie la phrase reformulée ou None s'il faut la supprimer."""
    # 1) Parenthèse contenant la valeur : « (soit 7,8 %) ».
    for m in re.finditer(r"\s*\([^()]*\)", phrase):
        if m.start() <= deb and fin <= m.end():
            return phrase[:m.start()] + phrase[m.end():]
    # 2) Proposition entre virgules / points-virgules, si le reste tient debout.
    # Séparateurs de proposition : « ; » ou une virgule SUIVIE d'une espace
    # (la virgule décimale de « 3,0 » n'en est pas une).
    bornes = [0] + [m.end() for m in re.finditer(r";\s*|,\s+", phrase)] + [len(phrase)]
    for a, b in zip(bornes, bornes[1:]):
        if a <= deb < b:
            reste = (phrase[:a].rstrip(", ;") + (", " if b < len(phrase) and a else " ") + phrase[b:].lstrip()).strip()
            # La proposition de tête porte le sujet : on ne la retire pas seule.
            if a > 0 and len(reste.split()) >= 6:
                reste = re.sub(r"\s+([.,;])", r"\1", reste)
                if not reste.endswith((".", "!", "?")):
                    reste += "."
                return reste
            break
    return None


def _nettoyer(t: str) -> str:
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([.,])", r"\1", t)
    t = re.sub(r"([.,;]){2,}", r"\1", t)
    return t.strip()


def controler_enonce(texte: str, idx: Dict[str, List[dict]],
                     bornes_annees: Tuple[int, int]) -> Tuple[str, List[dict], List[str], int]:
    """Applique R1-R3 à un énoncé. Renvoie (texte contrôlé, valeurs retenues,
    valeurs écartées, nombre de valeurs citées)."""
    phrases = _PHRASES.split(texte.strip()) if texte.strip() else []
    sortie, retenues, ecartees, n_citees = [], [], [], 0
    for ph in phrases:
        courante = ph
        # On traite les valeurs non soutenues une à une (les positions changent).
        for _ in range(20):
            nombres = extraire_nombres(courante, bornes_annees)
            fautive = next((n for n in nombres if chercher(n, idx) is None), None)
            if fautive is None:
                break
            ecartees.append(fautive.texte)
            nouvelle = _retirer(courante, fautive.debut, fautive.fin)
            if nouvelle is None:
                courante = ""
                break
            courante = nouvelle
        if courante:
            sortie.append(_nettoyer(courante))
    # Décompte sur le texte brut, valeurs retenues sur le texte final.
    n_citees = len(extraire_nombres(texte, bornes_annees))
    final = " ".join(sortie)
    for n in extraire_nombres(final, bornes_annees):
        src = chercher(n, idx)
        if src is not None:
            retenues.append({"valeur": n.texte, "source": src})
    return final, retenues, ecartees, n_citees


def controler(enonces: List[dict], autorisees: List[ValeurAutorisee],
              bornes_annees: Tuple[int, int] = (2010, 2035)) -> ResultatControle:
    """Contrôle une liste d'énoncés [{type, texte, valeurs}] (sortie JSON du
    modèle). Les valeurs déclarées dans « valeurs » et absentes du texte sont
    aussi vérifiées : un énoncé ne peut pas revendiquer une valeur non soutenue."""
    idx = index_autorise(autorisees)
    res = ResultatControle()
    for e in enonces:
        texte = str(e.get("texte", "")).strip()
        typ = str(e.get("type", "constat"))
        final, retenues, ecartees, n_citees = controler_enonce(texte, idx, bornes_annees)
        # Valeurs déclarées hors du texte : contrôlées elles aussi.
        dans_texte = {k for n in extraire_nombres(texte, bornes_annees) for k in cles(n)}
        for v in e.get("valeurs", []) or []:
            for n in extraire_nombres(str(v), bornes_annees):
                if not (cles(n) & dans_texte) and chercher(n, idx) is None:
                    ecartees.append(n.texte)
                    n_citees += 1
        res.n_valeurs_citees += n_citees
        res.n_valeurs_soutenues += n_citees - len(ecartees)
        action = "supprime" if not final else "reformule"
        for v in ecartees:
            res.ecartees.append(ValeurEcartee(valeur=v, enonce_original=texte,
                                              enonce_type=typ, action=action))
        if final:
            res.enonces.append(EnonceControle(type=typ, texte=final, texte_original=texte,
                                              valeurs=retenues, ecartees=ecartees))
    return res


def valeurs_non_soutenues(texte: str, autorisees: List[ValeurAutorisee],
                          bornes_annees: Tuple[int, int] = (2010, 2035)) -> List[str]:
    """Valeurs d'un texte absentes des valeurs autorisées (mesure H2, sans
    rien modifier au texte)."""
    idx = index_autorise(autorisees)
    return [n.texte for n in extraire_nombres(texte, bornes_annees) if chercher(n, idx) is None]
