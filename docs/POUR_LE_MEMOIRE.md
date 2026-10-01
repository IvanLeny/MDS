# Valeurs et textes à insérer dans le mémoire v5

Titre (v5.1) : *« Conception et évaluation d'un système de génération augmentée par récupération (RAG)
hybride à restitution contrôlée, appliqué aux publications statistiques du MINPMEESA : de la génération
assistée des commentaires à la note d'analyse stratégique »*.

Toutes les valeurs ci-dessous sortent d'exécutions réelles, dont la source est indiquée.
Deux exécutions de référence (config `config.yaml`, graine 42, même base de 904 passages) :
- `data/results/2026-09-28/` : environnement cloud (Linux), **sans modèle de langage** (mode extractif) ;
- `data/results/2026-09-28_api_gpt-oss-20b/` : PC de l'étudiant (Windows 10, Python 3.12, 4 cœurs), moteur
  **`api` Groq `openai/gpt-oss-20b`** (`run_all --llm api`, 11 h 20 d'exécution, surtout de l'attente liée aux
  limites du compte gratuit). **C'est la source des valeurs H1-ancrage, H2 et Tableau 3.2 ci-dessous.**
  Les valeurs de H1-récupération y sont identiques à celles du cloud.
- `MDS_resultats/2026-09-30_bge-m3_sans-llm/` (Google Colab, CPU) : base reconstruite avec l'**encodeur retenu
  bge-m3**, `run_all --llm none --encodeurs-mesures …`. **C'est la source des valeurs H1-récupération et
  abstention ci-dessous** (à verser dans `data/results/`).

> **Trois réserves à rappeler dans le chapitre 4, tant qu'elles tiennent :**
> 1. résultats **PROVISOIRES** : appariements au statut « candidat », non encore validés par double lecture ;
> 2. H1-récupération mesurée avec bge-m3 sur le **jeu qui a servi à choisir l'encodeur** (biais de sélection,
>    E18) : à confirmer sur les questions des cadres ;
> 3. modèle de langage appelé via un **service distant de développement** (Groq, `openai/gpt-oss-20b`), et non
>    par Ollama sur le poste cible : mêmes poids ouverts, mais temps de réponse non transposables.
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

Choix retenu (option A, octobre 2026, voir `docs/ECARTS_MEMOIRE.md` E15) : **`gpt-oss:20b`** (Ollama,
local : moteur du déploiement) et, pendant le développement, **Groq `openai/gpt-oss-20b`** (mêmes poids
ouverts). Borne haute non déployable : `openai/gpt-oss-120b`. Le couple initial `llama3.1:8b` /
`llama-3.1-8b-instant` n'est plus disponible chez Groq.

| Moteur / modèle | Déployable | Temps médian | JSON valide | Valeurs écartées |
|---|---|---|---|---|
| ollama / gpt-oss:20b (retenu) | oui (16 Go RAM) | non mesuré (Ollama absent du poste de mesure) | — | — |
| ollama / llama3.1:8b | oui | non mesuré | — | — |
| ollama / qwen2.5:7b-instruct | oui | non mesuré | — | — |
| ollama / mistral:7b-instruct | oui | non mesuré | — | — |
| ollama / llama3.2:3b | oui | non mesuré | — | — |
| api Groq / openai/gpt-oss-20b | non (développement) | 23,2 s (réseau inclus) | 100 % | 1,1 % |
| api Groq / openai/gpt-oss-120b | non (borne haute) | 26,2 s (réseau inclus) | 100 % | 3,3 % |

Mesure sur 20 indicateurs (source : `data/results/2026-09-28_api_gpt-oss-20b/tableau_3_2_modeles_langage.json`) ;
2 appels en échec sur 20 pour le 20b (coupures réseau), 0 pour le 120b. « Valeurs écartées » = part des valeurs
citées par le modèle que le contrôle littéral a retirées.
Lecture : le modèle 20b produit toujours un JSON valide et fait **moins** de citations non soutenues que la
borne haute 120b (1,1 % contre 3,3 %) : le modèle plus gros n'apporte rien sur ce critère, ce qui conforte le
choix du 20b. Les lignes Ollama restent à mesurer sur le poste cible (`run_all --llm ollama`).

## 3.1.5 / Tableau 3.3 — Choix de l'encodeur (source : `tableau_3_3_encodeurs.json`)

Mesures du 30/09/2026 sur Google Colab (**CPU**, 2 cœurs virtuels, sans GPU), base reconstruite à l'identique
(904 passages, 16 211 valeurs, 572 variations) ; 52 questions du corpus ; source :
`data/results/2026-09-30_encodeurs/` (`tableau_3_3_encodeurs.json`, `tableau_3_3_par_question.csv`).

| Encodeur | Longueur max. (tokens) | Succès@5 hybride | MRR hybride | Dense seul (S@5 / MRR) | p (MRR hybride vs repli) | Indexation (Colab CPU) |
|---|---|---|---|---|---|---|
| **BAAI/bge-m3 (retenu)** | 8 192 | **0,88** (46/52) | **0,694** | **0,85 / 0,674** | **0,016** | 9 090 s (2 h 31) |
| multilingual-e5-large | 512 | 0,87 (45/52) | 0,681 | 0,85 / 0,619 | 0,015 | 4 989 s (1 h 23) |
| sentence-camembert-base | 128 | 0,71 (37/52) | 0,475 | 0,42 / 0,302 | 0,109 | 448 s |
| MiniLM-L12 (repli léger) | 128 | 0,81 (42/52) | 0,512 | 0,46 / 0,394 | 0,348 | 136 s |
| Repli hors ligne TF-IDF + SVD (256 d.) | sans limite | 0,79 (41/52) | 0,581 | 0,75 / 0,559 | — | 29 s |

**Choix : bge-m3**, conformément à la règle fixée a priori (E18) : c'est le choix par défaut du mémoire, et aucun
autre candidat ne fait mieux (il est premier sur les cinq critères de qualité).

Lecture :
- les deux encodeurs conçus pour la **recherche documentaire** (bge-m3, e5) améliorent significativement le
  repli (MRR hybride +0,11, p ≈ 0,015) ; les deux modèles de **similarité de phrases** (camembert, MiniLM) non ;
- la **longueur lue** explique une grande part de l'écart : les modèles limités à 128 tokens ne voient que le
  début des passages, alors que les tableaux linéarisés dépassent souvent 500 tokens ; bge-m3, qui lit les
  passages en entier, obtient la meilleure voie dense (MRR 0,674 contre 0,619 pour e5, limité à 512) ;
- **coût** : sur CPU, l'indexation par bge-m3 prend environ 2 h 30 (une seule fois, à la construction de la
  base) ; une recherche n'encode que la question, en une fraction de seconde. Le poste de la Cellule devra donc
  prévoir une reconstruction longue, sans effet sur l'usage quotidien ;
- réserve (E18) : ces scores servent aussi au choix ; H1 est à confirmer sur les questions des cadres.

Texte proposé (3.1.5) : « Cinq encodeurs ont été comparés sur les 52 questions du jeu de consultation. bge-m3,
retenu, place une page pertinente parmi les cinq premiers résultats pour 88 % des questions en recherche
hybride (MRR 0,69), contre 79 % (MRR 0,58) pour l'encodeur de référence hors ligne ; l'écart est significatif
(Wilcoxon apparié, p = 0,016). Les modèles de similarité de phrases, limités à 128 tokens, ne font pas mieux que
la référence. »


## 3.4.2 — Interface

Quatre parcours et une page « Base documentaire » (`minpmeesa/app/streamlit_app.py`) ; captures dans
`data/outputs/captures/` (Annexe III). Temps de réponse sur le poste de développement (Linux, 4 cœurs,
15,7 Go, sans GPU, mode extractif) : consultation, médiane **0,20 s** (P90 0,40 s) ; commentaire, médiane
**0,01 s** (P90 0,11 s) ; note d'analyse d'un chapitre, **2,16 s** ; note stratégique, **1,88 s**.
Ces temps n'incluent aucun appel à un modèle de langage : à refaire sur le poste cible avec `gpt-oss:20b`.
Avec le moteur `api` (PC Windows) : note stratégique, médiane **150 s** ; note d'analyse d'un chapitre, médiane
**58 min** (maximum 9 h 42). Ces durées mesurent surtout l'**attente imposée par le quota du compte gratuit
Groq** (appels mis en file), et non le calcul : elles ne sont pas à reporter comme temps du système. Le temps
« commentaire » (médiane 0,04 s) est lu dans le cache disque, les commentaires ayant déjà été générés pour H2.

## 3.5.4 / Tableau 3.8 / Annexe V — Note stratégique 2024

Fichier : `data/outputs/note_strategique_2024.docx` (et `.md`). **6 évolutions** retenues, **689 mots**,
contrôles automatiques : BN4 (toute valeur tracée) satisfait ; BN5 (rubriques, 3 messages clés, ≤ 2 pages)
satisfait. Un seul objectif documenté est rattaché : Note de perspective n°001/2024, p. 3.
Attention : pour **2023**, seules **2 évolutions** sont retenues (minimum attendu : 5), faute de variations
citées dans les commentaires. À signaler, ou à reprendre après validation.
Version rédigée par le modèle de langage (`data/results/2026-09-28_api_gpt-oss-20b/note_strategique_2024_llm.docx`) :
**7 évolutions, 776 mots**, BN4 et BN5 satisfaits (aucune valeur non tracée). 2023 : 2 évolutions, 258 mots.

## Tableau 3.7 — Chaîne de traçabilité (source : `data/outputs/tracabilite_exemple.csv`)

| Énoncé | Commentaire | Variation | Valeur | Ligne / colonne | Tableau | Page |
|---|---|---|---|---|---|---|
| « Par rapport à 2023, l'évolution la plus marquée concerne « Stock des PME » (hausse de 12,8 %). » | n° 74 (pme-typologie, non validé) | 12,8 % | 443 524 | Stock des PME / 2024 (e) | Annuaire 2024, tableau 16 | 27 |
| (même énoncé) | n° 74 | 12,8 % | 393 166 | Stock des PME / 2023 (e) | Annuaire 2024, tableau 16 | 27 |

## 4.1 / 4.2 — H1, récupération (source : `2026-09-30_bge-m3_sans-llm/`, 52 questions du corpus, encodeur bge-m3)

| Configuration | Succès@5 | MRR |
|---|---|---|
| Lexicale seule (lexique pondéré) | 0,71 | n.c. |
| Dense seule (bge-m3) | 0,85 | 0,67 |
| **Hybride, RRF k = 60** | **0,88** | **0,69** |

(Succès@1, nDCG@5 et ablations k = 10, 20 et « sans lexique » : dans `h1_recuperation_configurations.csv` du
dossier, à reporter une fois versé dans le dépôt ; « n.c. » = non communiqué dans le résumé.)

Wilcoxon apparié (hybride k = 60, sur le rang réciproque) : contre la voie lexicale, **p = 0,001** ; contre la
voie dense, p = 0,681. L'hybride améliore nettement la recherche par mots-clés ; face à bge-m3 seul, le gain
(+0,03 de Succès@5, +0,02 de MRR) n'est pas significatif.
Abstention (validation croisée à 5 plis, signal = cosinus dense maximal) : **100 %** des questions hors corpus
refusées (10/10) ; **3/52** questions du corpus refusées à tort (5,8 %, légèrement au-dessus de la cible de 5 %
fixée pour la calibration : la cible porte sur les plis d'apprentissage, le taux rapporté sur les plis de test) ;
seuil 0,621.
Pour mémoire, avec l'encodeur de repli (28/09) : Succès@5 0,79, MRR 0,58, 9/10 hors corpus refusées.
Kappa du jeu de questions : **non mesuré** (seconde annotation à faire).

Texte proposé (4.2) : « Avec l'encodeur bge-m3, la recherche hybride place une page pertinente parmi les cinq
premiers résultats pour 88 % des 52 questions (MRR 0,69), au-dessus du seuil de 80 % fixé par H1. Elle fait
significativement mieux que la recherche par mots-clés (p = 0,001), mais pas significativement mieux que la
recherche sémantique seule (85 %, p = 0,68) : avec un encodeur performant, l'apport de la fusion est faible
sur ce jeu. Toutes les questions hors sujet sont refusées. »

## 4.3 — H1, ancrage (source : `exercice_20XX/h1_ancrage_par_indicateur.csv`, moteur api gpt-oss-20b)

Commentaires rédigés par le modèle **avec** les modèles de rédaction (commentaires antérieurs récupérés) contre
**sans**, comparés aux commentaires publiés :

| Exercice | n | ROUGE-L avec / sans | p (Wilcoxon) | Similarité avec / sans | p |
|---|---|---|---|---|---|
| 2024 | 13 | 0,17 / 0,19 | 0,773 | 0,44 / 0,52 | 0,793 |
| 2023 | 14 | 0,13 / 0,16 | 0,942 | 0,37 / 0,46 | 0,923 |

**Critère non atteint** : l'appui sur les rédactions antérieures ne rapproche pas le texte produit des
commentaires publiés ; il l'en éloigne légèrement (4 indicateurs gagnent, 9 perdent en 2024). Texte proposé :
« Contrairement à l'hypothèse, fournir au modèle les commentaires des éditions antérieures n'améliore pas la
proximité avec le commentaire publié (ROUGE-L 0,17 contre 0,19, p = 0,77). Deux explications sont
plausibles : le modèle reprend des formulations d'éditions passées, qui diffèrent de celles de l'édition
évaluée ; les modèles de rédaction allongent le contexte au détriment des valeurs de l'exercice. L'effet
propre de l'ancrage se lit plutôt dans la comparaison aux gabarits ci-dessous. »

## 4.4 — H2, contrôle de citation littérale (source : `exercice_20XX/h2_par_indicateur.csv`)

| Exercice | Valeurs non soutenues sans contrôle | Après contrôle | Exa après | Couv | Couv_ind | Valeurs écartées |
|---|---|---|---|---|---|---|
| 2024 | **0** / 120 | 0 / 120 | 1,000 | 1,000 | 0,92 | 0 |
| 2023 | **2** / 112 | 0 / 110 | 1,000 | 0,982 | 0,86 | 2 (arrondi 1, calcul 1) |

- **« 0 après contrôle »** : atteint pour les deux exercices.
- **« ≥ 1 sans contrôle »** : non atteint en 2024 (le modèle ancré n'a cité aucune valeur non soutenue), atteint
  en 2023. Le verdict du Tableau 4.1 porte sur 2024 : **critère non atteint**, donc H2 « non validée » selon la
  règle. Voir `docs/ECARTS_MEMOIRE.md` E17 pour la discussion.
- **TFR** : non mesurable en 2024 (aucune valeur écartée). En 2023, la vérification automatique classe les 2
  valeurs écartées comme faux rejets (TFR 2/2), mais sur 2 valeurs seulement et par une heuristique
  (le nombre apparaît sur la page source). À la relecture : « plus de 78 % » (part de Yaoundé et Douala) est
  un **calcul du modèle**, écarté à juste titre ; « inférieure à 4 % » est un seuil, discutable. TFR définitif :
  **à établir par relecture** (`h2_echantillon_relecture.csv`).
- **Couv_ind ≥ 80 %** : atteint (0,92 en 2024 ; 0,86 en 2023).

Texte proposé : « Ancré sur les valeurs autorisées, gpt-oss-20b n'a cité aucune valeur non soutenue en 2024
(120 valeurs) et 2 sur 112 en 2023, retirées par le contrôle littéral. Le contrôle garantit une exactitude de
100 % après filtrage, pour une couverture de 98 à 100 % des valeurs citées. La valeur ajoutée du contrôle est
réelle mais rare avec un modèle bien ancré ; elle se manifeste davantage sur la borne haute 120b (3,3 % de
valeurs écartées) et sur les commentaires publiés eux-mêmes (voir l'analyse complémentaire). »

### Référence « gabarits » (v5.1) — source : `exercice_20XX/h1_reference_gabarits_par_indicateur.csv`

Mêmes indicateurs rédigés en mode `--llm none`, comparés aux commentaires **publiés** du rapport d'analyse
(encodeur de repli pour la similarité) :

| Exercice | n | ROUGE-L | Similarité | Indicateurs commentés | Valeurs citées (moy.) | Mots (moy.) |
|---|---|---|---|---|---|---|
| Gabarits 2024 | 13 | 0,14 | 0,40 | 100 % | 3,6 | 61 |
| **LLM ancré 2024** (gpt-oss-20b) | 13 | **0,19** | **0,49** | 100 % | 10,2 | 133 |
| Gabarits 2023 | 14 | 0,12 | 0,38 | 100 % | 3,0 | 57 |
| **LLM ancré 2023** (gpt-oss-20b) | 14 | 0,13 | 0,37 | 86 % | 7,9 | 91 |

Wilcoxon apparié, LLM contre gabarits :
- 2024 : ROUGE-L Δ = +0,049, **p = 0,013** (11 indicateurs gagnent, 2 perdent) ; similarité Δ = +0,088, **p = 0,008** ;
- 2023 : ROUGE-L Δ = +0,016, p = 0,153 (11 gagnent, 3 perdent) ; similarité Δ = −0,009, p = 0,670.

Texte proposé : « Face à une rédaction automatique par gabarits (ROUGE-L 0,14), le modèle ancré atteint
0,19 en 2024 (p = 0,013) et se rapproche significativement des commentaires publiés, en citant trois fois plus
de valeurs, toutes contrôlées. Sur l'exercice 2023, l'écart va dans le même sens mais n'est pas significatif
(p = 0,15). » La grille BN contient les deux versions de la note stratégique (gabarits : 2024, 6 évolutions,
689 mots ; LLM : 2024, 7 évolutions, 776 mots ; 2023 : 2 évolutions dans les deux versions).

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

Fichiers prêts dans `data/results/2026-09-28_api_gpt-oss-20b/` (avec les notes des deux versions) : `h3_protocole_chronometrage.docx`, `h3_saisie_temps.xlsx`,
`h3_grille_evaluation.xlsx` (BN4 et BN5 pré-remplis par la vérification automatique).

## 4.6 / Tableau 4.1 — Confrontation (source : `resume.md`)

| Hypothèse | Verdict (provisoire) |
|---|---|
| H1 | **non validée** (règle stricte), mais **volet récupération atteint** : Succès@5 = 0,88 ≥ 0,80 avec bge-m3 ; hybride ≥ meilleure voie seule (0,88 vs 0,85 ; significatif contre lexicale, p = 0,001, non contre dense, p = 0,68). Le critère qui échoue est l'ancrage par les rédactions antérieures (ROUGE-L 0,17 vs 0,19, p = 0,77) ; en revanche, LLM ancré > gabarits (p = 0,013, 2024) |
| H2 | **non validée** (au sens strict de la règle) : 0 valeur non soutenue après contrôle (atteint), mais aucune avant contrôle en 2024 (le critère « ≥ 1 sans » n'est atteint qu'en 2023) ; TFR à établir par relecture ; Couv_ind 0,92 (atteint) |
| H3 | **non concluante** : non mesurée (temps système mesurés seulement) |

## Résumé / abstract (« PH »)

Proposition de phrase de résultats, à ajuster après les mesures définitives :
« Sur un corpus de 18 publications (661 pages) du MINPMEESA, la recherche hybride place une page pertinente
parmi les cinq premiers résultats pour 88 % des 52 questions de test, contre 71 % pour la recherche lexicale
seule, et refuse toutes les questions hors sujet. Le contrôle de citation littérale garantit que toute valeur
d'un commentaire produit est rattachée à une cellule d'un tableau de l'Annuaire ou à une variation calculée
par le programme. Ancré sur ces valeurs, le modèle gpt-oss-20b produit des commentaires plus proches des
commentaires publiés que des gabarits déterministes (ROUGE-L 0,19 contre 0,14, p = 0,013), sans aucune valeur
non soutenue après contrôle. »
*Abstract* : "On a corpus of 18 MINPMEESA publications (661 pages), hybrid retrieval ranks a relevant page
among the top five results for 88% of 52 test questions, versus 71% for lexical search alone, and declines
all out-of-scope questions. Literal citation control guarantees that every value in a generated
commentary is traced to an Annuaire table cell or to a variation computed by the program. Grounded on these
values, the gpt-oss-20b model produces commentaries closer to the published ones than deterministic templates
(ROUGE-L 0.19 vs 0.14, p = 0.013), with no unsupported value left after control."
