"""Produit le document Word « Résultats, tableaux et illustrations » destiné à la finalisation du mémoire.

Toutes les valeurs viennent des exécutions déposées dans data/results/ et data/outputs/ (voir
docs/POUR_LE_MEMOIRE.md, qui en indique la source exacte). Aucune valeur n'est calculée ici.

    python scripts/document_resultats.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RACINE = Path(__file__).resolve().parents[1]
R_BGE = RACINE / "data/results/2026-09-30_bge-m3_sans-llm"
R_API = RACINE / "data/results/2026-09-28_api_gpt-oss-20b"
CAPT = RACINE / "data/outputs/captures"
SORTIE = RACINE / "docs/livrables/Resultats_ANALYSPME_pour_memoire.docx"

VERT = RGBColor(0x00, 0x7A, 0x5E)
GRIS = RGBColor(0x5B, 0x67, 0x70)

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2)
    s.top_margin = s.bottom_margin = Cm(2)

n_tab = [0]
n_fig = [0]


def ombrer(cellule, couleur: str) -> None:
    tc = cellule._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), couleur)
    tc.append(sh)


def titre(texte: str, niveau: int = 1) -> None:
    h = doc.add_heading(texte, level=niveau)
    for r in h.runs:
        r.font.color.rgb = VERT


def para(texte: str, gras: bool = False, italique: bool = False, taille: int | None = None,
         couleur: RGBColor | None = None) -> None:
    p = doc.add_paragraph()
    # **gras** en ligne
    for i, morceau in enumerate(texte.split("**")):
        r = p.add_run(morceau)
        r.bold = gras or i % 2 == 1
        r.italic = italique
        if taille:
            r.font.size = Pt(taille)
        if couleur:
            r.font.color.rgb = couleur


def puces(items: list[str]) -> None:
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        for i, morceau in enumerate(it.split("**")):
            p.add_run(morceau).bold = i % 2 == 1


def legende(texte: str, source: str | None = None) -> None:
    p = doc.add_paragraph()
    r = p.add_run(texte)
    r.bold = True
    r.font.size = Pt(10)
    if source:
        r2 = p.add_run(f"  Source : {source}")
        r2.italic = True
        r2.font.size = Pt(9)
        r2.font.color.rgb = GRIS


def tableau(nom: str, entetes: list[str], lignes: list[list[str]], source: str | None = None,
            gras_lignes: set[int] = frozenset()) -> None:
    n_tab[0] += 1
    legende(f"Tableau R{n_tab[0]} — {nom}", source)
    t = doc.add_table(rows=1, cols=len(entetes))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, e in zip(t.rows[0].cells, entetes):
        c.text = ""
        r = c.paragraphs[0].add_run(e)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        ombrer(c, "007A5E")
    for i, l in enumerate(lignes):
        cells = t.add_row().cells
        for c, v in zip(cells, l):
            c.text = ""
            r = c.paragraphs[0].add_run(str(v))
            r.font.size = Pt(9)
            r.bold = i in gras_lignes
            if i % 2 == 1:
                ombrer(c, "F2F7F5")
    doc.add_paragraph()


def figure(chemin: Path, nom: str, source: str, largeur_cm: float = 15.5) -> None:
    if not chemin.is_file():
        print(f"ABSENT : {chemin}", file=sys.stderr)
        return
    n_fig[0] += 1
    doc.add_picture(str(chemin), width=Cm(largeur_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Figure R{n_fig[0]} — {nom}")
    r.bold = True
    r.font.size = Pt(10)
    r2 = p.add_run(f"\nSource : {source}")
    r2.italic = True
    r2.font.size = Pt(9)
    r2.font.color.rgb = GRIS


def texte_propose(texte: str) -> None:
    t = doc.add_table(rows=1, cols=1)
    c = t.rows[0].cells[0]
    ombrer(c, "F2F7F5")
    c.text = ""
    p = c.paragraphs[0]
    r = p.add_run("Texte proposé : ")
    r.bold = True
    r.font.color.rgb = VERT
    r.font.size = Pt(10)
    r2 = p.add_run(texte)
    r2.italic = True
    r2.font.size = Pt(10)
    doc.add_paragraph()


def saut() -> None:
    doc.add_page_break()


# ---------------------------------------------------------------- page de garde
LOGO = RACINE / "assets/logo.png"
if LOGO.is_file():
    doc.add_paragraph()
    doc.add_picture(str(LOGO), width=Cm(3.6))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("ANALYS'PME")
r.bold = True
r.font.size = Pt(30)
r.font.color.rgb = VERT
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Assistant d'analyse des publications statistiques des PMEESA\nMINPMEESA — Cellule des Statistiques")
r.font.size = Pt(13)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("\nRésultats, tableaux, figures et captures\npour la finalisation du mémoire")
r.bold = True
r.font.size = Pt(18)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("\nConception et évaluation d'un système RAG hybride à restitution contrôlée, appliqué aux "
              "publications statistiques du MINPMEESA\n\nIvan Leny — Master 2, ISSEA\nVersion du 06/10/2026")
r.italic = True
r.font.size = Pt(11)
saut()

# ---------------------------------------------------------------- mode d'emploi
titre("Mode d'emploi de ce document")
para("Ce document rassemble **toutes les valeurs mesurées** par le prototype ANALYS'PME, sous forme de "
     "tableaux et de figures prêts à copier dans le mémoire, avec les captures de l'interface. Chaque tableau "
     "et chaque figure indique le fichier dont il provient : rien n'est saisi à la main ni estimé.")
para("Les tableaux sont numérotés R1, R2… (R pour « résultats ») ; renumérotez-les selon le mémoire. Pour chaque "
     "section, le numéro de section ou de tableau du mémoire visé est indiqué dans le titre. Les encadrés "
     "« Texte proposé » peuvent être repris tels quels ou adaptés.")
titre("Sources des résultats", 2)
tableau("Exécutions de référence",
        ["Exécution", "Environnement", "Sert pour"],
        [["data/results/2026-09-30_bge-m3_sans-llm", "Google Colab (CPU), encodeur bge-m3, sans modèle de langage",
          "H1 récupération, abstention, Tableau 3.3"],
         ["data/results/2026-09-30_encodeurs", "Google Colab (CPU), 5 encodeurs", "Tableau 3.3 (comparaison)"],
         ["data/results/2026-09-28_api_gpt-oss-20b", "PC Windows 10, moteur Groq openai/gpt-oss-20b",
          "H1 ancrage, H2, Tableau 3.2, gabarits vs LLM"],
         ["data/results/2026-10-01_apres-plan-AB_sans-llm", "Poste de développement, après les améliorations A et B",
          "Gabarits après amélioration, temps système"],
         ["data/outputs/", "Poste de développement", "Note stratégique 2024, traçabilité, captures"]])
titre("Trois réserves à rappeler au chapitre 4", 2)
puces(["Résultats **provisoires** : les 58 appariements graphique ↔ tableau sont au statut « candidat » (48) ou "
       "« à vérifier » (10) ; aucun n'est encore validé par double lecture.",
       "H1-récupération mesurée avec bge-m3 sur le **jeu de questions qui a aussi servi à choisir l'encodeur** "
       "(biais de sélection) : à confirmer sur les questions des cadres.",
       "Modèle de langage appelé par un **service distant de développement** (Groq, openai/gpt-oss-20b) et non par "
       "Ollama sur le poste cible : mêmes poids ouverts, mais temps de réponse non transposables."])
saut()

# ---------------------------------------------------------------- 1. corpus
titre("1. Corpus et base documentaire (Tableau 2.6, Annexe I)")
corpus = [
    ["Annuaire 2021", "annuaire", "2021", "80", "60", "0", "97"],
    ["Annuaire 2022", "annuaire", "2022", "69", "63", "0", "104"],
    ["Annuaire 2023", "annuaire", "2023", "86", "82", "0", "134"],
    ["Annuaire 2024", "annuaire", "2024", "97", "86", "0", "142"],
    ["Rapport d'analyse 2021", "rapport_analyse", "2021", "25", "2", "10", "29"],
    ["Rapport d'analyse 2022", "rapport_analyse", "2022", "26", "1", "15", "40"],
    ["Rapport d'analyse 2023", "rapport_analyse", "2023", "33", "5", "19", "58"],
    ["Rapport d'analyse 2024", "rapport_analyse", "2024", "42", "1", "15", "51"],
    ["Note de conjoncture T3 2022", "note_conjoncture", "2022", "20", "3", "12", "28"],
    ["Note de conjoncture T4 2023", "note_conjoncture", "2023", "34", "9", "39", "75"],
    ["Note de conjoncture T1 2024", "note_conjoncture", "2024", "15", "1", "11", "21"],
    ["Note de conjoncture T2 2024", "note_conjoncture", "2024", "15", "1", "11", "21"],
    ["Note de conjoncture T3 2024", "note_conjoncture", "2024", "15", "0", "9", "17"],
    ["Note de conjoncture T1 2025", "note_conjoncture", "2025", "21", "1", "12", "25"],
    ["Bulletin loi de finances 2023", "contexte", "2023", "4", "0", "0", "2"],
    ["Bulletin n°4 (crédits, garantie)", "contexte", "2024", "2", "0", "0", "3"],
    ["Note de perspective inflation", "contexte", "2023", "29", "6", "8", "28"],
    ["Note de perspective compétitivité", "contexte", "2024", "48", "0", "3", "28"],
    ["Total (18 publications)", "", "", "661", "", "", "903"],
]
tableau("Corpus documentaire du prototype",
        ["Document", "Type", "Exercice", "Pages", "Tableaux", "Graphiques", "Passages"], corpus,
        "data/corpus/inventaire.csv, data/base/build_rapport.json", gras_lignes={len(corpus) - 1})
tableau("Contenu de la base (SQLite + FAISS)",
        ["Élément", "Nombre", "Remarque"],
        [["Documents", "19", "18 publications + 1 document de test fictif (cloisonnement)"],
         ["Passages indexés", "904", "903 hors document de test ; 8 fragments rejetés (trop courts)"],
         ["Valeurs (cellules de tableaux)", "16 211", "chacune avec document, page, tableau, ligne, colonne"],
         ["Variations calculées", "4 242", "572 avant la correction du 01/10/2026 (colonnes Effectif / %)"],
         ["Appariements graphique ↔ tableau", "58", "48 candidats, 10 à vérifier, 0 validé"],
         ["Vecteurs FAISS", "904", "un par passage (bge-m3 : 1 024 dimensions ; repli : 256)"]],
        "data/base/build_rapport.json")
para("Corpus manquant : notes de conjoncture T1, T2, T3 2023 et T4 2024. Les 18 publications sont au statut "
     "« publie » (à confirmer auprès de la Cellule).")
titre("Table d'appariement (Annexe II)", 2)
tableau("Appariements proposés par exercice",
        ["Exercice", "Lignes proposées"],
        [["2021", "9"], ["2022", "15"], ["2023", "19"], ["2024", "15"], ["Total", "58 (48 candidats, 10 à vérifier)"]],
        "data/pairing/appariement_20XX.csv", gras_lignes={4})
para("Erreur connue corrigée : 2024, graphique 2 → tableau 2 (et non 17). Insérer la table complète après la "
     "double lecture ; le kappa de Cohen sera dans data/pairing/accord_AAAA.json.")
saut()

# ---------------------------------------------------------------- 2. choix des modèles
titre("2. Choix du modèle de langage (section 3.1.4, Tableau 3.2)")
tableau("Comparaison des modèles de langage (20 indicateurs)",
        ["Moteur / modèle", "Déployable", "Temps médian", "JSON valide", "Valeurs écartées"],
        [["ollama / gpt-oss:20b (retenu)", "oui (16 Go RAM)", "non mesuré", "—", "—"],
         ["ollama / llama3.1:8b", "oui", "non mesuré", "—", "—"],
         ["ollama / qwen2.5:7b-instruct", "oui", "non mesuré", "—", "—"],
         ["ollama / mistral:7b-instruct", "oui", "non mesuré", "—", "—"],
         ["ollama / llama3.2:3b", "oui", "non mesuré", "—", "—"],
         ["api Groq / openai/gpt-oss-20b", "non (développement)", "23,2 s (réseau inclus)", "100 %", "1,1 %"],
         ["api Groq / openai/gpt-oss-120b", "non (borne haute)", "26,2 s (réseau inclus)", "100 %", "3,3 %"]],
        "2026-09-28_api_gpt-oss-20b/tableau_3_2_modeles_langage.json", gras_lignes={0, 5})
para("2 appels en échec sur 20 pour le 20b (coupures réseau), 0 pour le 120b. « Valeurs écartées » : part des "
     "valeurs citées par le modèle que le contrôle littéral a retirées. Les lignes Ollama restent à mesurer sur le "
     "poste cible (run_all --llm ollama).")
texte_propose("Le modèle gpt-oss-20b produit toujours un JSON valide et cite moins de valeurs non soutenues que la "
              "borne haute gpt-oss-120b (1,1 % contre 3,3 %) : le modèle plus gros n'apporte rien sur ce critère, ce "
              "qui conforte le choix d'un modèle de 20 milliards de paramètres, déployable sur un poste de 16 Go.")

titre("3. Choix de l'encodeur (section 3.1.5, Tableau 3.3)")
tableau("Comparaison des encodeurs (52 questions, Google Colab CPU)",
        ["Encodeur", "Longueur max.", "Succès@5 hybride", "MRR hybride", "Dense seul (S@5 / MRR)",
         "p (vs repli)", "Indexation"],
        [["BAAI/bge-m3 (retenu)", "8 192", "0,88 (46/52)", "0,694", "0,85 / 0,674", "0,016", "9 090 s (2 h 31)"],
         ["multilingual-e5-large", "512", "0,87 (45/52)", "0,681", "0,85 / 0,619", "0,015", "4 989 s (1 h 23)"],
         ["sentence-camembert-base", "128", "0,71 (37/52)", "0,475", "0,42 / 0,302", "0,109", "448 s"],
         ["MiniLM-L12 (repli léger)", "128", "0,81 (42/52)", "0,512", "0,46 / 0,394", "0,348", "136 s"],
         ["Repli hors ligne TF-IDF + SVD", "sans limite", "0,79 (41/52)", "0,581", "0,75 / 0,559", "—", "29 s"]],
        "data/results/2026-09-30_encodeurs/tableau_3_3_encodeurs.json", gras_lignes={0})
puces(["Les encodeurs conçus pour la **recherche documentaire** (bge-m3, e5) améliorent significativement le repli "
       "(MRR hybride +0,11, p ≈ 0,015) ; les modèles de similarité de phrases (camembert, MiniLM) non.",
       "La **longueur lue** explique une grande part de l'écart : limités à 128 tokens, ces modèles ne voient que le "
       "début des passages, alors que les tableaux linéarisés dépassent souvent 500 tokens.",
       "bge-m3 contre e5-large, question par question : MRR 0,694 contre 0,681, p = 0,73 (12 gagnées, 12 perdues) : "
       "**statistiquement équivalents**. bge-m3 est maintenu par la règle fixée a priori, non par une supériorité "
       "démontrée.",
       "Coût : l'indexation par bge-m3 prend environ 2 h 30 sur CPU, une seule fois ; une recherche n'encode que la "
       "question, en une fraction de seconde."])
texte_propose("Cinq encodeurs ont été comparés sur les 52 questions du jeu de consultation. bge-m3, retenu, place une "
              "page pertinente parmi les cinq premiers résultats pour 88 % des questions en recherche hybride (MRR "
              "0,69), contre 79 % (MRR 0,58) pour l'encodeur de référence hors ligne ; l'écart est significatif "
              "(Wilcoxon apparié, p = 0,016). Les modèles de similarité de phrases, limités à 128 tokens, ne font pas "
              "mieux que la référence.")
saut()

# ---------------------------------------------------------------- 3. interface
titre("4. Le prototype ANALYS'PME : interface (section 3.4.2, Annexe III)")
para("Quatre parcours (Consulter, Commenter un indicateur, Note d'analyse, Note stratégique) et une page « Base "
     "documentaire ». Identité visuelle : logo du MINPMEESA placé avant le nom ANALYS'PME, couleurs nationales (vert, "
     "rouge, jaune) en version vive, sans émoticônes ; chaque énoncé est présenté comme une carte étiquetée CONSTAT ou "
     "PERSPECTIVE, suivie de ses sources. Aucune ressource externe n'est chargée : l'interface fonctionne hors ligne.")
para("Deux garde-fous d'usage complètent l'interface : (1) en cas de refus d'une question, l'outil propose des "
     "intitulés d'indicateurs de l'Annuaire proches de la question, chacun vérifié au-dessus du seuil d'abstention "
     "(le seuil n'est pas modifié) ; (2) si la réponse du modèle de langage est inexploitable (format invalide, "
     "refus, moins de deux constats sourcés après contrôle, ou attente supérieure à 240 s), le commentaire est rédigé "
     "par les gabarits et ce repli est signalé. Les évaluations du modèle (H1, H2, Tableau 3.2) désactivent ce repli "
     "pour mesurer le modèle seul.")
tableau("Temps de réponse du système (sans modèle de langage)",
        ["Service", "Médiane", "P90", "Mesure du 28/09", "Remarque"],
        [["Consultation", "0,25 s", "0,51 s", "0,20 s (P90 0,40 s)", "recherche hybride + abstention"],
         ["Commentaire d'un indicateur", "0,01 s", "0,13 s", "0,01 s (P90 0,11 s)", "gabarits"],
         ["Note d'analyse (un chapitre)", "2,77 s", "4,18 s", "2,16 s", ""],
         ["Note stratégique", "4,31 s", "4,83 s", "1,88 s", "chiffres clés et contrôles ajoutés le 01/10"]],
        "2026-10-01_apres-plan-AB_sans-llm/resume.md ; 2026-09-28/resume.md")
para("Poste de développement : Linux, 4 cœurs, 15,7 Go, sans GPU. Ces temps n'incluent aucun appel à un modèle de "
     "langage. Avec le moteur api (Groq) sur le PC Windows, la note stratégique a pris 150 s en médiane, surtout "
     "de l'attente imposée par le quota du compte gratuit : ce n'est pas un temps du système, à ne pas reporter "
     "comme tel.", italique=True, taille=10)
captures = [
    ("1_consulter.png", "Parcours « Consulter » : extraits sourcés (document, page) ; refus motivé et suggestions sinon"),
    ("2_commenter.png", "Parcours « Commenter un indicateur » : énoncés étiquetés CONSTAT / PERSPECTIVE et source de chaque valeur"),
    ("3_note_analyse.png", "Parcours « Note d'analyse » : choix de l'Annuaire, puis de l'étendue"),
    ("4_note_strategique.png", "Parcours « Note stratégique » : encadré des chiffres clés de l'exercice 2024"),
    ("5_base_documentaire.png", "Page « Base documentaire » : ajout d'un document et exploration de la base"),
]
for f, nom in captures:
    figure(CAPT / f, nom, f"data/outputs/captures/{f}", 15)
saut()

# ---------------------------------------------------------------- 4. note stratégique
titre("5. Note stratégique 2024 (section 3.5.4, Tableau 3.8, Annexe V)")
para("Mode gabarits (sans modèle de langage), version du 01/10/2026 après les améliorations A et B. "
     "**5 évolutions** retenues (une par grandeur), **549 mots** ; critères BN4 (toute valeur tracée) et BN5 "
     "(rubriques, 3 messages clés, longueur) satisfaits automatiquement ; aucune valeur écartée.")
tableau("Chiffres clés de l'exercice 2024",
        ["Grandeur", "Valeur 2024", "Évolution / 2023", "Source"],
        [["Stock de PME", "443 524", "+12,8 %", "Annuaire 2024, tableau 4, p. 18"],
         ["Créations de PME dans les CFCE", "21 132", "+7,5 %", "Annuaire 2024, tableau 8, p. 20"],
         ["Valeur ajoutée des PME", "7 291 millions de FCFA", "+11,8 %", "Annuaire 2024, tableau 16, p. 27"],
         ["OES enregistrées", "3 909", "+1,1 %", "Annuaire 2024, tableau 21, p. 30"],
         ["UPA enregistrées", "3 602", "+1,3 %", "Annuaire 2024, tableau 29, p. 38"]],
        "data/outputs/note_strategique_2024.md")
titre("Messages clés produits", 2)
puces(["En 2024, le stock de PME atteint 443 524, en hausse de 12,8 % par rapport à 2023.",
       "La dynamique la plus forte concerne « Adamaoua » (répartition par Région) pour le stock de PME : +12,8 % du "
       "stock en un an.",
       "Point de vigilance : les UPA enregistrées reculent pour « Masculin » (répartition par sexe), avec une baisse "
       "de 3,9 % de l'effectif par rapport à 2023."])
titre("Pistes pour la décision (typées, sans chiffre)", 2)
puces(["Cibler : examiner la situation de « Adamaoua » pour le stock de PME.",
       "Cibler : examiner la situation de « Bamenda / Tertiaire » pour les créations de PME dans les CFCE.",
       "Approfondir : documenter les facteurs de la hausse durable observée pour la valeur ajoutée des PME.",
       "Cibler : examiner la situation de « Nord-Ouest » pour les OES enregistrées.",
       "Suivre : fixer un objectif de référence pour les UPA enregistrées."])
para("Exercice 2023 : 4 évolutions calculables (stock, créations, OES, UPA), sous le minimum de 5 ; la note le "
     "signale et l'explique plutôt que d'y faire figurer des évolutions non comparables. Version rédigée par le "
     "modèle de langage (2024, avant les améliorations) : 7 évolutions, 776 mots, BN4 et BN5 satisfaits.")
texte_propose("La note retient une évolution par grandeur suivie (stock, créations, valeur ajoutée, organisations de "
              "l'économie sociale, unités de production artisanale), celle de son total, et la détaille par la "
              "sous-catégorie la plus dynamique, à condition que celle-ci repose sur un effectif d'au moins 50 "
              "unités et 1 % du total. Une variation calculée sur un très petit effectif n'est jamais présentée "
              "comme une tendance.")

titre("6. Chaîne de traçabilité (Tableau 3.7)", 1)
lignes_tr = []
with open(RACINE / "data/outputs/tracabilite_exemple.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if r["code_indicateur"] in ("pme-typologie", "stock-pme-region"):
            lignes_tr.append([r["enonce"], f"n° {r['commentaire_prod_id']} ({r['code_indicateur']}, non validé)",
                              f"{r['variation']} %", r["valeur"], f"{r['ligne']} / {r['colonne']}",
                              f"Annuaire 2024, tableau {r['tableau']}", r["page"]])
tableau("De l'énoncé de la note à la cellule de l'Annuaire",
        ["Énoncé", "Commentaire", "Variation", "Valeur", "Ligne / colonne", "Tableau", "Page"], lignes_tr,
        "data/outputs/tracabilite_exemple.csv")
para("Lecture : chaque énoncé chiffré de la note renvoie à un commentaire, à la variation calculée par le "
     "programme, puis aux deux valeurs de l'Annuaire qui la fondent (exercice et référence), avec ligne, colonne, "
     "tableau et page.")
saut()

# ---------------------------------------------------------------- 5. H1
titre("7. H1 — Recherche documentaire (sections 4.1 et 4.2)")
tableau("Récupération sur 52 questions du corpus (encodeur bge-m3)",
        ["Configuration", "Succès@1", "Succès@5", "MRR", "nDCG@5"],
        [["Lexicale seule (lexique pondéré)", "0,40", "0,71", "0,53", "0,59"],
         ["Lexicale sans lexique", "0,38", "0,71", "0,52", "0,61"],
         ["Dense seule (bge-m3)", "0,54", "0,85", "0,67", "0,85"],
         ["Hybride, RRF k = 10", "0,60", "0,88", "0,71", "0,83"],
         ["Hybride, RRF k = 20", "0,58", "0,87", "0,69", "0,82"],
         ["Hybride, RRF k = 60 (retenu a priori)", "0,58", "0,88", "0,69", "0,82"],
         ["Hybride sans lexique", "0,60", "0,85", "0,71", "0,84"]],
        "2026-09-30_bge-m3_sans-llm/h1_recuperation_configurations.csv", gras_lignes={5})
figure(R_BGE / "figure_h1_succes5_mrr.png", "Succès@5 et MRR par configuration (bge-m3)",
       "2026-09-30_bge-m3_sans-llm/figure_h1_succes5_mrr.png")
figure(R_BGE / "figure_h1_ablations.png", "Ablations : valeur de k et rôle du lexique métier",
       "2026-09-30_bge-m3_sans-llm/figure_h1_ablations.png")
tableau("Tests de Wilcoxon appariés (hybride k = 60)",
        ["Comparaison", "Mesure", "Δ", "p", "Questions gagnées / perdues"],
        [["Hybride vs lexicale", "rang réciproque", "+0,168", "< 0,001", "25 / 6"],
         ["Hybride vs dense", "rang réciproque", "+0,019", "0,681", "9 / 11"],
         ["Hybride vs lexicale", "Succès@5", "", "0,007", ""],
         ["Hybride vs dense", "Succès@5", "", "0,414", ""]],
        "2026-09-30_bge-m3_sans-llm/resultats.json")
tableau("Abstention (validation croisée à 5 plis, signal = cosinus dense maximal)",
        ["Mesure", "Valeur"],
        [["Questions hors corpus refusées", "10 / 10 (100 %)"],
         ["Questions du corpus refusées à tort", "3 / 52 (5,8 %)"],
         ["Seuil calibré (bge-m3)", "0,621"],
         ["Pour mémoire, encodeur de repli", "9 / 10 refusées ; seuil 0,489"]],
        "2026-09-30_bge-m3_sans-llm/h1_abstention_validation_croisee_dense_max_refus_a_tort_max.csv")
para("k = 60 a été fixé a priori et n'est pas réajusté, même si k = 10 obtient un MRR un peu plus élevé : ce serait "
     "du sur-ajustement. Le lexique métier fait gagner 2 questions au Succès@5 hybride, sans effet sur le MRR. "
     "Le taux de 5,8 % de refus à tort dépasse légèrement la cible de 5 %, fixée sur les plis d'apprentissage. "
     "Kappa du jeu de questions : non mesuré (seconde annotation à faire).")
texte_propose("Avec l'encodeur bge-m3, la recherche hybride place une page pertinente parmi les cinq premiers "
              "résultats pour 88 % des 52 questions (MRR 0,69), au-dessus du seuil de 80 % fixé par H1. Elle fait "
              "significativement mieux que la recherche par mots-clés (p < 0,001), mais pas significativement mieux "
              "que la recherche sémantique seule (85 %, p = 0,68) : avec un encodeur performant, l'apport de la "
              "fusion est faible sur ce jeu. Toutes les questions hors sujet sont refusées.")
saut()

titre("8. H1 — Ancrage par les rédactions antérieures (section 4.3)")
tableau("Commentaires du modèle avec / sans appui sur les commentaires antérieurs (gpt-oss-20b)",
        ["Exercice", "n", "ROUGE-L avec / sans", "p", "Similarité avec / sans", "p"],
        [["2024", "13", "0,17 / 0,19", "0,773", "0,44 / 0,52", "0,793"],
         ["2023", "14", "0,13 / 0,16", "0,942", "0,37 / 0,46", "0,923"]],
        "2026-09-28_api_gpt-oss-20b/exercice_20XX/h1_ancrage_par_indicateur.csv")
para("**Critère non atteint** : en 2024, 4 indicateurs gagnent et 9 perdent avec l'appui.")
texte_propose("Contrairement à l'hypothèse, fournir au modèle les commentaires des éditions antérieures n'améliore "
              "pas la proximité avec le commentaire publié (ROUGE-L 0,17 contre 0,19, p = 0,77). Deux explications "
              "sont plausibles : le modèle reprend des formulations d'éditions passées, qui diffèrent de celles de "
              "l'édition évaluée ; les modèles de rédaction allongent le contexte au détriment des valeurs de "
              "l'exercice.")
titre("Le modèle de langage face aux gabarits", 2)
tableau("Proximité avec les commentaires publiés : gabarits contre modèle ancré",
        ["Rédaction", "n", "ROUGE-L", "Similarité", "Indicateurs commentés", "Valeurs citées (moy.)", "Mots (moy.)"],
        [["Gabarits 2024", "13", "0,14", "0,40", "100 %", "3,6", "61"],
         ["LLM ancré 2024 (gpt-oss-20b)", "13", "0,19", "0,49", "100 %", "10,2", "133"],
         ["Gabarits 2023", "14", "0,12", "0,38", "100 %", "3,0", "57"],
         ["LLM ancré 2023 (gpt-oss-20b)", "14", "0,13", "0,37", "86 %", "7,9", "91"],
         ["Gabarits 2024, après améliorations A–B", "13", "0,16", "0,43", "100 %", "6,4", "110"]],
        "2026-09-28_api_gpt-oss-20b/exercice_20XX/h1_reference_gabarits_par_indicateur.csv ; "
        "2026-10-01_apres-plan-AB_sans-llm/resume.md", gras_lignes={1})
figure(R_API / "figure_h1_gabarits_vs_llm.png", "Gabarits contre modèle de langage ancré (2024)",
       "2026-09-28_api_gpt-oss-20b/figure_h1_gabarits_vs_llm.png")
para("Wilcoxon apparié, LLM contre gabarits : 2024, ROUGE-L Δ = +0,049, **p = 0,013** (11 gagnent, 2 perdent), "
     "similarité Δ = +0,088, **p = 0,008** ; 2023, ROUGE-L Δ = +0,016, p = 0,153, similarité Δ = −0,009, p = 0,670. "
     "Les tests portent sur les gabarits du 28/09 ; après les améliorations, les gabarits 2024 atteignent un "
     "ROUGE-L de 0,16 (comparaison au LLM non refaite).")
texte_propose("Face à une rédaction automatique par gabarits (ROUGE-L 0,14), le modèle ancré atteint 0,19 en 2024 "
              "(p = 0,013) et se rapproche significativement des commentaires publiés, en citant trois fois plus de "
              "valeurs, toutes contrôlées. Sur l'exercice 2023, l'écart va dans le même sens mais n'est pas "
              "significatif (p = 0,15).")
saut()

# ---------------------------------------------------------------- 6. H2
titre("9. H2 — Contrôle de citation littérale (section 4.4)")
tableau("Valeurs citées par le modèle, sans et avec contrôle",
        ["Exercice", "Non soutenues sans contrôle", "Après contrôle", "Exactitude après", "Couverture",
         "Couv_ind", "Valeurs écartées"],
        [["2024", "0 / 120", "0 / 120", "1,000", "1,000", "0,92", "0"],
         ["2023", "2 / 112", "0 / 110", "1,000", "0,982", "0,86", "2 (arrondi 1, calcul 1)"]],
        "2026-09-28_api_gpt-oss-20b/exercice_20XX/h2_par_indicateur.csv")
figure(R_API / "figure_h2_exactitude_couverture.png", "Exactitude et Couv_ind, ancrage simple contre ancrage + citation littérale (2024)",
       "2026-09-28_api_gpt-oss-20b/figure_h2_exactitude_couverture.png")
tableau("Critères de H2",
        ["Critère", "Mesure", "Atteint ?"],
        [["0 valeur non soutenue après contrôle", "0 (2024 et 2023)", "oui"],
         ["≥ 1 valeur non soutenue sans contrôle", "0 en 2024 ; 2 en 2023", "non en 2024 (oui en 2023)"],
         ["TFR < 5 %", "non mesurable en 2024 ; à établir par relecture en 2023", "à établir"],
         ["Couv_ind ≥ 80 %", "0,92 (2024) ; 0,86 (2023)", "oui"]],
        "2026-09-28_api_gpt-oss-20b/resume.md")
para("En 2023, des deux valeurs écartées, « plus de 78 % » est un calcul du modèle, écarté à juste titre ; « inférieure "
     "à 4 % » est un seuil, discutable. Le TFR définitif est à établir par relecture (h2_echantillon_relecture.csv).")
texte_propose("Ancré sur les valeurs autorisées, gpt-oss-20b n'a cité aucune valeur non soutenue en 2024 (120 valeurs) "
              "et 2 sur 112 en 2023, retirées par le contrôle littéral. Le contrôle garantit une exactitude de 100 % "
              "après filtrage, pour une couverture de 98 à 100 % des valeurs citées. Sa valeur ajoutée est réelle "
              "mais rare avec un modèle bien ancré ; elle se manifeste davantage sur la borne haute 120b (3,3 % de "
              "valeurs écartées) et sur les commentaires publiés eux-mêmes.")
titre("Analyse complémentaire : les commentaires publiés passés au contrôle (ce n'est pas H2)", 2)
tableau("Valeurs des commentaires publiés retrouvées littéralement dans les sources",
        ["Exercice", "Retrouvées", "Part", "Calcul", "Invention*", "Autre exercice", "Arrondi"],
        [["2024", "61 / 123", "49,6 %", "49", "7", "5", "1"],
         ["2023", "26 / 86", "30,2 %", "38", "16", "0", "6"]],
        "2026-09-28_api_gpt-oss-20b/exercice_20XX/analyse_commentaires_publies.csv")
figure(R_API / "figure_commentaires_publies.png", "Part des valeurs des commentaires publiés retrouvées littéralement",
       "2026-09-28_api_gpt-oss-20b/figure_commentaires_publies.png", 13)
para("* « Invention » regroupe tout ce qui n'a pas pu être rapproché d'une source (chiffres d'autres tableaux, "
     "appariements provisoires) : **cela ne signifie pas une erreur du ministère**. Une grande partie des chiffres "
     "publiés sont des calculs du rédacteur, argument pour que le programme calcule lui-même les variations.",
     italique=True, taille=10)
saut()

# ---------------------------------------------------------------- 7. H3 et synthèse
titre("10. H3 — Temps humain et qualité des notes (section 4.5)")
para("**Non mesurée** : la séance chronométrée et la notation par les lecteurs restent à organiser. Fichiers prêts "
     "dans data/results/2026-09-28_api_gpt-oss-20b/ : h3_protocole_chronometrage.docx, h3_saisie_temps.xlsx, "
     "h3_grille_evaluation.xlsx (BN4 et BN5 pré-remplis par la vérification automatique).")

titre("11. Confrontation des hypothèses (section 4.6, Tableau 4.1)")
tableau("Verdicts provisoires",
        ["Hypothèse", "Critères atteints", "Critères non atteints ou non mesurés", "Verdict"],
        [["H1", "Succès@5 = 0,88 ≥ 0,80 ; hybride ≥ meilleure voie seule ; LLM ancré > gabarits (p = 0,013)",
          "Ancrage par les rédactions antérieures (ROUGE-L 0,17 vs 0,19, p = 0,77)", "non validée (volet récupération atteint)"],
         ["H2", "0 valeur non soutenue après contrôle ; Couv_ind 0,92",
          "≥ 1 valeur non soutenue sans contrôle (non atteint en 2024) ; TFR à établir", "non validée (règle stricte)"],
         ["H3", "—", "Temps humain et grille BN non mesurés", "non concluante"]],
        "resume.md des exécutions de référence")
para("Règle : « validée » si tous les critères sont mesurés et atteints ; « non validée » si un critère mesuré n'est "
     "pas atteint ; « non concluante » si des critères restent non mesurés.", italique=True, taille=10)

titre("12. Résumé et abstract")
texte_propose("Sur un corpus de 18 publications (661 pages) du MINPMEESA, la recherche hybride place une page "
              "pertinente parmi les cinq premiers résultats pour 88 % des 52 questions de test, contre 71 % pour la "
              "recherche lexicale seule, et refuse toutes les questions hors sujet. Le contrôle de citation littérale "
              "garantit que toute valeur d'un commentaire produit est rattachée à une cellule d'un tableau de "
              "l'Annuaire ou à une variation calculée par le programme. Ancré sur ces valeurs, le modèle gpt-oss-20b "
              "produit des commentaires plus proches des commentaires publiés que des gabarits déterministes "
              "(ROUGE-L 0,19 contre 0,14, p = 0,013), sans aucune valeur non soutenue après contrôle.")
texte_propose("On a corpus of 18 MINPMEESA publications (661 pages), hybrid retrieval ranks a relevant page among the "
              "top five results for 88% of 52 test questions, versus 71% for lexical search alone, and declines all "
              "out-of-scope questions. Literal citation control guarantees that every value in a generated commentary "
              "is traced to an Annuaire table cell or to a variation computed by the program. Grounded on these "
              "values, the gpt-oss-20b model produces commentaries closer to the published ones than deterministic "
              "templates (ROUGE-L 0.19 vs 0.14, p = 0.013), with no unsupported value left after control.")

titre("13. Ce qui reste à mesurer avant la soutenance", 2)
puces(["Validation des 58 appariements par double lecture, puis kappa de Cohen ; relancer ensuite la base et "
       "l'évaluation.",
       "Seconde annotation du jeu de questions (kappa) et questions posées par les cadres (confirmation de H1).",
       "Séance H3 (temps humain) et notation des notes stratégiques par les lecteurs (grille BN).",
       "Relecture des valeurs écartées (TFR de H2).",
       "Mesures Ollama (gpt-oss:20b) sur le poste cible de la Cellule (Tableau 3.2)."])

SORTIE.parent.mkdir(parents=True, exist_ok=True)
doc.save(SORTIE)
print(f"{SORTIE} : {n_tab[0]} tableaux, {n_fig[0]} figures")
