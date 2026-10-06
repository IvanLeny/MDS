"""Interface locale (section 3.4.1) : 4 parcours + page « Base documentaire ».

Lancement : double-clic sur demarrer.bat (Windows) ou ./demarrer.sh
            (= streamlit run minpmeesa/app/streamlit_app.py)
"""
from __future__ import annotations

import re
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
from minpmeesa.app import identite  # noqa: E402
from minpmeesa.store import db  # noqa: E402

ID = identite.charger()
_LOGO = identite.logo(ID)
st.set_page_config(page_title=f"{ID['nom']} — MINPMEESA", page_icon=str(_LOGO) if _LOGO else None, layout="wide")
st.markdown(identite.css(ID), unsafe_allow_html=True)
st.markdown(identite.bandeau(ID), unsafe_allow_html=True)
if _LOGO:
    st.logo(str(_LOGO), size="large")


@st.cache_resource
def moteur() -> Moteur:
    return Moteur()


@st.cache_resource
def client_llm(choix: str):
    c = config.charger()
    return obtenir(c, choix, delai=c["llm"]["ollama"].get("delai_interface_s"))


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
    if res.get("repli_gabarits"):
        st.info(f"Rédaction du modèle **{res.get('modele')}** non retenue ({res['repli_gabarits']}) : "
                "commentaire rédigé par les **gabarits**, à partir des chiffres de l'Annuaire.")
    for e in res["enonces"]:
        st.markdown(identite.enonce(e.get("type", "constat"), e["texte"],
                                    [r["libelle"] for r in e.get("references", [])]), unsafe_allow_html=True)
    if res.get("valeurs_ecartees"):
        with st.expander(f"Valeurs écartées par le contrôle ({len(res['valeurs_ecartees'])})"):
            st.table(pd.DataFrame(res["valeurs_ecartees"])[["valeur", "type", "action", "texte_original"]])


# ------------------------------------------------------------------ barre latérale
cfg = config.charger()
st.sidebar.markdown(f'<div class="ap-side-titre">{ID["nom"]}</div><div class="ap-side-sous">{ID["structure"]}</div>',
                    unsafe_allow_html=True)
choix_llm = st.sidebar.selectbox("Rédaction", ["ollama", "none", "api"],
                                 format_func=lambda x: {"ollama": "Modèle de langage local (Ollama)",
                                                        "none": "Sans modèle de langage (gabarits)",
                                                        "api": "Service distant — développement seulement"}[x])
client, explication = client_llm(choix_llm)
st.sidebar.markdown(f'<div class="ap-etat"><b>Moteur de rédaction</b><br>{explication}</div>',
                    unsafe_allow_html=True)
page = st.sidebar.radio("Page", ["Parcours", "Base documentaire"])

try:
    m = moteur()
except FileNotFoundError:
    st.error("La base n'est pas encore construite. Page « Base documentaire » → « Reconstruire la base ».")
    m = None
    page = "Base documentaire"

if page == "Parcours" and m:
    con = m.con
    t1, t2, t3, t4 = st.tabs(["Consulter", "Commenter un indicateur", "Note d'analyse", "Note stratégique"])

    with t1:
        st.markdown(identite.entete_service(
            1, "Poser une question aux publications",
            "Recherche dans les Annuaires, rapports et notes publiés : chaque extrait renvoie à son document et à sa "
            "page ; sans source suffisante, l'outil s'abstient."), unsafe_allow_html=True)
        if "q_suggeree" in st.session_state:
            st.session_state["q"] = st.session_state.pop("q_suggeree")
        q = st.text_input("Votre question", key="q",
                          placeholder="Ex. : Combien de PME ont été créées dans les CFCE en 2024 ?")
        rep = st.checkbox("Ajouter une réponse rédigée courte (facultatif)")
        if q:
            r = consultation.consulter(q, m, rediger=rep, client=client)
            if r.get("reponse") and r["reponse"].get("texte"):
                st.success(r["reponse"]["texte"])
                st.caption(f"Réponse rédigée ({r['reponse'].get('redaction')}), chiffres contrôlés contre les extraits.")
            if r["abstention"]:
                st.warning(r["message"] + " La question est peut-être trop générale ou formulée avec d'autres "
                           "mots que ceux des publications.")
                if r.get("suggestions"):
                    st.markdown("**Essayez plutôt, avec les intitulés de l'Annuaire :**")
                    for i, s_ in enumerate(r["suggestions"]):
                        if st.button(s_, key=f"sugg{i}"):
                            st.session_state["q_suggeree"] = s_
                            st.rerun()
            for i, p in enumerate(r["passages"], 1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {p['titre']}** — page {p['page']}")
                    st.write(p["extrait"])
                    if st.toggle("Ouvrir la page", key=f"pg{i}"):
                        st.image(page_pdf(p["fichier"], p["page"]))
            st.caption(f"Temps de réponse : {r['duree_s']} s — encodeur : {r['encodeur']}")

    with t2:
        st.markdown(identite.entete_service(
            2, "Commenter un indicateur",
            "Commentaire d'un graphique du rapport d'analyse à partir du tableau apparié de l'Annuaire et des "
            "variations calculées par le programme ; chaque chiffre est contrôlé."), unsafe_allow_html=True)
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
        st.markdown(identite.entete_service(
            3, "Note d'analyse d'un Annuaire statistique",
            "Choisissez un Annuaire, puis l'Annuaire entier ou certains chapitres : chaque tableau apparié est commenté."),
            unsafe_allow_html=True)
        annuaires = [dict(r) for r in con.execute(
            "SELECT doc_id, titre, exercice FROM documents WHERE type='annuaire' AND statut_diffusion='publie' "
            "ORDER BY exercice DESC")]
        ann = st.selectbox("Annuaire statistique", annuaires,
                           format_func=lambda a: f"{a['titre']} (exercice {a['exercice']})", key="ann3")
        etendue = st.radio("Étendue", ["Tout l'Annuaire", "Chapitres choisis"], horizontal=True, key="et3")
        choix = []
        if etendue == "Chapitres choisis":
            chapitres = list(dict.fromkeys(r[0] for r in con.execute(
                "SELECT chapitre FROM passages WHERE doc_id=? AND nature='tableau' AND chapitre LIKE 'CHAPITRE%' "
                "ORDER BY page", (ann["doc_id"],))))
            choix = st.multiselect("Chapitres de cet Annuaire", chapitres, key="ch3")
        if client is not None and etendue == "Tout l'Annuaire":
            st.caption("Avec un modèle de langage, la rédaction d'un Annuaire entier peut prendre longtemps.")
        if st.button("Rédiger la note d'analyse", type="primary", disabled=etendue == "Chapitres choisis" and not choix):
            titre = f"Note d'analyse — {ann['titre']}"
            with st.spinner("Rédaction des commentaires de l'Annuaire…"):
                if etendue == "Tout l'Annuaire":
                    st.session_state["na"] = analysis_note.rediger(con, ann["exercice"], documents=[ann["doc_id"]],
                                                                   client=client, moteur=m, titre=titre)
                else:
                    motif = "|".join(re.escape(c) for c in choix)
                    st.session_state["na"] = analysis_note.rediger(con, ann["exercice"], chapitre=f"^({motif})$",
                                                                   client=client, moteur=m,
                                                                   titre=f"{titre} — {len(choix)} chapitre(s)")
        na = st.session_state.get("na")
        if na:
            st.markdown(f"#### {na['titre']}")
            st.caption(f"{len(na['sections'])} tableau(x) commenté(s) ; {len(na['abstentions'])} à commenter manuellement.")
            avertissements(na)
            for s in na["sections"]:
                st.markdown(f"#### Tableau {s['tableau_n']} : {s['intitule']}")
                afficher_commentaire(s["commentaire"])
            if na["abstentions"]:
                st.warning("À commenter manuellement : " + ", ".join(f"tableau {a['tableau_n']}" for a in na["abstentions"]))
            bouton_word("Exporter en Word", docx_export.exporter_note_analyse, na, f"note_analyse_{na['exercice']}.docx")

    with t4:
        st.markdown(identite.entete_service(
            4, "Note d'analyse stratégique",
            "Une à deux pages pour les décideurs : chiffres clés, messages, évolutions marquantes et pistes, tous tracés "
            "jusqu'à la page de l'Annuaire."), unsafe_allow_html=True)
        ex4 = st.selectbox("Exercice", exercices, key="ex4")
        if st.button("Rédiger la note stratégique", type="primary"):
            st.session_state["ns"] = strategic_note.rediger(con, ex4, client, m)
        ns = st.session_state.get("ns")
        if ns:
            avertissements(ns)
            if ns.get("chiffres_cles"):
                st.markdown("### Chiffres clés")
                cols = st.columns(min(3, len(ns["chiffres_cles"])))
                for i, b in enumerate(ns["chiffres_cles"]):
                    nom, _, reste = b["texte"].partition(" : ")
                    valeur, _, evo = reste.rstrip(".").partition(" (")
                    mu = re.match(r"([\d\s  ,.]+?)\s+([^\d].*)$", valeur)   # « 7 291 millions de … » -> unité au libellé
                    if mu:
                        valeur, nom = mu.group(1), f"{nom} ({mu.group(2)})"
                    cols[i % len(cols)].metric(nom, valeur, evo.rstrip(")").replace("−", "-") or None)
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
    st.markdown(identite.entete_service(
        5, "Base documentaire",
        "Ajouter une publication, reconstruire la base et explorer son contenu (documents, passages, valeurs, "
        "variations)."), unsafe_allow_html=True)
    st.caption(f"Base SQLite : `{db.chemin_base()}` · index vectoriel FAISS : `{config.chemin('base') / 'dense.faiss'}`")

    def reconstruire():
        from minpmeesa.ingestion.build import construire
        with st.spinner("Intégration dans la base : extraction, découpage, valeurs, variations, index (quelques minutes)…"):
            r = construire(verbeux=False)
        st.cache_resource.clear()
        st.success(f"Base à jour : {r['nb_documents']} documents, {r['nb_passages']} passages, "
                   f"{r['nb_valeurs']} valeurs, {r['nb_variations']} variations.")
        for a_ in r["avertissements"]:
            st.caption(a_)

    with st.form("ajout"):
        st.markdown("**Ajouter un PDF à la base**")
        f = st.file_uploader("Fichier PDF", type="pdf")
        c1, c2, c3 = st.columns(3)
        titre = c1.text_input("Titre")
        type_ = c2.selectbox("Type", ["annuaire", "rapport_analyse", "note_conjoncture", "contexte"])
        exercice = c3.number_input("Exercice", 2010, 2035, 2025)
        trimestre = c1.selectbox("Trimestre", ["", "T1", "T2", "T3", "T4"])
        statut = c2.selectbox("Statut de diffusion", ["publie", "interne"])
        integrer = c3.checkbox("Intégrer tout de suite dans la base", value=True)
        if st.form_submit_button("Ajouter") and f and titre:
            import yaml
            dest = config.chemin("corpus") / Path(f.name).name
            reg = yaml.safe_load(config.chemin("registre").read_text(encoding="utf-8"))
            reg["documents"] = [d for d in reg["documents"] if d["doc_id"] != dest.stem]   # remplacement éventuel
            dest.write_bytes(f.getvalue())
            reg["documents"].append({"doc_id": dest.stem, "fichier": dest.name, "titre": titre, "type": type_,
                                     "exercice": int(exercice), "trimestre": trimestre or None,
                                     "statut_diffusion": statut})
            config.chemin("registre").write_text(yaml.safe_dump(reg, allow_unicode=True, sort_keys=False),
                                                 encoding="utf-8")
            st.success(f"{dest.name} copié dans le corpus et inscrit au registre.")
            if integrer:
                reconstruire()
                m = moteur()
            else:
                st.info("Le document sera intégré à la prochaine reconstruction de la base.")
    if st.button("Reconstruire la base"):
        reconstruire()
        m = moteur()

    if m:
        con = m.con
        st.markdown("### Explorer la base")
        n = lambda t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        k = st.columns(6)
        for col, (lib, t) in zip(k, [("Documents", "documents"), ("Passages", "passages"), ("Valeurs", "valeurs"),
                                     ("Variations", "variations"), ("Appariements", "appariement"),
                                     ("Productions", "productions")]):
            col.metric(lib, f"{n(t):,}".replace(",", " "))
        st.caption(f"Index vectoriel FAISS : {m.dense.ntotal:,} vecteurs".replace(",", " ")
                   + f" · encodeur : {m.nom_encodeur}")
        o1, o2, o3, o4, o5, o6 = st.tabs(["Documents", "Passages", "Valeurs", "Variations", "Appariements",
                                          "Journal des productions"])
        with o1:
            docs = pd.read_sql_query(
                "SELECT d.doc_id, d.titre, d.type, d.exercice, d.trimestre, d.statut_diffusion, d.nb_pages, "
                "(SELECT COUNT(*) FROM passages p WHERE p.doc_id=d.doc_id) AS passages, "
                "(SELECT COUNT(*) FROM valeurs v WHERE v.doc_id=d.doc_id) AS valeurs, d.fichier "
                "FROM documents d ORDER BY d.type, d.exercice", con)
            st.dataframe(docs, hide_index=True, width='stretch')
        ids = [r[0] for r in con.execute("SELECT doc_id FROM documents ORDER BY type, exercice")]
        with o2:
            c1, c2 = st.columns([1, 2])
            dsel = c1.selectbox("Document", ids, key="exp_doc")
            mot = c2.text_input("Rechercher dans le texte", key="exp_mot")
            q = ("SELECT passage_id, page, nature, chapitre, section, numero, substr(texte, 1, 300) AS extrait "
                 "FROM passages WHERE doc_id=?")
            args = [dsel]
            if mot:
                q += " AND texte LIKE ?"
                args.append(f"%{mot}%")
            st.dataframe(pd.read_sql_query(q + " ORDER BY page, passage_id LIMIT 500", con, params=args),
                         hide_index=True, width='stretch')
        with o3:
            c1, c2 = st.columns(2)
            dv = c1.selectbox("Document", ids, key="exp_doc_v")
            tabs_ = [r[0] for r in con.execute("SELECT DISTINCT tableau_n FROM valeurs WHERE doc_id=? "
                                               "ORDER BY tableau_n", (dv,))]
            tn = c2.selectbox("Tableau", tabs_, key="exp_tab") if tabs_ else None
            if tn is not None:
                st.dataframe(pd.read_sql_query(
                    "SELECT valeur_id, page, tableau_intitule, ligne, colonne, valeur_texte, unite FROM valeurs "
                    "WHERE doc_id=? AND tableau_n=? ORDER BY valeur_id", con, params=[dv, tn]),
                    hide_index=True, width='stretch')
        with o4:
            codes = [r[0] for r in con.execute("SELECT DISTINCT code_indicateur FROM variations ORDER BY 1")]
            cv = st.selectbox("Indicateur", codes, key="exp_var")
            st.dataframe(pd.read_sql_query(
                "SELECT exercice, exercice_ref, ligne, sous_colonne, valeur, valeur_ref, var_abs_texte, "
                "var_rel_texte, valeur_id, valeur_ref_id FROM variations WHERE code_indicateur=? "
                "ORDER BY exercice DESC, exercice_ref DESC", con, params=[cv]), hide_index=True, width='stretch')
        with o5:
            st.dataframe(pd.read_sql_query(
                "SELECT exercice, code_indicateur, graphique_n, graphique_intitule, tableau_n, tableau_intitule, "
                "score, statut FROM appariement ORDER BY exercice DESC, graphique_n", con),
                hide_index=True, width='stretch')
        with o6:
            cols = [r[1] for r in con.execute("PRAGMA table_info(productions)")]
            garder = [c for c in ("prod_id", "type", "horodatage", "modele", "statut_validation", "valide_par", "duree_s")
                      if c in cols]
            st.dataframe(pd.read_sql_query(f"SELECT {', '.join(garder)} FROM productions ORDER BY 1 DESC LIMIT 300",
                                           con), hide_index=True, width='stretch')

st.markdown(identite.pied(ID), unsafe_allow_html=True)
