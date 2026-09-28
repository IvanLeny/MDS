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


def libelle_source(s: dict) -> str:
    if s.get("nature") == "variation":
        return (f"variation calculée ({s.get('grandeur')}) : {s.get('ligne')}, "
                f"valeurs n° {s.get('valeur_id')} et n° {s.get('valeur_ref_id')} (réf. {s.get('exercice_ref')})")
    return (f"{s.get('doc_id')}, tableau {s.get('tableau_n')}, p. {s.get('page')} "
            f"({s.get('ligne')} | {s.get('colonne')})")


def tracer(con: sqlite3.Connection, enonces: list[dict], modeles: list[dict]) -> list[dict]:
    """Complète chaque énoncé par ses références lisibles."""
    out = []
    for e in enonces:
        refs = []
        for s in e.get("sources", []):
            ref = {"valeur": s.get("valeur"), "nature": s.get("nature"), "libelle": libelle_source(s)}
            if s.get("nature") == "variation":
                ref["valeurs_sources"] = [valeur(con, s["valeur_id"]), valeur(con, s["valeur_ref_id"])]
            else:
                ref["valeurs_sources"] = [valeur(con, s["valeur_id"])] if s.get("valeur_id") else []
            refs.append(ref)
        forme = None
        if modeles:
            m = max(modeles, key=lambda m: jaccard(e["texte"], m["texte"]))
            if jaccard(e["texte"], m["texte"]) > 0.05:
                forme = {"doc_id": m["doc_id"], "page": m["page"], "passage_id": m["passage_id"],
                         "libelle": f"modèle de rédaction : {m['doc_id']}, p. {m['page']}"}
        out.append({**e, "references": refs, "modele_de_forme": forme})
    return out
