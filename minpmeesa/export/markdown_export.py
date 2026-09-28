"""Export Markdown des commentaires et des notes (lecture rapide, versionnable)."""
from __future__ import annotations

from ..generation.strategic_note import RUBRIQUES


def _drapeaux(o: dict) -> list[str]:
    out = []
    if o.get("mode_extractif"):
        out.append("> ⚠ Mode extractif (sans modèle de langage).")
    if o.get("provisoire"):
        out.append("> ⚠ PROVISOIRE : appariement non validé.")
    if o.get("commentaires_non_valides") or o.get("valide") is False:
        out.append("> ⚠ Commentaires non validés : à relire.")
    return out


def commentaire(res: dict) -> str:
    l = [f"### {res.get('indicateur') or res.get('tableau_intitule')} ({res['exercice']})", *_drapeaux(res)]
    if res.get("abstention"):
        return "\n".join(l + [f"*{res.get('mention')} — {res.get('motif')}*"])
    for e in res["enonces"]:
        l.append(f"- **{e.get('type', '')}** : {e['texte']}")
        for r in e.get("references", []):
            l.append(f"  - source : {r['libelle']}")
    for v in res.get("valeurs_ecartees", []):
        l.append(f"- *valeur écartée* : {v['valeur']} ({v['action']})")
    return "\n".join(l)


def note_analyse(note: dict) -> str:
    l = [f"# {note['titre']}", *_drapeaux(note)]
    chap = None
    for s in note["sections"]:
        if s["chapitre"] != chap:
            chap = s["chapitre"]
            l.append(f"\n## {chap}")
        l.append("\n" + commentaire(s["commentaire"]))
    return "\n".join(l)


def note_strategique(note: dict) -> str:
    l = [f"# {note['titre']}", *_drapeaux(note)]
    for r in RUBRIQUES:
        l.append(f"\n## {r}")
        l += [f"- {b['texte']}" for b in note["rubriques"][r]]
    return "\n".join(l)
