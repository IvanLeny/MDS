"""Export Word des productions (python-docx) : commentaire, note d'analyse,
note stratégique. Sous chaque énoncé : ses sources ; en fin de document : les
valeurs écartées et les abstentions."""
from __future__ import annotations

from pathlib import Path
from typing import List

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

GRIS = RGBColor(0x59, 0x59, 0x59)
ROUGE = RGBColor(0xA0, 0x1C, 0x1C)


def _doc(titre: str, sous_titre: str = "") -> Document:
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    en = d.add_paragraph("MINPMEESA — Cellule des Statistiques")
    en.runs[0].font.size, en.runs[0].font.color.rgb = Pt(9), GRIS
    d.add_heading(titre, level=0)
    if sous_titre:
        p = d.add_paragraph(sous_titre)
        p.runs[0].italic = True
    return d


def _mention(d: Document, texte: str, couleur=ROUGE) -> None:
    p = d.add_paragraph()
    r = p.add_run(texte)
    r.bold, r.font.color.rgb, r.font.size = True, couleur, Pt(9.5)


def _source(d: Document, texte: str) -> None:
    p = d.add_paragraph()
    p.paragraph_format.left_indent = Pt(18)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(texte)
    r.font.size, r.font.color.rgb, r.italic = Pt(8.5), GRIS, True


def libelle_source(s: dict) -> str:
    if s.get("genre") == "variation":
        return (f"variation calculée par le programme — {s.get('doc_id', '')}, tableau {s.get('tableau_n')}, "
                f"p. {s.get('page')} (valeurs n° {s.get('valeur_id')} et {s.get('valeur_ref_id')})")
    return (f"{s.get('doc_id', '')}, tableau {s.get('tableau_n')}, p. {s.get('page')} — "
            f"{s.get('ligne', '')} | {s.get('colonne', '')} (valeur n° {s.get('valeur_id')})")


def _enonces(d: Document, enonces: List[dict]) -> None:
    for e in enonces:
        p = d.add_paragraph(style="List Bullet")
        if e.get("type") == "perspective":
            p.add_run("Perspective : ").italic = True
        p.add_run(e["texte"])
        for v in e.get("valeurs", []):
            _source(d, f"« {v['valeur']} » : {libelle_source(v['source'])}")


def _ecarts(d: Document, ecartees: List[dict], abstentions: List[str]) -> None:
    if ecartees:
        d.add_heading("Valeurs écartées par le contrôle de citation littérale", level=2)
        for e in ecartees:
            _source(d, f"« {e['valeur']} » ({e['action']}) — énoncé d'origine : {e['enonce_original']}")
    if abstentions:
        d.add_heading("Abstentions", level=2)
        for a in abstentions:
            d.add_paragraph(a, style="List Bullet")


def exporter_commentaire(c, chemin: Path) -> Path:
    d = _doc(f"Commentaire — {c.intitule}", f"Exercice {c.exercice} · indicateur {c.code} · mode : {c.mode}")
    if "extractif" in c.mode:
        _mention(d, "Mode extractif (sans modèle de langage) : énoncés composés par gabarits déterministes.")
    if c.abstention:
        _mention(d, "Sources insuffisantes, à commenter manuellement. Motif : " + c.abstention)
    _enonces(d, c.enonces)
    if c.modeles:
        d.add_heading("Modèles de rédaction utilisés (exercices antérieurs)", level=2)
        for m in c.modeles:
            _source(d, f"{m['doc_id']}, p. {m['page']} (exercice {m['exercice']})")
    _ecarts(d, c.ecartees, [c.abstention] if c.abstention else [])
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d.save(chemin)
    return chemin


def exporter_note_analyse(n, chemin: Path) -> Path:
    d = _doc(n.titre, f"Périmètre : {n.perimetre} · mode : {n.mode}")
    for a in n.avertissements:
        _mention(d, a)
    chap, sec = None, None
    for b in n.blocs:
        if b.intertitre != chap:
            if b.transition:
                d.add_paragraph(b.transition).runs[0].italic = True
            d.add_heading(b.intertitre.title() if b.intertitre.isupper() else b.intertitre, level=1)
            chap = b.intertitre
        d.add_heading(b.intitule, level=2)
        if not b.valide:
            _mention(d, "Commentaire généré, non validé par un cadre.", GRIS)
        if b.abstention:
            _mention(d, f"Sources insuffisantes, à commenter manuellement ({b.abstention}).")
        _enonces(d, b.enonces)
        _source(d, f"Tableau {b.tableau_n} de l'Annuaire, p. {b.page_tableau}")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d.save(chemin)
    return chemin


def exporter_note_strategique(n, chemin: Path) -> Path:
    d = _doc(f"Note d'analyse stratégique — exercice {n.exercice}", f"Mode : {n.mode}")
    for a in n.avertissements:
        _mention(d, a)
    d.add_heading("Messages clés", level=1)
    _enonces(d, n.messages)
    d.add_heading("Évolutions marquantes", level=1)
    for e in n.evolutions:
        p = d.add_paragraph(style="List Bullet")
        p.add_run(e["texte"])
        if e.get("objectif_bn3"):
            o = e["objectif_bn3"]
            _source(d, f"Objectif documenté : « {o['texte'][:300]} » — {o['titre']}, p. {o['page']}")
        _source(d, f"Source : {e['commentaire']} ; {e['doc_annuaire']}, tableau {e['tableau_n']}, p. {e['page']} "
                   f"(valeurs n° {e['valeur_id']} et {e['valeur_ref_id']}) ; score BN1 = {e['score_bn1']}")
    d.add_heading("Points d'attention", level=1)
    for a in n.points_attention or ["Aucun recul marqué parmi les évolutions retenues."]:
        d.add_paragraph(a, style="List Bullet")
    d.add_heading("Pistes pour la décision", level=1)
    for p_ in n.pistes:
        d.add_paragraph(p_, style="List Bullet")
    d.add_heading("Sources", level=1)
    for s in n.sources:
        d.add_paragraph(s, style="List Bullet")
    _ecarts(d, n.ecartees, [])
    p = d.add_paragraph(f"Vérifications automatiques : BN4 (toute valeur tracée) = {'oui' if n.verif_bn4 else 'non'} ; "
                        f"BN5 (≤ 2 pages, {n.nb_mots} mots) = {'oui' if n.verif_bn5 else 'non'}.")
    p.runs[0].font.size, p.runs[0].font.color.rgb = Pt(8.5), GRIS
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d.save(chemin)
    return chemin
