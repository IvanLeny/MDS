# Valeurs et textes à insérer dans le mémoire v5

Titre (v5.1) : *« Conception et évaluation d'un système de génération augmentée par récupération (RAG)
hybride à restitution contrôlée, appliqué aux publications statistiques du MINPMEESA : de la génération
assistée des commentaires à la note d'analyse stratégique »*.

Toutes les valeurs ci-dessous sortent d'exécutions réelles, dont la source est indiquée.
Résultats de référence : `data/results/2026-09-28/` (run du 28/09/2026, config `config.yaml`, graine 42).

> **Trois réserves à rappeler dans le chapitre 4, tant qu'elles tiennent :**
> 1. résultats **PROVISOIRES** : appariements au statut « candidat », non encore validés par double lecture ;
> 2. voie dense mesurée avec l'**encodeur de repli hors ligne** (TF-IDF + SVD), et non avec bge-m3 ;
> 3. **aucun modèle de langage** disponible : rédaction en mode extractif ; H1 (ancrage) et H2 « non mesurés ».
>
> Après validation de l'appariement et installation des modèles sur le poste cible, relancer
> `python -m minpmeesa.ingestion.build`, puis `python -m minpmeesa.evaluation.run_all`, et remplacer
> ces valeurs.

Les numéros de sections et de tableaux suivent la liste des espaces « ……… » de la spécification. Vérifier
dans le mémoire que chaque espace attend bien le contenu indiqué.

---

## Tableau 2.6 / Annexe I — Corpus (source : `data/corpus/inventaire.csv`)

| Document | Type | Exercice | Pages | Tableaux | Graphiques | Passages |
|---|---|---|---|---|---|---|
| Annuaire 2021 | annuaire | 2021 | 80 | 60 | 0 | 97 |
| Annuaire 2022 | annuaire | 2022 | 69 | 63 | 0 | 104 |
| Annuaire 2023 | annuaire | 2023 | 86 | 82 | 0 | 134 |
| Annuaire 2024 | annuaire | 2024 | 97 | 86 | 0 | 142 |
| Rapport d'analyse 2021 | rapport_analyse | 2021 | 25 | 2 | 10 | 29 |
| Rapport d'analyse 2022 | rapport_analyse | 2022 | 26 | 1 | 15 | 40 |
| Rapport d'analyse 2023 | rapport_analyse | 2023 | 33 | 5 | 19 | 58 |
| Rapport d'analyse 2024 | rapport_analyse | 2024 | 42 | 1 | 15 | 51 |
| Note de conjoncture T3 2022 | note_conjoncture | 2022 | 20 | 3 | 12 | 28 |
| Note de conjoncture T4 2023 | note_conjoncture | 2023 | 34 | 9 | 39 | 75 |
| Note de conjoncture T1 2024 | note_conjoncture | 2024 | 15 | 1 | 11 | 21 |
| Note de conjoncture T2 2024 | note_conjoncture | 2024 | 15 | 1 | 11 | 21 |
| Note de conjoncture T3 2024 | note_conjoncture | 2024 | 15 | 0 | 9 | 17 |
| Note de conjoncture T1 2025 | note_conjoncture | 2025 | 21 | 1 | 12 | 25 |
| Bulletin loi de finances 2023 | contexte | 2023 | 4 | 0 | 0 | 2 |
| Bulletin n°4 (crédits, garantie) | contexte | 2024 | 2 | 0 | 0 | 3 |
| Note de perspective inflation | contexte | 2023 | 29 | 6 | 8 | 28 |
| Note de perspective compétitivité | contexte | 2024 | 48 | 0 | 3 | 28 |

Totaux : **18 publications, 661 pages** ; base : **903 passages** (hors document de test), **16 211 valeurs**
(triplets), **572 variations calculées**, **8 fragments rejetés** (trop courts). Les « tableaux » des notes et
des rapports sont ceux que détecte l'extracteur (source : `data/base/build_rapport.json`).
Corpus manquant : notes de conjoncture **T4 2024** (et T1 à T3 2023).
Les 18 documents sont au statut « publie », à confirmer auprès de la Cellule. Un document de test synthétique,
« interne », sert au seul test de cloisonnement.

## Annexe II — Table d'appariement (source : `data/pairing/appariement_20XX.csv`)

58 lignes proposées (2021 : 9 ; 2022 : 15 ; 2023 : 19 ; 2024 : 15) : **48 « candidat », 10 « a_verifier »,
0 validée**. Correction de l'erreur connue : 2024, graphique 2 → **tableau 2** (et non plus 17).
→ Insérer la table **après** double lecture ; kappa de Cohen dans `data/pairing/accord_AAAA.json`.

## 3.1.4 / Tableau 3.2 — Choix du modèle de langage (source : `tableau_3_2_modeles_langage.json`)

Choix arrêté (v5.1) : **`llama3.1:8b`** (Ollama, Q4_K_M, local : moteur du déploiement) et, pendant le
développement, **Groq `llama-3.1-8b-instant`** (mêmes poids ouverts). En option, `llama-3.3-70b-versatile`
sert de borne haute de qualité, non déployable sur le poste de la Cellule.

| Moteur / modèle | Déployable | Temps médian | JSON valide | Valeurs écartées |
|---|---|---|---|---|
| ollama / llama3.1:8b (retenu) | oui | non mesuré (Ollama absent du poste de mesure) | — | — |
| ollama / qwen2.5:7b-instruct | oui | non mesuré | — | — |
| ollama / mistral:7b-instruct | oui | non mesuré | — | — |
| ollama / llama3.2:3b | oui | non mesuré | — | — |
| api Groq / llama-3.1-8b-instant | non (développement) | non mesuré (service injoignable, clé absente) | — | — |
| api Groq / llama-3.3-70b-versatile | non (borne haute) | non mesuré | — | — |

→ À remplir par `run_all --llm api` (avec `GROQ_API_KEY`), puis `run_all --llm ollama` sur le poste cible.
Le choix du couple est **arrêté**, mais pas encore étayé par des mesures du prototype : le signaler dans le
texte (voir `docs/ECARTS_MEMOIRE.md`, E12).

## 3.1.5 / Tableau 3.3 — Choix de l'encodeur (source : `tableau_3_3_encodeurs.json`)

| Encodeur | Succès@5 (hybride) | MRR (hybride) | Indexation |
|---|---|---|---|
| BAAI/bge-m3 | non mesuré (modèle absent) | — | — |
| multilingual-e5-large | non mesuré | — | — |
| sentence-camembert-base | non mesuré | — | — |
| MiniLM-L12 (repli léger) | non mesuré | — | — |
| Repli hors ligne TF-IDF + SVD (256 d.) | 0,79 | 0,58 | 22,7 s (904 passages) |

## 3.4.2 — Interface

Quatre parcours et une page « Base documentaire » (`minpmeesa/app/streamlit_app.py`) ; captures dans
`data/outputs/captures/` (Annexe III). Temps de réponse sur le poste de développement (Linux, 4 cœurs,
15,7 Go, sans GPU, mode extractif) : consultation, médiane **0,20 s** (P90 0,40 s) ; commentaire, médiane
**0,01 s** (P90 0,11 s) ; note d'analyse d'un chapitre, **2,16 s** ; note stratégique, **1,88 s**.
Ces temps n'incluent aucun appel à un modèle de langage : à refaire sur le poste cible avec `llama3.1:8b`.

## 3.5.4 / Tableau 3.8 / Annexe V — Note stratégique 2024

Fichier : `data/outputs/note_strategique_2024.docx` (et `.md`). **6 évolutions** retenues, **689 mots**,
contrôles automatiques : BN4 (toute valeur tracée) satisfait ; BN5 (rubriques, 3 messages clés, ≤ 2 pages)
satisfait. Un seul objectif documenté est rattaché : Note de perspective n°001/2024, p. 3.
Attention : pour **2023**, seules **2 évolutions** sont retenues (minimum attendu : 5), faute de variations
citées dans les commentaires. À signaler, ou à reprendre après validation.

## Tableau 3.7 — Chaîne de traçabilité (source : `data/outputs/tracabilite_exemple.csv`)

| Énoncé | Commentaire | Variation | Valeur | Ligne / colonne | Tableau | Page |
|---|---|---|---|---|---|---|
| « Par rapport à 2023, l'évolution la plus marquée concerne « Stock des PME » (hausse de 12,8 %). » | n° 74 (pme-typologie, non validé) | 12,8 % | 443 524 | Stock des PME / 2024 (e) | Annuaire 2024, tableau 16 | 27 |
| (même énoncé) | n° 74 | 12,8 % | 393 166 | Stock des PME / 2023 (e) | Annuaire 2024, tableau 16 | 27 |

## 4.1 / 4.2 — H1, récupération (source : `h1_recuperation_configurations.csv`, 52 questions du corpus)

| Configuration | Succès@1 | Succès@5 | MRR | nDCG@5 |
|---|---|---|---|---|
| Lexicale seule (lexique pondéré) | 0,40 | 0,71 | 0,53 | 0,59 |
| Dense seule (repli) | 0,40 | 0,75 | 0,56 | 0,71 |
| Hybride, RRF k = 10 | 0,44 | 0,77 | 0,59 | 0,70 |
| Hybride, RRF k = 20 | 0,42 | 0,77 | 0,57 | 0,70 |
| **Hybride, RRF k = 60** | 0,42 | **0,79** | 0,58 | 0,71 |
| Hybride sans lexique | 0,42 | 0,73 | 0,57 | 0,72 |

Wilcoxon apparié (hybride k = 60, sur le MRR) : contre la voie lexicale, Δ = +0,055, p = 0,125 ; contre la
voie dense, Δ = +0,022, p = 0,403. Écarts non significatifs à 5 %.
Abstention (validation croisée à 5 plis) : **90 %** des questions hors corpus refusées (9/10) ; **3/52**
questions du corpus refusées à tort (5,8 %) ; seuil 0,489 (cosinus dense).
Kappa du jeu de questions : **non mesuré** (seconde annotation à faire).

## 4.3 — H1, ancrage : **non mesuré** (aucun modèle de langage). 4.4 — H2 : **non mesuré** (même raison).

### Référence « gabarits » (v5.1) — source : `exercice_20XX/h1_reference_gabarits_par_indicateur.csv`

Mêmes indicateurs rédigés en mode `--llm none`, comparés aux commentaires **publiés** du rapport d'analyse
(encodeur de repli pour la similarité) :

| Exercice | n | ROUGE-L | Similarité | Indicateurs commentés | Valeurs citées (moy.) | Mots (moy.) |
|---|---|---|---|---|---|---|
| 2024 | 13 | 0,14 | 0,40 | 100 % | 3,6 | 61 |
| 2023 | 14 | 0,12 | 0,38 | 100 % | 3,0 | 57 |

Le côté « LLM ancré » est **non mesuré**. Texte possible une fois la mesure faite : « Face à une rédaction
automatique par gabarits (ROUGE-L 0,14), le modèle ancré atteint ……… (p = ………) », à présenter
honnêtement, que le résultat soit favorable ou non. La grille BN contient les deux versions de la note
stratégique (gabarits : 2024, 6 évolutions, 689 mots ; 2023, 2 évolutions, 255 mots).

Analyse complémentaire mesurée, **qui n'est pas H2** (source : `exercice_20XX/analyse_commentaires_publies*.csv`).
Le contrôle littéral est appliqué aux commentaires **publiés** par le ministère.
- **2024** : 61 valeurs sur 123 (**49,6 %**) se retrouvent telles quelles dans le tableau apparié ou les
  variations calculées. Les autres : calcul 49, invention 7, chiffre d'un autre exercice 5, arrondi 1.
- **2023** : 26 sur 86 (**30,2 %**). Les autres : calcul 38, invention 16, arrondi 6.

Lecture : une grande partie des chiffres des commentaires publiés sont des calculs faits par le rédacteur
(parts à deux décimales, taux sur des périodes non standard). C'est un argument pour que le programme
calcule lui-même les variations (3.3.3). La catégorie « invention » regroupe tout ce qui n'a pas pu être
rapproché d'une source ; elle inclut les chiffres venant d'autres tableaux et les erreurs d'appariement
provisoires. **Elle ne signifie pas une erreur du ministère.**

## 4.5 — H3 : temps humain et grille BN : **non mesurés** (séance et lecteurs à organiser)

Fichiers prêts dans `data/results/2026-09-28/` : `h3_protocole_chronometrage.docx`, `h3_saisie_temps.xlsx`,
`h3_grille_evaluation.xlsx` (BN4 et BN5 pré-remplis par la vérification automatique).

## 4.6 / Tableau 4.1 — Confrontation (source : `resume.md`)

| Hypothèse | Verdict (provisoire) |
|---|---|
| H1 | **non validée** : Succès@5 = 0,79 < 0,80 ; hybride ≥ meilleure voie seule (oui, non significatif) ; ancrage non mesuré |
| H2 | **non concluante** : non mesurée |
| H3 | **non concluante** : non mesurée (temps système mesurés seulement) |

## Résumé / abstract (« PH »)

Proposition de phrase de résultats, à ajuster après les mesures définitives :
« Sur un corpus de 18 publications (661 pages) du MINPMEESA, la recherche hybride place une page pertinente
parmi les cinq premiers résultats pour 79 % des 52 questions de test, contre 71 % pour la recherche lexicale
seule, et refuse 9 questions hors sujet sur 10. Le contrôle de citation littérale garantit que toute valeur
d'un commentaire produit est rattachée à une cellule d'un tableau de l'Annuaire ou à une variation calculée
par le programme. »
*Abstract* : "On a corpus of 18 MINPMEESA publications (661 pages), hybrid retrieval ranks a relevant page
among the top five results for 79% of 52 test questions, versus 71% for lexical search alone, and declines
9 out of 10 out-of-scope questions. Literal citation control guarantees that every value in a generated
commentary is traced to an Annuaire table cell or to a variation computed by the program."
