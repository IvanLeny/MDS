"""Export Word (python-docx) des commentaires et des notes."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from ..generation.strategic_note import RUBRIQUES

GRIS = RGBColor(0x59, 0x59, 0x59)
ROUGE = RGBColor(0xA0, 0x1E, 0x1E)


def _rgb(hexa: str) -> RGBColor:
    return RGBColor.from_string(hexa.lstrip("#").upper())


def _doc(titre: str) -> Document:
    from ..app import identite
    i = identite.charger()
    vert = _rgb(i["couleurs"]["vert"])
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)
    for niveau in ("Title", "Heading 1", "Heading 2", "Heading 3"):
        d.styles[niveau].font.color.rgb = vert
    # En-tête de page : logo (s'il est fourni) + nom de l'outil et de la structure
    ent = d.sections[0].header.paragraphs[0]
    lg = identite.logo(i)
    if lg:
        ent.add_run().add_picture(str(lg), height=Cm(1.2))
        ent.add_run("   ")
    r = ent.add_run(f"{i['nom']} — {i['structure']}")
    r.font.size, r.font.color.rgb = Pt(9), GRIS
    d.add_heading(titre, level=0)
    return d


def _avertissements(d: Document, obj: dict):
    msgs = []
    if obj.get("mode_extractif"):
        msgs.append("Texte produit en MODE EXTRACTIF (sans modèle de langage) : gabarits déterministes.")
    if obj.get("provisoire"):
        msgs.append("PROVISOIRE : appariement indicateur / tableau non encore validé par double lecture.")
    if obj.get("commentaires_non_valides") or obj.get("valide") is False:
        msgs.append("Commentaires non encore validés par la Cellule : document à relire.")
    for m in msgs:
        p = d.add_paragraph()
        r = p.add_run("⚠ " + m)
        r.bold, r.font.color.rgb, r.font.size = True, ROUGE, Pt(9)


def _note_source(d: Document, texte: str):
    p = d.add_paragraph()
    r = p.add_run(texte)
    r.italic, r.font.size, r.font.color.rgb = True, Pt(8), GRIS
    p.paragraph_format.space_after = Pt(2)


def _commentaire(d: Document, res: dict, niveau: int = 1):
    if res.get("abstention"):
        p = d.add_paragraph()
        r = p.add_run(f"{res.get('mention', 'sources insuffisantes, à commenter manuellement')} — {res.get('motif', '')}")
        r.italic = True
        return
    for e in res.get("enonces", []):
        p = d.add_paragraph(e["texte"], style="List Bullet" if e.get("type") == "perspective" else None)
        refs = "; ".join(r["libelle"] for r in e.get("references", []))
        if refs:
            _note_source(d, "Sources : " + refs)
    if res.get("valeurs_ecartees"):
        _note_source(d, "Valeurs écartées par le contrôle : " +
                     ", ".join(f"{v['valeur']} ({v['action']})" for v in res["valeurs_ecartees"]))


def exporter_commentaire(res: dict, chemin: Path) -> Path:
    d = _doc(f"Commentaire — {res.get('indicateur') or res.get('tableau_intitule')}")
    _note_source(d, f"Exercice {res['exercice']} ; tableau {res.get('tableau_n')} de l'Annuaire "
                    f"({res.get('doc_annuaire')}) ; modèle : {res.get('modele')}")
    _avertissements(d, res)
    _commentaire(d, res)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d.save(chemin)
    return chemin


def exporter_note_analyse(note: dict, chemin: Path) -> Path:
    d = _doc(note["titre"])
    _note_source(d, f"Établie le {note['date']} ; modèle : {note['modele']}")
    _avertissements(d, note)
    chap = sect = None
    for s in note["sections"]:
        if s["chapitre"] != chap:
            chap = s["chapitre"]
            d.add_heading(chap, level=1)
            sect = None
        if s["section"] != sect and not s["section"].startswith("("):
            sect = s["section"]
            d.add_heading(sect, level=2)
        if s.get("transition"):
            d.add_paragraph(s["transition"])
        d.add_heading(f"Tableau {s['tableau_n']} : {s['intitule']}", level=3)
        if not s["valide"]:
            _note_source(d, "Commentaire non validé — à relire.")
        _commentaire(d, s["commentaire"])
    if note["abstentions"]:
        d.add_heading("Tableaux à commenter manuellement", level=1)
        for a in note["abstentions"]:
            d.add_paragraph(f"Tableau {a.get('tableau_n')} ({a['code']}) : sources insuffisantes — {a.get('motif')}",
                            style="List Bullet")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d.save(chemin)
    return chemin


def exporter_note_strategique(note: dict, chemin: Path) -> Path:
    d = _doc(note["titre"])
    _note_source(d, f"Établie le {note['date']} ; {note['nb_evolutions']} évolutions retenues ; "
                    f"{note['nb_mots']} mots ; modèle : {note['modele']}")
    _avertissements(d, note)
    if note.get("chiffres_cles"):
        from ..app import identite
        i = identite.charger()
        t = d.add_table(rows=1, cols=1)
        t.style = "Table Grid"
        cel = t.rows[0].cells[0]
        titre = cel.paragraphs[0].add_run("Chiffres clés")
        titre.bold, titre.font.color.rgb = True, _rgb(i["couleurs"]["vert"])
        for b in note["chiffres_cles"]:
            cel.add_paragraph(b["texte"], style="List Bullet")
        d.add_paragraph()
    for r in RUBRIQUES:
        d.add_heading(r, level=1)
        for b in note["rubriques"][r]:
            d.add_paragraph(b["texte"], style="List Bullet" if r != "Évolutions marquantes" else None)
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("Chaque valeur est tracée jusqu'au tableau et à la page (voir le fichier de traçabilité).")
    r.italic, r.font.size = True, Pt(8)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d.save(chemin)
    return chemin
