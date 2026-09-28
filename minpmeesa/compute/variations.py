"""Calcul déterministe des variations (section 3.3.3).

Le modèle de langage ne calcule jamais : le programme calcule, pour chaque
exercice antérieur disponible,
    var_abs     = v - v_ref
    var_rel_pct = 100 * (v - v_ref) / v_ref
avec la convention d'arrondi du ministère (1 décimale pour les %). Une valeur de
référence nulle ne donne pas de variation relative. Chaque variation garde les
identifiants des DEUX valeurs sources.

Deux sources de séries :
  1. les colonnes millésimées du tableau de l'Annuaire de l'exercice
     (ex. « 2016 … 2024 ») : valeurs publiées dans la même édition ;
  2. à défaut (tableau sans série), le même tableau apparié dans les Annuaires
     ANTÉRIEURS (même code indicateur, même libellé de ligne et de sous-colonne).
Aucune valeur postérieure à l'exercice traité n'est utilisée (BF6).
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from ..texte import normaliser


def decimales(texte: str) -> int:
    m = re.search(r"[.,](\d+)\s*%?\s*$", texte.strip())
    return len(m.group(1)) if m else 0


def formater(x: float, dec: int) -> str:
    """Écriture française : espace pour les milliers, virgule décimale."""
    s = f"{abs(x):,.{dec}f}".replace(",", " ").replace(".", ",")
    return ("-" if x < 0 and float(f"{abs(x):.{dec}f}") != 0 else "") + s


def arrondir(x: float, dec: int) -> float:
    """Arrondi « commercial » (0,05 -> 0,1), pas l'arrondi bancaire de Python."""
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-dec)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


@dataclass
class Variation:
    code_indicateur: str
    exercice: int
    exercice_ref: int
    ligne: str
    sous_colonne: str
    valeur: float
    valeur_ref: float
    var_abs: float
    var_abs_texte: str
    var_rel_pct: float | None
    var_rel_texte: str | None
    unite: str | None
    valeur_id: int
    valeur_ref_id: int


def calculer(v: float, v_texte: str, v_ref: float, v_ref_texte: str,
             dec_pct: int = 1) -> tuple[float, str, float | None, str | None]:
    """Variation absolue et relative, arrondies. Division par zéro -> pas de relative."""
    dec = max(decimales(v_texte), decimales(v_ref_texte))
    var_abs = arrondir(v - v_ref, dec)
    abs_txt = formater(var_abs, dec)
    if v_ref == 0:
        return var_abs, abs_txt, None, None
    rel = arrondir(100 * (v - v_ref) / v_ref, dec_pct)
    return var_abs, abs_txt, rel, formater(rel, dec_pct)


def _cle(ligne: str) -> str:
    return re.sub(r"\s+", " ", normaliser(ligne)).strip()


def variations_indicateur(con: sqlite3.Connection, code: str, exercice: int,
                          dec_pct: int = 1) -> list[Variation]:
    """Variations de l'indicateur `code` pour l'exercice traité."""
    app = con.execute("SELECT * FROM appariement WHERE code_indicateur=? AND exercice=?",
                      (code, exercice)).fetchone()
    if not app or app["tableau_n"] is None:
        return []
    vals = con.execute(
        "SELECT * FROM valeurs WHERE doc_id=? AND tableau_n=? AND valeur_num IS NOT NULL",
        (app["doc_annuaire"], app["tableau_n"])).fetchall()
    series: dict[tuple, dict[int, sqlite3.Row]] = {}
    sans_annee: dict[tuple, sqlite3.Row] = {}
    for v in vals:
        k = (_cle(v["ligne"]), v["sous_colonne"] or "")
        if v["annee_colonne"] is None:
            sans_annee.setdefault(k, v)
        elif v["annee_colonne"] <= exercice:          # BF6 : rien de postérieur
            series.setdefault(k, {}).setdefault(v["annee_colonne"], v)
    out: list[Variation] = []
    # 1) séries millésimées de la même édition
    for k, par_annee in series.items():
        cur = par_annee.get(exercice)
        if cur is None:
            continue
        for a, ref in sorted(par_annee.items()):
            if a >= exercice:
                continue
            va, vat, vr, vrt = calculer(cur["valeur_num"], cur["valeur_texte"],
                                        ref["valeur_num"], ref["valeur_texte"], dec_pct)
            out.append(Variation(code, exercice, a, cur["ligne"], k[1], cur["valeur_num"],
                                 ref["valeur_num"], va, vat, vr, vrt, cur["unite"],
                                 cur["valeur_id"], ref["valeur_id"]))
    # 2) tableaux sans série : éditions antérieures du même indicateur
    if not out and sans_annee:
        anciens = con.execute(
            "SELECT * FROM appariement WHERE code_indicateur=? AND exercice<? "
            "AND tableau_n IS NOT NULL ORDER BY exercice", (code, exercice)).fetchall()
        for a in anciens:
            prec = con.execute("SELECT * FROM valeurs WHERE doc_id=? AND tableau_n=? "
                               "AND valeur_num IS NOT NULL", (a["doc_annuaire"], a["tableau_n"])).fetchall()
            idx = {(_cle(v["ligne"]), v["sous_colonne"] or ""): v for v in prec
                   if v["annee_colonne"] in (None, a["exercice"])}
            for k, cur in sans_annee.items():
                ref = idx.get(k)
                if ref is None:
                    continue
                va, vat, vr, vrt = calculer(cur["valeur_num"], cur["valeur_texte"],
                                            ref["valeur_num"], ref["valeur_texte"], dec_pct)
                out.append(Variation(code, exercice, a["exercice"], cur["ligne"], k[1],
                                     cur["valeur_num"], ref["valeur_num"], va, vat, vr, vrt,
                                     cur["unite"], cur["valeur_id"], ref["valeur_id"]))
    return out


def calculer_tout(con: sqlite3.Connection, statuts: list[str], dec_pct: int = 1) -> int:
    """(Re)calcule la table `variations` pour toutes les lignes d'appariement utilisables."""
    con.execute("DELETE FROM variations")
    n = 0
    lignes = con.execute(
        f"SELECT code_indicateur, exercice FROM appariement WHERE statut IN ({','.join('?' * len(statuts))})",
        statuts).fetchall()
    for r in lignes:
        for v in variations_indicateur(con, r["code_indicateur"], r["exercice"], dec_pct):
            con.execute(
                "INSERT INTO variations (code_indicateur, exercice, exercice_ref, ligne, sous_colonne, "
                "valeur, valeur_ref, var_abs, var_abs_texte, var_rel_pct, var_rel_texte, unite, "
                "valeur_id, valeur_ref_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (v.code_indicateur, v.exercice, v.exercice_ref, v.ligne, v.sous_colonne, v.valeur,
                 v.valeur_ref, v.var_abs, v.var_abs_texte, v.var_rel_pct, v.var_rel_texte, v.unite,
                 v.valeur_id, v.valeur_ref_id))
            n += 1
    con.commit()
    return n
