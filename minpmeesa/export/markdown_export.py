"""Export Markdown des productions (lecture rapide, diff, archivage)."""
from __future__ import annotations

from pathlib import Path

from .docx_export import libelle_source


def commentaire_md(c) -> str:
    l = [f"# Commentaire — {c.intitule}", "", f"Exercice {c.exercice} · `{c.code}` · mode : {c.mode}", ""]
    if c.abstention:
        l += [f"> **Sources insuffisantes, à commenter manuellement.** ({c.abstention})", ""]
    for e in c.enonces:
        l.append(f"- {'*Perspective :* ' if e['type'] == 'perspective' else ''}{e['texte']}")
        for v in e.get("valeurs", []):
            l.append(f"  - « {v['valeur']} » : {libelle_source(v['source'])}")
    if c.ecartees:
        l += ["", "## Valeurs écartées", ""] + [f"- « {e['valeur']} » ({e['action']})" for e in c.ecartees]
    return "\n".join(l) + "\n"


def note_strategique_md(n) -> str:
    l = [f"# Note d'analyse stratégique — exercice {n.exercice}", "", f"Mode : {n.mode}", ""]
    l += [f"> {a}" for a in n.avertissements] + [""]
    l += ["## Messages clés", ""] + [f"- {m['texte']}" for m in n.messages]
    l += ["", "## Évolutions marquantes", ""] + [f"- {e['texte']}" for e in n.evolutions]
    l += ["", "## Points d'attention", ""] + [f"- {a}" for a in n.points_attention]
    l += ["", "## Pistes pour la décision", ""] + [f"- {p}" for p in n.pistes]
    l += ["", "## Sources", ""] + [f"- {s}" for s in n.sources]
    return "\n".join(l) + "\n"


def ecrire(texte: str, chemin: Path) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin
