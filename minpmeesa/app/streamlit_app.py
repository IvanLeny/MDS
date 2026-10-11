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
from minpmeesa.compute import series  # noqa: E402
from minpmeesa.guards import provenance  # noqa: E402
from minpmeesa.ingestion import pairing  # noqa: E402
from minpmeesa.texte import ensemble  # noqa: E402
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


@st.cache_resource(ttl=60)              # Ollama lancé après coup : pris en compte en une minute
def client_llm(choix: str):
    c = config.charger()
    return obtenir(c, choix, delai=c["llm"]["ollama"].get("delai_interface_s"))


def page_pdf(fichier: str, page: int) -> bytes:
    d = pymupdf.open(str(config.chemin("corpus") / fichier))
    return d[page - 1].get_pixmap(dpi=110).tobytes("png")


@st.cache_data(show_spinner="Lecture des chiffres de l'Annuaire…")
def tableau_de_bord(exercice: int) -> list[dict]:
    """Chiffres clés de l'exercice (gabarits : instantané, entièrement sourcé) et leur série publiée."""
    m_ = moteur()
    codes = [r[0] for r in m_.con.execute(
        "SELECT code_indicateur FROM appariement WHERE exercice=? AND tableau_n IS NOT NULL ORDER BY graphique_n",
        (exercice,))]
    coms = [(c, commentary.commenter(m_.con, c, exercice, None, journaliser=False, moteur=m_)) for c in codes]
    coms = [(c, r) for c, r in coms if not r.get("abstention")]
    out = []
    for code, nv in strategic_note.references_grandeurs(coms).values():
        com = dict(coms)[code]
        src = next((x["libelle"] for e in com["enonces"] if nv["valeur"] in e["texte"]
                    for x in e.get("references", []) if x["valeur"] == nv["valeur"]), None)
        _, pts = series.serie_principale(m_.con, code, exercice, series.nombre(nv["valeur"]))
        out.append({**nv, "code": code, "source": src, "serie": pts})
    return out


def surligner(texte: str, question: str) -> str:
    """Extrait avec les mots de la question surlignés (C4) ; texte échappé."""
    from html import escape
    mots = sorted(ensemble(question), key=len, reverse=True)
    t = escape(texte)
    if mots:
        motif = re.compile(r"\b(" + "|".join(re.escape(escape(m)) for m in mots) + r")\w*", re.I)
        t = motif.sub(lambda x: f'<mark class="ap-mark">{x.group(0)}</mark>', t)
    return f'<div class="ap-extrait">{t}</div>'


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
MODES = {"none": "Gabarits (sans modèle de langage)", "ollama": "Modèle de langage local (Ollama)",
         "api": "Service distant (développement)"}
_ollama_pret = client_llm("ollama")[0] is not None
choix_llm = st.sidebar.selectbox("Mode de rédaction", ["none", "ollama", "api"], index=1 if _ollama_pret else 0,
                                 format_func=MODES.get,
                                 help="Gabarits : instantané, chaque phrase est construite à partir des chiffres. "
                                      "Modèle local : texte mieux rédigé, plus lent, toujours contrôlé.")
client, explication = client_llm(choix_llm)
if client is not None:
    etat = f"Rédaction par <b>{client.nom.replace('ollama:', '')}</b>"
elif choix_llm == "none":
    etat = "Rédaction par <b>gabarits</b>, à partir des chiffres de l'Annuaire"
elif choix_llm == "ollama":
    mod = cfg["llm"]["ollama"]["modele"]
    etat = (f"Ollama n'est pas lancé ou le modèle <b>{mod}</b> n'est pas installé : "
            "rédaction par <b>gabarits</b>")
else:
    etat = "Service distant indisponible (clé absente) : rédaction par <b>gabarits</b>"
st.sidebar.markdown(f'<div class="ap-etat">{etat}</div>', unsafe_allow_html=True)
page = st.sidebar.radio("Navigation", ["Accueil", "Services", "Validation", "Base documentaire"])

try:
    m = moteur()
except FileNotFoundError:
    st.error("La base n'est pas encore construite. Page « Base documentaire » → « Reconstruire la base ».")
    m = None
    page = "Base documentaire"

if page == "Accueil" and m:
    con = m.con
    exercices_ = [r[0] for r in con.execute("SELECT DISTINCT exercice FROM appariement ORDER BY exercice DESC")]
    c_t, c_s = st.columns([3, 1])
    with c_s:
        ex0 = st.selectbox("Exercice", exercices_, key="ex0")
    with c_t:
        st.markdown(identite.entete_service(
            0, f"L'exercice {ex0} en chiffres",
            "Grandeurs principales lues dans l'Annuaire statistique, avec leur évolution et leur trajectoire "
            "sur les années publiées. Survolez le point d'interrogation pour voir la source exacte.",
            eyebrow="Tableau de bord"), unsafe_allow_html=True)
    kpis = tableau_de_bord(ex0)
    cols = st.columns(3)
    for i, k in enumerate(kpis):
        lib = k["nom"][:1].upper() + k["nom"][1:] + (f" ({k['unite']})" if k["unite"] else "")
        evo = (f"{'+' if k['sens'] == 'hausse' else '-'}{k['evolution']} %" if k["evolution"] else None)
        cols[i % 3].metric(lib, k["valeur"], evo, border=False, chart_data=[v for _, v in k["serie"]] or None,
                           chart_type="area", help=f"Source : {k['source']}" if k["source"] else None,
                           delta_description=f"par rapport à {k['ref']}" if k["ref"] else None)
    if kpis:
        an = sorted({a for k in kpis for a, _ in k["serie"]})
        st.caption(f"Courbes : valeurs publiées dans l'Annuaire {ex0} pour les années {', '.join(map(str, an))} "
                   "(années non publiées non interpolées). Chiffres provisoires tant que les appariements ne sont "
                   "pas validés par la Cellule.")
    st.markdown('<div class="ap-eyebrow" style="margin-top:22px">Ce que fait l\'outil</div>', unsafe_allow_html=True)
    st.markdown(identite.cartes_services([
        ("Consulter", "Interroger les Annuaires, rapports et notes : extraits sourcés à la page près, "
                      "refus motivé hors du corpus."),
        ("Commenter", "Rédiger le commentaire d'un indicateur : chaque chiffre est contrôlé contre le tableau "
                      "de l'Annuaire."),
        ("Note d'analyse", "Commenter tout un Annuaire, ou les chapitres choisis, et l'exporter en Word."),
        ("Note stratégique", "Une à deux pages pour les décideurs : chiffres clés, messages, pistes, tout tracé."),
    ]), unsafe_allow_html=True)
    n_ = {t: con.execute(f"SELECT COUNT(*) FROM documents WHERE type=? AND statut_diffusion='publie'", (t,)).fetchone()[0]
          for t in ("annuaire", "rapport_analyse", "note_conjoncture", "contexte")}
    st.caption(f"Corpus : {n_['annuaire']} Annuaires, {n_['rapport_analyse']} rapports d'analyse, "
               f"{n_['note_conjoncture']} notes de conjoncture, {n_['contexte']} documents de contexte publiés.")

if page == "Services" and m:
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
                    st.markdown(surligner(p["extrait"], q), unsafe_allow_html=True)
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
            c_txt, c_gr = st.columns([3, 2], gap="large")
            with c_txt:
                afficher_commentaire(res)
            with c_gr:
                ligne_, pts = series.serie_principale(con, code, ex)
                if len(pts) >= 2:
                    st.markdown(f"**{ligne_}** — valeurs publiées")
                    import altair as alt
                    fr = "replace(format(datum.value, ',.0f'), /,/g, ' ')"       # 400 000, pas 400,000
                    df_ = pd.DataFrame({"Année": [str(a) for a, _ in pts], "Valeur": [v for _, v in pts]})
                    st.altair_chart(alt.Chart(df_).mark_bar(color="#00A35C", cornerRadiusTopLeft=4,
                                                            cornerRadiusTopRight=4).encode(
                        x=alt.X("Année:N", axis=alt.Axis(labelAngle=0, title=None)),
                        y=alt.Y("Valeur:Q", axis=alt.Axis(title=None, labelExpr=fr, grid=True)),
                        tooltip=[alt.Tooltip("Année:N"), alt.Tooltip("Valeur:Q", format=",.0f")]
                    ).properties(height=260), width="stretch")
                    st.caption(f"Source : {provenance.nom_document(res.get('doc_annuaire'))}, tableau "
                               f"{res.get('tableau_n')} ; années non publiées non représentées.")
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

if page == "Validation" and m:
    con = m.con
    dossier = config.chemin("appariement")
    st.markdown(identite.entete_service(
        0, "Validation des appariements graphique ↔ tableau",
        "Chaque graphique du rapport d'analyse est relié à un tableau de l'Annuaire. Deux lecteurs de la Cellule "
        "vérifient chaque lien, séparément ; leurs décisions concordantes deviennent le statut « validé » et "
        "l'accord entre eux est mesuré (kappa de Cohen).", eyebrow="Contrôle humain"), unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    lecteur = c1.text_input("Votre nom (lecteur)", key="lecteur", placeholder="Ex. : A. Mbarga")
    exv = c2.selectbox("Exercice", [r[0] for r in con.execute(
        "SELECT DISTINCT exercice FROM appariement ORDER BY exercice DESC")], key="exv")
    lignes_v = pairing.lire_csv(dossier / f"appariement_{exv}.csv")
    lus = {int(r["graphique_n"]): r for r in pairing.lectures(dossier, exv)
           if lecteur and r["lecteur"].strip().lower() == lecteur.strip().lower()}
    nb_lect = {}
    for r in pairing.lectures(dossier, exv):
        nb_lect.setdefault(int(r["graphique_n"]), set()).add(r["lecteur"].strip().lower())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Appariements", len(lignes_v))
    k2.metric("Lus par vous", len(lus) if lecteur else "—")
    k3.metric("En double lecture", sum(len(v) >= 2 for v in nb_lect.values()))
    k4.metric("Validés", sum(r["statut"] == "valide" for r in lignes_v))
    if not lecteur:
        st.info("Indiquez votre nom pour commencer la lecture.")
    else:
        restants = [r for r in lignes_v if int(r["graphique_n"]) not in lus and r["statut"] not in ("valide", "rejete")]
        if not restants:
            st.success("Vous avez lu tous les appariements de cet exercice.")
        else:
            r = restants[0]
            g = int(r["graphique_n"])
            st.markdown(f"**Appariement {len(lus) + 1} sur {len(lus) + len(restants)}** — score de l'algorithme : "
                        f"{float(r['score']):.2f}")
            a, b = st.columns(2, gap="large")
            with a, st.container(border=True):
                st.markdown(f'<div class="ap-eyebrow">Graphique {g} — '
                            f'{provenance.nom_document(r["doc_rapport"])}</div>', unsafe_allow_html=True)
                st.markdown(f"**{r['graphique_intitule']}**")
                pg = con.execute("SELECT page FROM passages WHERE doc_id=? AND nature='graphique' AND numero=?",
                                 (r["doc_rapport"], g)).fetchone()
                if pg and st.toggle(f"Voir la page {pg[0]}", key=f"vg{exv}{g}"):
                    st.image(page_pdf(f"{r['doc_rapport']}.pdf", pg[0]))
            with b, st.container(border=True):
                st.markdown(f'<div class="ap-eyebrow">Tableau {r["tableau_n"] or "—"} — '
                            f'{provenance.nom_document(r["doc_annuaire"])}</div>', unsafe_allow_html=True)
                st.markdown(f"**{r['tableau_intitule'] or 'aucun tableau proposé'}**")
                pt = con.execute("SELECT MIN(page) FROM valeurs WHERE doc_id=? AND tableau_n=?",
                                 (r["doc_annuaire"], r["tableau_n"] or -1)).fetchone()
                if pt and pt[0] and st.toggle(f"Voir la page {pt[0]}", key=f"vt{exv}{g}"):
                    st.image(page_pdf(f"{r['doc_annuaire']}.pdf", pt[0]))
            with st.form(f"lecture{exv}{g}"):
                dec = st.radio("Votre décision", ["valide", "rejete", "corrige"], horizontal=True,
                               format_func={"valide": "Le lien est juste", "rejete": "Aucun tableau ne correspond",
                                            "corrige": "Un autre tableau correspond"}.get)
                tn = st.number_input("Numéro du bon tableau (si « un autre tableau »)", 1, 200, 1)
                if st.form_submit_button("Enregistrer ma décision", type="primary"):
                    pairing.enregistrer_lecture(dossier, exv, g, lecteur, dec, int(tn) if dec == "corrige" else None)
                    st.rerun()
    st.markdown("#### Consolider")
    st.caption("Applique la règle de double lecture : deux lecteurs d'accord → statut validé (ou rejeté) ; désaccord "
               "→ à vérifier. Les nouveaux statuts s'appliquent aux services après reconstruction de la base.")
    if st.button("Consolider la double lecture"):
        bl = pairing.consolider(dossier, exv)
        st.success(f"{bl['valide']} validé(s), {bl['rejete']} rejeté(s), {bl['a_verifier']} à vérifier ; "
                   f"kappa de Cohen : {bl['kappa_cohen'] if bl['kappa_cohen'] is not None else 'non calculable'} "
                   f"(sur {bl['n_double_lecture']} appariement(s) lus par deux lecteurs).")
    with st.expander("État de tous les appariements"):
        st.dataframe(pd.DataFrame(lignes_v)[["graphique_n", "graphique_intitule", "tableau_n", "tableau_intitule",
                                              "score", "statut", "valide_par"]], hide_index=True, width="stretch")

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
