"""Contrôle de citation littérale (Tableau 3.5, règles R0 à R3).

R0  harmoniser les écritures (voir normalize.py) ;
R1  chaque valeur de CHAQUE énoncé (constat comme perspective) est recherchée
    dans les valeurs autorisées (tableau de l'exercice) ou les variations
    calculées par le programme ;
R2  une valeur retrouvée est conservée et rattachée à sa source ;
R3  une valeur non retrouvée est écartée : l'énoncé est reformulé sans elle
    (la proposition qui la porte est retirée) ou supprimé ; l'écart est journalisé.
Ne sont pas des valeurs statistiques (liste d'exclusion explicite) : les
millésimes, les numéros de tableau, de graphique, de page, de chapitre, les
trimestres (T1…T4) et les ordinaux.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from .. import config
from .normalize import NOMBRE, canon, decimales, formes

_REFERENCE = re.compile(
    r"(tableau|tableaux|graphique|graphiques|figure|page|pages|p\.|chapitre|section|annexe|"
    r"encadré|n°|no|numéro|article|programme|csp|snd|loi)\s*$", re.I)
_ORDINAL_APRES = re.compile(r"^\s?(er|re|ère|e|è|ème|eme|ième|ieme|nd|nde)\b", re.I)


@dataclass
class Occurrence:
    texte: str                 # écriture telle qu'elle apparaît
    debut: int
    fin: int
    pourcent: bool


def _annees() -> tuple[int, int]:
    a, b = config.charger()["commentaire"]["annees_exclues"]
    return int(a), int(b)


def occurrences(texte: str) -> list[Occurrence]:
    """Valeurs statistiques d'un texte, liste d'exclusion appliquée."""
    amin, amax = _annees()
    out = []
    for m in NOMBRE.finditer(texte):
        n = m.group("n")
        avant = texte[max(0, m.start() - 20):m.start()]
        apres = texte[m.end():m.end() + 6]
        brut = n.replace(" ", "").replace(" ", "").replace(" ", "")
        pct = bool(m.group("pct"))
        # millésime isolé (hors pourcentage) ou borne d'une période « 2022-2024 »
        if brut.isdigit() and len(brut) == 4 and amin <= int(brut) <= amax and not pct:
            continue
        # trimestre T1..T4, S1, sigles collés (SND30, T3_2024)
        if re.search(r"[A-Za-z_]$", texte[max(0, m.start() - 1):m.start()]):
            continue
        if _REFERENCE.search(avant):
            continue
        if _ORDINAL_APRES.match(apres) and not pct and len(brut) <= 3:
            continue
        out.append(Occurrence(n, m.start(), m.end(), pct))
    return out


def nombres(texte: str) -> list[str]:
    return [o.texte for o in occurrences(texte)]


@dataclass
class Controle:
    enonces: list[dict] = field(default_factory=list)       # énoncés conservés (avec sources)
    ecartees: list[dict] = field(default_factory=list)      # valeurs écartées (R3), journalisées
    supprimes: list[dict] = field(default_factory=list)     # énoncés supprimés entièrement
    n_valeurs: int = 0                                      # valeurs citées avant contrôle
    n_retenues: int = 0

    def to_dict(self) -> dict:
        return {"enonces": self.enonces, "valeurs_ecartees": self.ecartees,
                "enonces_supprimes": self.supprimes, "n_valeurs": self.n_valeurs,
                "n_retenues": self.n_retenues}


def index_autorise(autorisees: list[dict]) -> dict[Decimal, dict]:
    """{valeur canonique -> source} à partir de [{texte, source}]."""
    idx: dict[Decimal, dict] = {}
    for a in autorisees:
        for v in formes(a["texte"]):
            idx.setdefault(v, a.get("source", {}))
    return idx


def trouver(occ: str, idx: dict[Decimal, dict]) -> dict | None:
    for v in formes(occ):
        if v in idx:
            return idx[v]
    return None


# Séparateurs de propositions (jamais la virgule décimale « 9,9 »).
_COUPURES = re.compile(r"\s*(?:,(?!\d)|;|:|\bsoit\b|\bet\b|\(|\)|\s[–—-]\s)\s*", re.I)


def _retirer(texte: str, occs: list[Occurrence]) -> str:
    """Retire la ou les propositions qui portent des valeurs non soutenues."""
    # Découpage en propositions (positions conservées)
    bornes = [0] + [m.end() for m in _COUPURES.finditer(texte)] + [len(texte)]
    morceaux = [(bornes[i], bornes[i + 1]) for i in range(len(bornes) - 1)]
    garder = []
    for a, b in morceaux:
        if any(a <= o.debut < b for o in occs):
            continue
        garder.append(texte[a:b])
    s = "".join(garder).strip()
    s = re.sub(r"\s+", " ", s)
    for _ in range(3):
        s = re.sub(r"(\s*[,;:(]\s*)+$", "", s).strip()
        s = re.sub(r"\s+(soit|et)\s*$", "", s, flags=re.I).strip()
    s = re.sub(r"^(\s*[,;:)]\s*)+", "", s)
    s = re.sub(r"\(\s*\)", "", s)
    if s and not s.endswith((".", "!", "?")):
        s += "."
    return s[:1].upper() + s[1:] if s else s


def controler(enonces: list[dict], autorisees: list[dict], modeles: list[str] | None = None,
              longueur_min: int | None = None) -> Controle:
    """Applique R1 à R3 à des énoncés [{type, texte, valeurs}].

    `autorisees` : [{texte, source}] (valeurs de l'exercice + variations calculées
    + nombres des libellés du tableau). `modeles` n'est jamais une source autorisée ;
    il sert seulement à qualifier l'écart (chiffre d'un modèle de rédaction).
    """
    longueur_min = longueur_min or config.charger()["commentaire"]["longueur_min_enonce"]
    idx = index_autorise(autorisees)
    c = Controle()
    for i, e in enumerate(enonces):
        texte = e.get("texte", "")
        occs = occurrences(texte)
        c.n_valeurs += len(occs)
        sources, mauvaises = [], []
        for o in occs:
            s = trouver(o.texte, idx)
            if s is None:
                mauvaises.append(o)
            else:
                sources.append({"valeur": o.texte, **s})
        if not mauvaises:
            c.n_retenues += len(occs)
            c.enonces.append({**e, "texte": texte, "sources": sources})
            continue
        nouveau = _retirer(texte, mauvaises)
        occ_rest = occurrences(nouveau)
        ok_rest = [o for o in occ_rest if trouver(o.texte, idx) is not None]
        action = "reformulé"
        if len(nouveau.split()) < longueur_min or len(ok_rest) != len(occ_rest):
            action = "supprimé"
        for o in mauvaises:
            c.ecartees.append({"enonce": i, "type": e.get("type", ""), "valeur": o.texte,
                               "texte_original": texte, "action": action,
                               "dans_modele": any(o.texte in (m or "") for m in (modeles or []))})
        if action == "supprimé":
            c.supprimes.append({**e, "motif": "valeur non soutenue"})
        else:
            c.n_retenues += len(ok_rest)
            src = [{"valeur": o.texte, **trouver(o.texte, idx)} for o in ok_rest]
            c.enonces.append({**e, "texte": nouveau, "texte_avant_controle": texte, "sources": src})
    return c


def classer_ecart(valeur: str, autorisees: list[str], anterieures: list[str]) -> str:
    """Typologie d'une valeur écartée (analyse des erreurs, H2) :
    arrondi | chiffre d'un autre exercice | calcul | invention."""
    v = canon(valeur)
    if v is None:
        return "invention"
    dec = decimales(valeur)
    num = [canon(a) for a in autorisees]
    num = [x for x in num if x is not None]
    pas = Decimal(1).scaleb(-dec)
    for a in num:
        if a != v and abs(a - v) <= pas / 2 + Decimal("1e-12"):
            return "arrondi"
    ant = {canon(a) for a in anterieures} - {None}
    if v in ant:
        return "chiffre d'un autre exercice"
    tol = pas / 2 + Decimal("1e-9")
    num = sorted(set(num))[:250]
    for i, a in enumerate(num):
        for b in num[i + 1:]:
            cand = [abs(a - b), a + b]
            if b != 0:
                cand += [abs(a - b) / b * 100, a / b * 100]
            if a != 0:
                cand += [abs(b - a) / a * 100, b / a * 100]
            if any(abs(x - v) <= tol for x in cand):
                return "calcul"
    return "invention"
