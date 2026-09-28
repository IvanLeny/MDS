"""Tableaux -> triplets (valeur, ligne, colonne) + unité (section 3.2.2).

Repris de src/ingestion/tables.py, avec une différence de méthode : les
en-têtes de colonne sont rattachés aux valeurs par la GÉOMÉTRIE (position
horizontale des mots d'en-tête au-dessus de la cellule), et non par l'indice
de colonne. La détection de tableaux de PyMuPDF restitue mal les cellules
fusionnées (« 2016 » couvrant « Effectif » et « % », « 2024 (e) Effectif % »
tassés dans une seule cellule) ; la position des mots, elle, est fiable.

Libellé de ligne : cellules non numériques à gauche de la première valeur,
avec report vertical des libellés de premier niveau (région, CFCE…) et
récupération d'un libellé placé sur une ligne voisine (cellule fusionnée
verticalement, cas du Tableau 1 de l'Annuaire 2024).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pymupdf

from ..guards.normalize import en_float

# Une cellule de donnée : un seul nombre, éventuellement suivi de % ou d'un renvoi.
_NUM_CELL = re.compile(
    r"^[+\-−]?(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,]\d+)?\s*%?\s*(?:\(\w\)|\*)?$")
_ANNEE_SEULE = re.compile(r"^20\d\d\s*(\(\s*[ep]\s*\))?$")
_TITRE = re.compile(r"Tableau\s+(\d+)\s*[:.\-–]\s*(.+)", re.S)


@dataclass
class Triplet:
    ligne: str
    colonne: str
    valeur_texte: str
    valeur_num: Optional[float]
    unite: str


@dataclass
class TableauExtrait:
    page: int
    numero: Optional[int]
    intitule: str
    bbox: Tuple[float, float, float, float]
    triplets: List[Triplet] = field(default_factory=list)

    def texte(self) -> str:
        tete = f"Tableau {self.numero} : {self.intitule}" if self.numero else (self.intitule or "Tableau")
        lignes = [f"{t.ligne} | {t.colonne} = {t.valeur_texte}" if t.colonne
                  else f"{t.ligne} = {t.valeur_texte}" for t in self.triplets]
        return tete + "\n" + "\n".join(lignes)


def _propre(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def est_valeur(s: Optional[str]) -> bool:
    s = _propre(s)
    return bool(s) and bool(_NUM_CELL.match(s)) and not _ANNEE_SEULE.match(s)


def unite_titre(intitule: str) -> str:
    m = re.search(r"\(\s*en\s+([^)]+)\)", intitule, re.I)
    return m.group(1).strip() if m else ""


def _lignes_entete(mots, x_min: float) -> List[List[tuple]]:
    """Regroupe les mots d'en-tête en lignes (même ordonnée) puis en
    expressions (mots proches sur une même ligne). Renvoie, pour chaque ligne,
    une liste de (x0, x1, texte)."""
    mots = sorted((w for w in mots if w[2] >= x_min), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lignes: List[List[tuple]] = []
    for w in mots:
        yc = (w[1] + w[3]) / 2
        if lignes and abs(lignes[-1][0][0] - yc) <= 3.0:
            lignes[-1].append((yc, w))
        else:
            lignes.append([(yc, w)])
    out = []
    for l in lignes:
        ws = sorted((w for _, w in l), key=lambda w: w[0])
        expr: List[list] = []
        for w in ws:
            if expr and w[0] - expr[-1][1] <= 4.5:
                expr[-1][1] = w[2]
                expr[-1][2] += " " + w[4]
            else:
                expr.append([w[0], w[2], w[4]])
        out.append([(a, b, t) for a, b, t in expr])
    return out


_EXPR_ANNEE = re.compile(r"^(20\d\d)\s*(\(\s*[ep]\s*\))?$")


def _entete_colonne(x0: float, x1: float, lignes: List[List[tuple]]) -> str:
    """Chemin d'en-tête d'une cellule.
    - millésime : UN seul, celui qui recouvre la cellule ou, à défaut (en-tête
      fusionné centré sur plusieurs colonnes), le plus proche horizontalement ;
    - sous-en-têtes (Effectif, %…) : expressions dont le centre tombe dans la cellule."""
    larg = max(x1 - x0, 12.0)
    cx = (x0 + x1) / 2
    annees = [e for l in lignes for e in l if _EXPR_ANNEE.match(e[2])]
    annee = None
    recouvrants = [(min(b, x1) - max(a, x0), t) for a, b, t in annees if min(b, x1) - max(a, x0) > 0]
    if recouvrants:
        annee = max(recouvrants)[1]
    elif annees:
        a, b, t = min(annees, key=lambda e: abs((e[0] + e[1]) / 2 - cx))
        if abs((a + b) / 2 - cx) <= 1.6 * larg:
            annee = t
    parts = [annee] if annee else []
    for l in lignes:
        for a, b, t in l:
            if _EXPR_ANNEE.match(t):
                continue
            if x0 - 2 <= (a + b) / 2 <= x1 + 2 and t not in parts:
                parts.append(t)
    return " · ".join(parts)


def _unite(colonne: str, titre_unite: str) -> str:
    c = colonne.lower()
    if "%" in c or "proportion" in c or "part" in c.split():
        return "%"
    if re.search(r"effectif|nombre", c):
        return "nombre"
    return titre_unite


def lineariser(table, page: pymupdf.Page, numero: Optional[int], intitule: str) -> TableauExtrait:
    rows = table.extract()
    geo = table.rows
    tab = TableauExtrait(page=page.number + 1, numero=numero, intitule=intitule,
                         bbox=tuple(round(x, 1) for x in table.bbox))
    if not rows or len(rows) != len(geo):
        return tab
    data_idx = [i for i, r in enumerate(rows) if any(est_valeur(c) for c in r[1:])]
    if not data_idx:
        return tab
    premiere = geo[data_idx[0]]
    # Zone d'en-tête : entre le haut du tableau et la première ligne de données.
    y_haut, y_bas = table.bbox[1] - 2, premiere.bbox[1] + 1
    x_valeurs = min(geo[i].cells[j][0] for i in data_idx for j, c in enumerate(rows[i])
                    if est_valeur(c) and j < len(geo[i].cells) and geo[i].cells[j])
    mots = [w for w in page.get_text("words")
            if w[1] >= y_haut and w[3] <= y_bas and table.bbox[0] - 2 <= w[0] <= table.bbox[2] + 2]
    lignes = _lignes_entete(mots, x_valeurs - 3)
    t_unite = unite_titre(intitule)

    niveau1 = ""
    etiquettes_seules = {}
    for i, r in enumerate(rows):
        if i in data_idx or i < data_idx[0]:
            continue
        lab = " ".join(_propre(c) for c in r if _propre(c))
        if lab:
            etiquettes_seules[i] = lab
    consommees = set()
    for i in data_idx:
        r, g = rows[i], geo[i]
        j0 = next(j for j, c in enumerate(r) if j >= 1 and est_valeur(c))
        if r[0] is not None and _propre(r[0]) and j0 > 1:
            niveau1 = _propre(r[0])
        gauche = [_propre(c) for c in r[:j0] if _propre(c)]
        # Cellule None = fusion verticale : on reporte le libellé de premier niveau.
        if j0 > 1 and r[0] is None and niveau1:
            gauche = [niveau1] + gauche
        libelle = " · ".join(dict.fromkeys(gauche))
        if not libelle:
            for k in (i + 1, i - 1):
                if k in etiquettes_seules and k not in consommees:
                    libelle = etiquettes_seules[k]
                    consommees.add(k)
                    break
        if not libelle:
            continue
        for j in range(j0, len(r)):
            c = r[j]
            if not est_valeur(c) or j >= len(g.cells) or not g.cells[j]:
                continue
            x0, _, x1, _ = g.cells[j]
            col = _entete_colonne(x0, x1, lignes)
            txt = _propre(c)
            tab.triplets.append(Triplet(ligne=libelle, colonne=col, valeur_texte=txt,
                                        valeur_num=en_float(re.sub(r"\(\w\)|\*", "", txt)),
                                        unite=_unite(col, t_unite)))
    _valeurs_non_rattachees(tab, rows)
    return tab


NON_RATTACHEE = "(valeur non rattachée à une ligne)"


def _valeurs_non_rattachees(tab: TableauExtrait, rows) -> None:
    """Valeurs tassées dans une cellule multiligne (« 7 096 1,6\\n125 961 28,4 »)
    que la lecture cellule par cellule ne rattache à aucune ligne. On les garde
    comme valeurs du tableau (même page, même numéro), sans libellé : elles
    restent citables et traçables, mais n'entrent dans aucune variation."""
    from ..guards.normalize import cles, extraire_nombres
    deja = set()
    for t in tab.triplets:
        for n in extraire_nombres(t.valeur_texte, bornes_annees=(0, -1), garder_references=True):
            deja |= cles(n)
    for r in rows:
        for c in r:
            if not c or "\n" not in c or est_valeur(c):
                continue
            for n in extraire_nombres(c, bornes_annees=(2010, 2035)):
                if cles(n) & deja:
                    continue
                deja |= cles(n)
                tab.triplets.append(Triplet(ligne=NON_RATTACHEE, colonne="", valeur_texte=n.texte,
                                            valeur_num=float(n.lectures[0]), unite=""))


def _titres(page: pymupdf.Page) -> List[Tuple[float, int, str]]:
    out = []
    for b in page.get_text("blocks"):
        m = _TITRE.match(_propre(b[4]))
        if m:
            out.append((b[3], int(m.group(1)), _propre(m.group(2))))
    return out


def extraire_tableaux(chemin: str) -> List[TableauExtrait]:
    """Tous les tableaux porteurs de valeurs d'un PDF, avec numéro et intitulé.
    Un tableau sans titre en haut de page prolonge le tableau de la page
    précédente (tableau scindé entre deux pages)."""
    doc = pymupdf.open(chemin)
    out: List[TableauExtrait] = []
    dernier: Tuple[Optional[int], str] = (None, "")
    for page in doc:
        try:
            trouves = page.find_tables().tables
        except Exception:
            continue
        titres = _titres(page)
        for t in sorted(trouves, key=lambda t: t.bbox[1]):
            au_dessus = [x for x in titres if x[0] <= t.bbox[1] + 6]
            if au_dessus:
                _, num, inti = max(au_dessus, key=lambda x: x[0])
                dernier = (num, inti)
            elif t.bbox[1] > page.rect.height * 0.35:
                dernier = (None, "")
            lin = lineariser(t, page, dernier[0], dernier[1])
            if lin.triplets:
                out.append(lin)
    doc.close()
    return out
