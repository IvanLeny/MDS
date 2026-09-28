"""Harmonisation des écritures numériques (règle R0, Tableau 3.5).

7,8 ≡ 7.8 ; 12 500 ≡ 12500 ≡ 12 500 (espace insécable ou fine) ; % ≡ pour cent.
Une écriture ambiguë (« 12.500 » : milliers ou décimale ?) reçoit ses deux
lectures ; le contrôle retient la valeur si l'une d'elles est autorisée.

Ne sont PAS des valeurs statistiques (liste d'exclusion testée) :
  - les millésimes isolés (bornes dans config.yaml : commentaire.annees_exclues) ;
  - les numéros de tableau, graphique, page, chapitre, section, annexe, figure ;
  - les trimestres (T1…T4, « 1er trimestre ») et les ordinaux (1er, 2e, 3ème…) ;
  - les bornes d'âge ou de durée (« de 30 à 40 ans », « moins de 20 ans »).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import List, Optional, Set, Tuple

# Espaces servant de séparateur de milliers : normal, insécable, fine insécable, fine.
_ESPACES = "    "
_SEP = f"[{_ESPACES}]"

# Nombre : signe éventuel, groupes de milliers séparés par espace/point/virgule,
# partie décimale éventuelle. L'ordre des alternatives privilégie les groupes.
NOMBRE_RE = re.compile(
    rf"(?<![\w,.])([+\-−–]?)\s?(\d{{1,3}}(?:{_SEP}\d{{3}})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)(?![\w])"
)

_UNITE_PCT = re.compile(r"^\s*(%|pour\s*cent|pourcent|points?\s+de\s+pourcentage|pts?\b)", re.I)

# Contextes qui font d'un nombre une référence et non une valeur.
_REFERENCE_AVANT = re.compile(
    r"(tableau|tableaux|graphique|graphiques|page|pages|p\.|pp\.|chapitre|section|annexe|"
    r"figure|encadré|article|n°|no\.|numéro)\s*$", re.I)
_ORDINAL_APRES = re.compile(r"^(er|ère|re|e|ème|eme|nd|nde|è)\b", re.I)
_TRIMESTRE = re.compile(r"(?<![\w])T[1-4](?![\w])")
_TRIMESTRE_APRES = re.compile(r"^\s*(er|e|ème|eme)?\s*trimestre", re.I)
# Borne d'âge ou de durée (« de 30 à 40 ans », « moins de 20 ans ») : pas une valeur statistique.
_ANS_APRES = re.compile(r"^\s*((?:-|à|et)\s*\d+\s*)?ans\b", re.I)


@dataclass(frozen=True)
class NombreTrouve:
    texte: str            # écriture telle qu'elle figure dans le texte
    debut: int
    fin: int
    lectures: Tuple[Decimal, ...]   # une ou deux lectures possibles
    pourcentage: bool


def _vers_decimal(s: str) -> Optional[Decimal]:
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def lectures(corps: str) -> Tuple[Decimal, ...]:
    """Lectures numériques possibles d'une écriture (sans signe)."""
    t = re.sub(_SEP, "", corps)
    if "." in t and "," in t:
        # Le dernier séparateur est la marque décimale.
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
        d = _vers_decimal(t)
        return (d,) if d is not None else ()
    for sep in (",", "."):
        if sep in t:
            parts = t.split(sep)
            if len(parts) > 2:
                # Séparateur répété : forcément des milliers (« 1.234.567 »).
                d = _vers_decimal("".join(parts))
                return (d,) if d is not None else ()
            ent, dec = parts
            d_dec = _vers_decimal(f"{ent}.{dec}")
            if len(dec) == 3 and ent and ent != "0":
                # « 12.500 » ou « 12,500 » : milliers ou décimale -> deux lectures.
                d_mil = _vers_decimal(ent + dec)
                return tuple(x for x in (d_dec, d_mil) if x is not None)
            return (d_dec,) if d_dec is not None else ()
    d = _vers_decimal(t)
    return (d,) if d is not None else ()


def canon(d: Decimal) -> str:
    """Forme canonique d'une valeur : « 7,8 » ≡ « 7,80 » ≡ « 7.8 »."""
    d = d.normalize()
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def est_millesime(d: Decimal, bornes: Tuple[int, int]) -> bool:
    return d == d.to_integral_value() and bornes[0] <= int(d) <= bornes[1]


def extraire_nombres(texte: str, bornes_annees: Tuple[int, int] = (2010, 2035),
                     garder_references: bool = False) -> List[NombreTrouve]:
    """Nombres d'un texte, hors millésimes isolés, références et ordinaux."""
    out: List[NombreTrouve] = []
    trimestres = {m.start() + 1 for m in _TRIMESTRE.finditer(texte)}
    for m in NOMBRE_RE.finditer(texte):
        signe, corps = m.group(1), m.group(2)
        deb, fin = m.start(2), m.end(2)
        avant, apres = texte[max(0, deb - 25):deb], texte[fin:fin + 30]
        if not garder_references:
            if deb in trimestres:
                continue
            if _REFERENCE_AVANT.search(avant):
                continue
            if _ORDINAL_APRES.match(apres) or _TRIMESTRE_APRES.match(apres) or _ANS_APRES.match(apres):
                continue
        lec = lectures(corps)
        if not lec:
            continue
        # Un millésime isolé (sans séparateur de milliers) n'est pas une valeur.
        brut = re.sub(_SEP, "", corps)
        if brut.isdigit() and len(brut) == 4 and corps == brut and est_millesime(lec[0], bornes_annees):
            continue
        if signe in ("-", "−", "–"):
            lec = tuple(-x for x in lec)
        pct = bool(_UNITE_PCT.match(apres))
        out.append(NombreTrouve(texte=(signe + corps).strip(), debut=m.start(), fin=fin,
                                lectures=lec, pourcentage=pct))
    return out


def cles(n: NombreTrouve) -> Set[str]:
    """Clés de comparaison d'un nombre : ses lectures canoniques, en valeur
    absolue (« baisse de 3,2 % » doit retrouver la variation −3,2)."""
    return {canon(abs(x)) for x in n.lectures}


def cles_valeur(texte: str) -> Set[str]:
    """Clés d'une écriture de valeur autorisée (source : tableau ou variation)."""
    ns = extraire_nombres(texte, bornes_annees=(0, -1), garder_references=True)
    out: Set[str] = set()
    for n in ns:
        out |= cles(n)
    return out


def en_float(texte: str) -> Optional[float]:
    """Valeur numérique d'une cellule de tableau (première lecture), ou None."""
    ns = extraire_nombres(texte, bornes_annees=(0, -1), garder_references=True)
    if len(ns) != 1:
        return None
    # Dans les Annuaires, les milliers sont séparés par des espaces : la
    # première lecture (point ou virgule = décimale) est la bonne.
    return float(ns[0].lectures[0])


def formater_fr(x: float, decimales: int) -> str:
    """Écriture à la française : espace pour les milliers, virgule décimale.
    Arrondi au plus proche, demi vers le haut. formater_fr(12500.456, 1) -> '12 500,5'."""
    q = Decimal(str(x)).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    signe = "-" if q < 0 else ""
    ent, _, dec = format(abs(q), "f").partition(".")
    groupes = []
    while len(ent) > 3:
        groupes.insert(0, ent[-3:])
        ent = ent[:-3]
    groupes.insert(0, ent)
    s = " ".join(groupes)
    return f"{signe}{s},{dec}" if dec else f"{signe}{s}"
