"""Livrables d'exemples demandés par l'encadreur (§8), exercice 2024.

    python -m minpmeesa.evaluation.exemples [--llm none|ollama]

Produit dans data/outputs/ : commentaire_exemple.docx, note_analyse_chapitre_PME_2024.docx,
note_strategique_2024.docx, tracabilite_exemple.csv (+ versions Markdown et JSON).
"""
from __future__ import annotations

import argparse
import csv
import json

from .. import config
from ..export import docx_export, markdown_export
from ..generation import analysis_note, commentary, strategic_note
from ..generation.llm import obtenir
from ..retrieval.hybrid import moteur as moteur_defaut
from ..store import db

CODE_EXEMPLE = "pme-creees-sur-periode"      # graphique 4 du rapport 2024 <-> tableau 7 de l'Annuaire


def generer(llm: str | None = None, exercice: int = 2024) -> dict:
    cfg = config.charger()
    client, explication = obtenir(cfg, llm)
    con, m = db.connecter(), moteur_defaut()
    out = config.chemin("sorties")
    out.mkdir(parents=True, exist_ok=True)
    com = commentary.commenter(con, CODE_EXEMPLE, exercice, client, moteur=m)
    docx_export.exporter_commentaire(com, out / "commentaire_exemple.docx")
    (out / "commentaire_exemple.md").write_text(markdown_export.commentaire(com), encoding="utf-8")
    na = analysis_note.rediger(con, exercice, chapitre=r"CHAPITRE I\b", client=client, moteur=m,
                               titre=f"Rapport d'analyse des tableaux de l'Annuaire {exercice} — chapitre I : PME")
    docx_export.exporter_note_analyse(na, out / f"note_analyse_chapitre_PME_{exercice}.docx")
    (out / f"note_analyse_chapitre_PME_{exercice}.md").write_text(markdown_export.note_analyse(na), encoding="utf-8")
    ns = strategic_note.rediger(con, exercice, client, m)
    docx_export.exporter_note_strategique(ns, out / f"note_strategique_{exercice}.docx")
    (out / f"note_strategique_{exercice}.md").write_text(markdown_export.note_strategique(ns), encoding="utf-8")
    with open(out / "tracabilite_exemple.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ns["tracabilite"][0]), delimiter=";")
        w.writeheader()
        w.writerows(ns["tracabilite"])
    bilan = {"modele": explication, "commentaire_enonces": len(com.get("enonces", [])),
             "note_analyse_tableaux_commentes": len(na["sections"]),
             "note_analyse_tableaux_a_commenter_manuellement": len(na["abstentions"]),
             "note_strategique_evolutions": ns["nb_evolutions"], "note_strategique_mots": ns["nb_mots"],
             "verification_bn4_bn5": strategic_note.verifier_bn4_bn5(ns),
             "provisoire": ns["provisoire"], "mode_extractif": client is None}
    (out / "exemples_bilan.json").write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")
    return bilan


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default=None, choices=["ollama", "api", "llamacpp", "none"])
    print(json.dumps(generer(ap.parse_args().llm), indent=2, ensure_ascii=False))
