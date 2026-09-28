"""Ligne de commande : python -m minpmeesa.app.cli <commande> ..."""
from __future__ import annotations

import argparse
import json

from .. import config
from ..generation.llm import obtenir


def main():
    ap = argparse.ArgumentParser(prog="minpmeesa")
    ap.add_argument("--llm", default=None, choices=["ollama", "llamacpp", "none"])
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("construire", help="reconstruire la base depuis data/corpus")
    c = sp.add_parser("consulter"); c.add_argument("question")
    c = sp.add_parser("commenter"); c.add_argument("code"); c.add_argument("exercice", type=int)
    c = sp.add_parser("note-analyse"); c.add_argument("exercice", type=int); c.add_argument("--chapitre", default=r"CHAPITRE I\b")
    c = sp.add_parser("note-strategique"); c.add_argument("exercice", type=int)
    sp.add_parser("indicateurs", help="lister les indicateurs appariés")
    a = ap.parse_args()
    if a.cmd == "construire":
        from ..ingestion.build import main as b
        return b()
    from ..retrieval.hybrid import Moteur
    m = Moteur()
    client, expl = obtenir(config.charger(), a.llm)
    if a.cmd == "consulter":
        from ..retrieval.consultation import consulter
        r = consulter(a.question, m)
        print(r["message"] or "")
        for p in r["passages"]:
            print(f"- {p['titre']}, p. {p['page']} : {p['extrait']}")
    elif a.cmd == "commenter":
        from ..export.markdown_export import commentaire
        from ..generation.commentary import commenter
        print(f"[{expl}]\n" + commentaire(commenter(m.con, a.code, a.exercice, client, moteur=m)))
    elif a.cmd == "note-analyse":
        from ..export.markdown_export import note_analyse
        from ..generation.analysis_note import rediger
        print(note_analyse(rediger(m.con, a.exercice, chapitre=a.chapitre, client=client, moteur=m)))
    elif a.cmd == "note-strategique":
        from ..export.markdown_export import note_strategique
        from ..generation.strategic_note import rediger
        print(note_strategique(rediger(m.con, a.exercice, client, m)))
    elif a.cmd == "indicateurs":
        for r in m.con.execute("SELECT exercice, code_indicateur, statut, graphique_intitule FROM appariement "
                               "ORDER BY exercice DESC, graphique_n"):
            print(json.dumps(dict(r), ensure_ascii=False))


if __name__ == "__main__":
    main()
