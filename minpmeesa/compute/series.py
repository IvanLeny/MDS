"""Séries annuelles d'un indicateur, lues dans les variations calculées (valeurs de l'Annuaire).

Sert aux petits graphiques de l'interface (accueil, commentaire) : chaque point est une valeur
publiée d'un tableau de l'Annuaire ; aucune année manquante n'est interpolée.
"""
from __future__ import annotations

import re
import sqlite3


def nombre(texte: str | None) -> float | None:
    """« 443 524 » -> 443524.0 ; « 7 291 » -> 7291.0 ; « 12,8 » -> 12.8."""
    t = re.sub(r"[^\d,.\-]", "", texte or "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def serie(con: sqlite3.Connection, code: str, exercice: int, ligne: str,
          sous_colonne: str | None = None) -> list[tuple[int, float]]:
    """[(année, valeur)] de la ligne `ligne` de l'indicateur, vue depuis l'exercice `exercice`."""
    q = ("SELECT exercice_ref, valeur_ref, valeur FROM variations WHERE code_indicateur=? AND exercice=? "
         "AND ligne=?")
    args: list = [code, exercice, ligne]
    if sous_colonne is not None:
        q += " AND COALESCE(sous_colonne, '')=?"
        args.append(sous_colonne)
    pts: dict[int, float] = {}
    for ref, v_ref, v in con.execute(q, args):
        if v_ref is not None:
            pts.setdefault(int(ref), float(v_ref))
        if v is not None:
            pts.setdefault(int(exercice), float(v))
    return sorted(pts.items())


def serie_principale(con: sqlite3.Connection, code: str, exercice: int,
                     valeur: float | None = None) -> tuple[str | None, list[tuple[int, float]]]:
    """Ligne principale de l'indicateur (celle dont la valeur de l'exercice vaut `valeur`, sinon le total)
    et sa série. Renvoie (None, []) si l'indicateur n'a pas de variation calculée."""
    lignes = con.execute("SELECT DISTINCT ligne, COALESCE(sous_colonne, ''), valeur FROM variations "
                         "WHERE code_indicateur=? AND exercice=?", (code, exercice)).fetchall()
    if not lignes:
        return None, []

    def rang(l):
        meme = valeur is not None and l[2] is not None and abs(l[2] - valeur) < 1e-6
        total = bool(re.match(r"\s*(total|ensemble)", l[0] or "", re.I))
        return (not meme, not total, l[1] not in ("", "Effectif", "Effectifs"))

    ligne, sc, _ = min(lignes, key=rang)
    return ligne, serie(con, code, exercice, ligne, sc)
