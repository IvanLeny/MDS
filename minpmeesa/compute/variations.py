"""Calcul déterministe des variations (section 3.3.3).

Le programme calcule, le modèle de langage ne calcule jamais.
  var_abs     = v − v_ref
  var_rel_pct = 100 × (v − v_ref) / v_ref      (v_ref = 0 -> pas de variation relative)
Arrondi selon la convention du ministère : 1 décimale pour les pourcentages,
et pour les écarts absolus la précision des valeurs sources.

Chaque variation conserve les identifiants des deux valeurs sources
(valeur_id, valeur_ref_id) : c'est ce qui permet la traçabilité BN4.

Deux cas de figure dans les Annuaires :
  - le tableau apparié porte une série (colonnes ou lignes millésimées) :
    v et v_ref viennent du même tableau, donc de la même édition ;
  - le tableau ne porte que l'exercice : v_ref vient du tableau apparié au
    même indicateur dans l'Annuaire de l'exercice antérieur (même ligne, même colonne).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .. import config
from ..guards.normalize import formater_fr

_ANNEE = re.compile(r"\b(20[0-3]\d)\b")


@dataclass
class Point:
    valeur_id: int
    annee: int
    serie: Tuple[str, ...]           # (ligne, colonne, nature) sans millésime
    valeur: float
    texte: str
    unite: str
    page: int
    tableau_n: Optional[int]
    doc_id: str


_MOTS_UNITE = re.compile(r"\b(effectifs?|nombre|valeur)\b|%", re.I)


def _sans_annee(s: str, unites: bool = False) -> str:
    """Libellé débarrassé du millésime (et, pour une colonne, des mots d'unité :
    « 2016 · Effectif » et « 2020 (e) » appartiennent à la même série)."""
    s = _ANNEE.sub("", s or "")
    s = re.sub(r"\(\s*[ep]\s*\)", "", s)           # « 2023 (e) » : estimation
    if unites:
        s = _MOTS_UNITE.sub("", s)
    parts = [p.strip() for p in s.split("·")]
    return " · ".join(p for p in parts if p)


def annee_de(ligne: str, colonne: str) -> Optional[int]:
    """Millésime porté par la cellule (colonne d'abord, puis ligne)."""
    for s in (colonne, ligne):
        m = _ANNEE.findall(s or "")
        if len(m) == 1:
            return int(m[0])
    return None


def decimales(texte: str) -> int:
    m = re.search(r"[.,](\d+)\s*%?\s*$", texte.strip())
    return len(m.group(1)) if m else 0


def points_du_tableau(rows) -> List[Point]:
    """Convertit les triplets d'un tableau en points datés."""
    out = []
    for r in rows:
        if r["valeur_num"] is None:
            continue
        a = annee_de(r["ligne"], r["colonne"])
        if a is None:
            continue
        nature = "%" if (r["unite"] or "") == "%" else "niveau"
        out.append(Point(valeur_id=r["valeur_id"], annee=a,
                         serie=(_sans_annee(r["ligne"]), _sans_annee(r["colonne"], True), nature),
                         valeur=float(r["valeur_num"]), texte=r["valeur_texte"],
                         unite=r["unite"] or "", page=r["page"], tableau_n=r["tableau_n"],
                         doc_id=r["doc_id"]))
    return out


def variation(p: Point, ref: Point, code: str) -> dict:
    """Une ligne de la table `variations`."""
    dec_pct = int(config.get("commentaire.decimales_pourcentage", 1))
    dec_abs = max(int(config.get("commentaire.decimales_absolue", 0)),
                  decimales(p.texte), decimales(ref.texte))
    var_abs = p.valeur - ref.valeur
    var_rel = None if ref.valeur == 0 else 100.0 * var_abs / ref.valeur
    lib = " · ".join(x for x in p.serie[:2] if x) or "valeur"
    if p.serie[-1] == "%":
        lib += " (%)"
    return {
        "code_indicateur": code, "ligne": lib, "exercice": p.annee, "exercice_ref": ref.annee,
        "valeur": p.valeur, "valeur_ref": ref.valeur,
        "var_abs": round(var_abs, dec_abs), "var_rel_pct": None if var_rel is None else round(var_rel, dec_pct),
        "var_abs_texte": formater_fr(var_abs, dec_abs),
        "var_rel_texte": None if var_rel is None else formater_fr(var_rel, dec_pct),
        "valeur_id": p.valeur_id, "valeur_ref_id": ref.valeur_id,
        "unite": p.unite,
    }


def _par_serie(points: List[Point], exercice: int) -> Dict[tuple, Dict[int, Point]]:
    """Regroupe les points par série, années ≤ exercice. Deux valeurs pour la
    même série et la même année : lecture ambiguë du tableau, l'année est
    retirée de la série (aucune variation n'est calculée sur une valeur douteuse)."""
    par_serie: Dict[tuple, Dict[int, Point]] = {}
    ambigus = set()
    for p in points:
        if p.annee > exercice:
            continue
        s = par_serie.setdefault(p.serie, {})
        if p.annee in s:
            ambigus.add((p.serie, p.annee))
        s[p.annee] = p
    for serie, annee in ambigus:
        par_serie[serie].pop(annee, None)
    return par_serie


def variations_serie(points: List[Point], code: str, exercice: int) -> List[dict]:
    """Variations de l'exercice traité par rapport à CHAQUE exercice antérieur
    disponible dans la même série. Aucune valeur postérieure n'est utilisée."""
    par_serie = _par_serie(points, exercice)
    out = []
    for serie, pts in par_serie.items():
        if exercice not in pts:
            continue
        for a in sorted(pts):
            if a < exercice:
                out.append(variation(pts[exercice], pts[a], code))
    return out


def variations_historiques(points: List[Point], code: str, exercice: int) -> List[dict]:
    """Variations d'une année sur l'autre (a vs a-1) pour a ≤ exercice :
    sert à la volatilité (BN1) et à la mise en perspective (BN2)."""
    par_serie = _par_serie(points, exercice)
    out = []
    for serie, pts in par_serie.items():
        annees = sorted(pts)
        for a0, a1 in zip(annees, annees[1:]):
            out.append(variation(pts[a1], pts[a0], code))
    return out


def calculer_pour_indicateur(base, code: str, exercice: int) -> List[dict]:
    """Variations de `code` pour l'exercice traité, à partir du tableau apparié
    dans l'Annuaire de cet exercice (et, à défaut de série, de l'Annuaire N-1)."""
    app = base.q("SELECT * FROM appariement WHERE code_indicateur=? AND exercice=? "
                 "AND statut != 'rejete' AND tableau_n IS NOT NULL", (code, exercice))
    if not app:
        return []
    a = app[0]
    rows = base.valeurs_tableau(a["doc_annuaire"], a["tableau_n"])
    pts = points_du_tableau(rows)
    out = variations_serie(pts, code, exercice)
    if out:
        return out
    # Pas de série dans le tableau : on rapproche du tableau apparié en N-1.
    prec = base.q("SELECT * FROM appariement WHERE code_indicateur=? AND exercice<? "
                  "AND statut != 'rejete' AND tableau_n IS NOT NULL ORDER BY exercice DESC",
                  (code, exercice))
    if not prec:
        return []
    p = prec[0]
    ref_rows = {(r["ligne"], r["colonne"]): r for r in base.valeurs_tableau(p["doc_annuaire"], p["tableau_n"])}
    for r in rows:
        ref = ref_rows.get((r["ligne"], r["colonne"]))
        if ref is None or r["valeur_num"] is None or ref["valeur_num"] is None:
            continue
        nat = "%" if (r["unite"] or "") == "%" else "niveau"
        cur = Point(r["valeur_id"], exercice, (r["ligne"], r["colonne"], nat), float(r["valeur_num"]),
                    r["valeur_texte"], r["unite"] or "", r["page"], r["tableau_n"], r["doc_id"])
        old = Point(ref["valeur_id"], p["exercice"], (ref["ligne"], ref["colonne"], nat),
                    float(ref["valeur_num"]), ref["valeur_texte"], ref["unite"] or "",
                    ref["page"], ref["tableau_n"], ref["doc_id"])
        out.append(variation(cur, old, code))
    return out


def recalculer_tout(base) -> int:
    """(Re)calcule la table `variations` pour tous les indicateurs appariés."""
    base.conn.execute("DELETE FROM variations")
    n = 0
    for a in base.q("SELECT DISTINCT code_indicateur, exercice FROM appariement "
                    "WHERE statut != 'rejete'"):
        rows = calculer_pour_indicateur(base, a["code_indicateur"], a["exercice"])
        base.ajouter_variations(rows)
        n += len(rows)
    base.commit()
    return n
