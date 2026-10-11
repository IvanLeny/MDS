"""Traçabilité énoncé -> passage / tableau / page (BF7, BN4).

Reprise de l'ancien `src/guards/provenance.py`, en deux niveaux :
  - un énoncé qui cite une valeur renvoie au tableau et à la page de chaque
    valeur (et, pour une variation, à ses DEUX valeurs sources) ;
  - un énoncé sans valeur (interprétation, perspective) renvoie au modèle de
    rédaction dont il reprend le plus la formulation, s'il y en a un.
"""
from __future__ import annotations

import sqlite3

from ..texte import jaccard


def valeur(con: sqlite3.Connection, valeur_id: int) -> dict | None:
    r = con.execute("SELECT v.valeur_id, v.doc_id, v.page, v.tableau_n, v.tableau_intitule, v.ligne, "
                    "v.colonne, v.valeur_texte, d.titre FROM valeurs v JOIN documents d USING(doc_id) "
                    "WHERE valeur_id=?", (valeur_id,)).fetchone()
    return dict(r) if r else None


_NOMS = [(r"^annuaire_(\d{4})", "Annuaire {0}"), (r"^rapport_analyse_(\d{4})", "Rapport d'analyse {0}"),
         (r"^note_conjoncture_(T\d)_(\d{4})", "Note de conjoncture {0} {1}")]


def nom_document(doc_id: str | None) -> str:
    """« annuaire_2024 » -> « Annuaire 2024 » (libellé destiné au lecteur ; l'identifiant reste en base)."""
    import re
    for motif, gabarit in _NOMS:
        m = re.match(motif, doc_id or "")
        if m:
            return gabarit.format(*m.groups())
    return (doc_id or "").replace("_", " ").capitalize()


def _cellule(v: dict | None) -> str:
    if not v:
        return ""
    return f"{nom_document(v.get('doc_id'))}, tableau {v.get('tableau_n')}, p. {v.get('page')}"


def libelle_source(s: dict, v: dict | None = None) -> str:
    """Libellé lisible d'une source. Pour une variation, `v` est la valeur de l'exercice (pour situer le
    tableau) ; les numéros des deux valeurs restent dans `valeurs_sources` (traçabilité)."""
    if s.get("nature") == "variation":
        ref = f", {s.get('exercice')} / {s.get('exercice_ref')}" if s.get("exercice") else f" (réf. {s.get('exercice_ref')})"
        ou = f" — {_cellule(v)}" if v else ""
        return f"Variation calculée par le programme : {s.get('ligne')}{ref}{ou}"
    return (f"{nom_document(s.get('doc_id'))}, tableau {s.get('tableau_n')}, p. {s.get('page')} "
            f"— {s.get('ligne')}, {s.get('colonne')}")


def a_afficher(refs: list[dict]) -> list[str]:
    """Libellés de sources à montrer au lecteur : sans doublon, et sans les nombres lus dans un libellé
    de ligne ou de colonne (« 30-40 ans » -> 30, 40), qui restent dans la traçabilité complète."""
    return list(dict.fromkeys(r["libelle"] for r in refs if r.get("nature") != "libellé"))


def tracer(con: sqlite3.Connection, enonces: list[dict], modeles: list[dict]) -> list[dict]:
    """Complète chaque énoncé par ses références lisibles."""
    out = []
    for e in enonces:
        refs = []
        for s in e.get("sources", []):
            if s.get("nature") == "variation":
                vs = [valeur(con, s["valeur_id"]), valeur(con, s["valeur_ref_id"])]
            else:
                vs = [valeur(con, s["valeur_id"])] if s.get("valeur_id") else []
            ref = {"valeur": s.get("valeur"), "nature": s.get("nature"),
                   "libelle": libelle_source(s, vs[0] if vs else None), "valeurs_sources": vs}
            refs.append(ref)
        forme = None
        if modeles:
            m = max(modeles, key=lambda m: jaccard(e["texte"], m["texte"]))
            if jaccard(e["texte"], m["texte"]) > 0.05:
                forme = {"doc_id": m["doc_id"], "page": m["page"], "passage_id": m["passage_id"],
                         "libelle": f"modèle de rédaction : {nom_document(m['doc_id'])}, p. {m['page']}"}
        out.append({**e, "references": refs, "modele_de_forme": forme})
    return out
