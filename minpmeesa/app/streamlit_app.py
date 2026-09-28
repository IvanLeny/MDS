"""Interface locale (section 3.4.1) : 4 parcours + page « Base documentaire ».

Lancement : double-clic sur demarrer.bat (Windows) ou ./demarrer.sh
            (= streamlit run minpmeesa/app/streamlit_app.py)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402
import pymupdf  # noqa: E402
import streamlit as st  # noqa: E402

from minpmeesa import config  # noqa: E402
from minpmeesa.export import docx_export  # noqa: E402
from minpmeesa.generation import analysis_note, commentary, strategic_note  # noqa: E402
from minpmeesa.generation.llm import obtenir  # noqa: E402
from minpmeesa.retrieval import consultation  # noqa: E402
from minpmeesa.retrieval.hybrid import Moteur  # noqa: E402
from minpmeesa.store import db  # noqa: E402

st.set_page_config(page_title="Aide à la décision — MINPMEESA", page_icon="📊", layout="wide")


@st.cache_resource
def moteur() -> Moteur:
    return Moteur()


@st.cache_resource
def client_llm(choix: str):
    return obtenir(config.charger(), choix)


def page_pdf(fichier: str, page: int) -> bytes:
    d = pymupdf.open(str(config.chemin("corpus") / fichier))
    return d[page - 1].get_pixmap(dpi=110).tobytes("png")


def avertissements(o: dict):
    if o.get("mode_extractif"):
        st.info("Texte produit **sans modèle de langage** (gabarits à partir des chiffres de l'Annuaire).")
    if o.get("provisoire"):
        st.warning("**Provisoire** : le lien entre l'indicateur et le tableau n'a pas encore été validé.")
    if o.get("commentaires_non_valides"):
        st.warning(f"{len(o['commentaires_non_valides'])} commentaire(s) non encore validé(s) : à relire.")


def bouton_word(label: str, fonction, objet: dict, nom: str):
    with tempfile.TemporaryDirectory() as t:
        p = fonction(objet, Path(t) / nom)
        st.download_button(label, p.read_bytes(), file_name=nom,
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def afficher_commentaire(res: dict):
    if res.get("abstention"):
        st.error(f"**{res.get('mention')}** — {res.get('motif')}")
        return
    for e in res["enonces"]:
        icone = "🔎" if e.get("type") == "constat" else "➡️"
        st.markdown(f"{icone} {e['texte']}")
        refs = [r["libelle"] for r in e.get("references", [])]
        if refs:
            st.caption("Sources : " + " ; ".join(refs))
    if res.get("valeurs_ecartees"):
        with st.expander(f"Valeurs écartées par le contrôle ({len(res['valeurs_ecartees'])})"):
            st.table(pd.DataFrame(res["valeurs_ecartees"])[["valeur", "type", "action", "texte_original"]])


# ------------------------------------------------------------------ barre latérale
cfg = config.charger()
st.sidebar.title("📊 Aide à la décision")
st.sidebar.caption("Publications statistiques du MINPMEESA")
choix_llm = st.sidebar.selectbox("Rédaction", ["ollama", "none", "api"],
                                 format_func=lambda x: {"ollama": "Modèle de langage local (Ollama)",
                                                        "none": "Sans modèle de langage (gabarits)",
                                                        "api": "Service distant — développement seulement"}[x])
client, explication = client_llm(choix_llm)
st.sidebar.caption(f"Moteur de rédaction : {explication}")
page = st.sidebar.radio("Page", ["Parcours", "Base documentaire"])

try:
    m = moteur()
except FileNotFoundError:
    st.error("La base n'est pas encore construite. Page « Base documentaire » → « Reconstruire la base ».")
    m = None
    page = "Base documentaire"

if page == "Parcours" and m:
    con = m.con
    t1, t2, t3, t4 = st.tabs(["🔍 Consulter", "✍️ Commenter un indicateur", "📄 Note d'analyse", "🎯 Note stratégique"])

    with t1:
        st.subheader("Poser une question aux publications")
        q = st.text_input("Votre question", placeholder="Ex. : Combien de PME ont été créées dans les CFCE en 2024 ?")
        if q:
            r = consultation.consulter(q, m)
            if r["abstention"]:
                st.warning(r["message"])
            for i, p in enumerate(r["passages"], 1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {p['titre']}** — page {p['page']}")
                    st.write(p["extrait"])
                    if st.toggle("Ouvrir la page", key=f"pg{i}"):
                        st.image(page_pdf(p["fichier"], p["page"]))
            st.caption(f"Temps de réponse : {r['duree_s']} s — encodeur : {r['encodeur']}")

    with t2:
        st.subheader("Commenter un indicateur")
        exercices = [r[0] for r in con.execute("SELECT DISTINCT exercice FROM appariement ORDER BY exercice DESC")]
        ex = st.selectbox("Exercice", exercices, key="ex2")
        inds = con.execute("SELECT code_indicateur, graphique_intitule, statut FROM appariement WHERE exercice=? "
                           "AND statut IN ('valide','candidat') ORDER BY graphique_n", (ex,)).fetchall()
        code = st.selectbox("Indicateur", [i[0] for i in inds],
                            format_func=lambda c: next(f"{i[1]}" + (" (à valider)" if i[2] != "valide" else "")
                                                       for i in inds if i[0] == c))
        if st.button("Rédiger le commentaire", type="primary"):
            st.session_state["com"] = commentary.commenter(con, code, ex, client, moteur=m)
        res = st.session_state.get("com")
        if res and res["code_indicateur"] == code:
            avertissements(res)
            afficher_commentaire(res)
            c1, c2 = st.columns(2)
            with c1:
                if not res.get("abstention"):
                    bouton_word("Exporter en Word", docx_export.exporter_commentaire, res, f"commentaire_{code}.docx")
            with c2:
                if res.get("prod_id") and st.button("Valider ce commentaire"):
                    analysis_note.valider_production(con, res["prod_id"], "cellule")
                    st.success("Commentaire validé : il sera repris dans les notes.")

    with t3:
        st.subheader("Note d'analyse")
        ex3 = st.selectbox("Exercice", [r[0] for r in con.execute(
            "SELECT DISTINCT exercice FROM documents WHERE type='annuaire' ORDER BY exercice DESC")], key="ex3")
        chapitres = [r[0] for r in con.execute(
            "SELECT DISTINCT p.chapitre FROM passages p JOIN documents d USING(doc_id) WHERE d.type='annuaire' "
            "AND d.exercice=? AND p.nature='tableau' AND p.chapitre LIKE 'CHAPITRE%'", (ex3,))]
        chap = st.selectbox("Chapitre de l'Annuaire", chapitres)
        if st.button("Assembler la note", type="primary"):
            import re
            st.session_state["na"] = analysis_note.rediger(con, ex3, chapitre=re.escape(chap), client=client, moteur=m)
        na = st.session_state.get("na")
        if na:
            avertissements(na)
            for s in na["sections"]:
                st.markdown(f"#### Tableau {s['tableau_n']} : {s['intitule']}")
                afficher_commentaire(s["commentaire"])
            if na["abstentions"]:
                st.warning("À commenter manuellement : " + ", ".join(f"tableau {a['tableau_n']}" for a in na["abstentions"]))
            bouton_word("Exporter en Word", docx_export.exporter_note_analyse, na, f"note_analyse_{ex3}.docx")

    with t4:
        st.subheader("Note d'analyse stratégique")
        ex4 = st.selectbox("Exercice", exercices, key="ex4")
        if st.button("Rédiger la note stratégique", type="primary"):
            st.session_state["ns"] = strategic_note.rediger(con, ex4, client, m)
        ns = st.session_state.get("ns")
        if ns:
            avertissements(ns)
            for r in strategic_note.RUBRIQUES:
                st.markdown(f"### {r}")
                for b in ns["rubriques"][r]:
                    st.markdown(f"- {b['texte']}")
            v = strategic_note.verifier_bn4_bn5(ns)
            st.caption(f"{ns['nb_mots']} mots ; toute valeur tracée : {'oui' if v['BN4_toute_valeur_tracee'] else 'non'}")
            with st.expander("Traçabilité (énoncé → valeur → tableau → page)"):
                st.dataframe(pd.DataFrame(ns["tracabilite"]))
            bouton_word("Exporter en Word", docx_export.exporter_note_strategique, ns, f"note_strategique_{ex4}.docx")

if page == "Base documentaire":
    st.subheader("Base documentaire")
    if m:
        docs = pd.DataFrame([dict(r) for r in db.documents(m.con)])
        st.dataframe(docs[["titre", "type", "exercice", "trimestre", "statut_diffusion", "nb_pages", "fichier"]],
                     hide_index=True)
    with st.form("ajout"):
        st.markdown("**Ajouter un PDF** (il sera inscrit au registre, puis pris en compte à la reconstruction)")
        f = st.file_uploader("Fichier PDF", type="pdf")
        c1, c2, c3 = st.columns(3)
        titre = c1.text_input("Titre")
        type_ = c2.selectbox("Type", ["annuaire", "rapport_analyse", "note_conjoncture", "contexte"])
        exercice = c3.number_input("Exercice", 2010, 2035, 2025)
        trimestre = c1.selectbox("Trimestre", ["", "T1", "T2", "T3", "T4"])
        statut = c2.selectbox("Statut de diffusion", ["publie", "interne"])
        if st.form_submit_button("Ajouter") and f and titre:
            import yaml
            dest = config.chemin("corpus") / Path(f.name).name
            dest.write_bytes(f.getvalue())
            reg = yaml.safe_load(config.chemin("registre").read_text(encoding="utf-8"))
            reg["documents"].append({"doc_id": dest.stem, "fichier": dest.name, "titre": titre, "type": type_,
                                     "exercice": int(exercice), "trimestre": trimestre or None,
                                     "statut_diffusion": statut})
            config.chemin("registre").write_text(yaml.safe_dump(reg, allow_unicode=True, sort_keys=False),
                                                 encoding="utf-8")
            st.success(f"{dest.name} ajouté au registre. Lancez la reconstruction.")
    if st.button("Reconstruire la base"):
        from minpmeesa.ingestion.build import construire
        with st.spinner("Reconstruction en cours (quelques minutes)…"):
            r = construire(verbeux=False)
        st.cache_resource.clear()
        st.success(f"Base reconstruite : {r['nb_documents']} documents, {r['nb_passages']} passages.")
        for a in r["avertissements"]:
            st.caption("⚠ " + a)
