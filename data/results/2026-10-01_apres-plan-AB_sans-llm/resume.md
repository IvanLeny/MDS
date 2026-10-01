# Résumé de l'évaluation — 141.7 s d'exécution

> **Résultats PROVISOIRES** : les tables d'appariement ne sont pas encore validées par double lecture ; l'évaluation utilise les appariements « candidats ».
> **Moteur du modèle de langage : `none` — modèle : `aucun (mode extractif)`** (mode sans modèle de langage (--llm none)).
> Encodeur utilisé : `repli-hors-ligne-tfidf-svd`.


## Tableau 4.1 — Confrontation des hypothèses aux critères

| Hypothèse | Critère | Valeur mesurée | p-value | Critère atteint ? |
|---|---|---|---|---|
| H1 | Succès@5 (hybride) ≥ 0,80 | 0,79 | — | non |
| H1 | hybride ≥ meilleure voie seule (Succès@5 / MRR) | 0,79 vs 0,75 / 0,58 vs 0,56 | lexicale : 0,125 ; dense : 0,403 (MRR, Wilcoxon) | oui |
| H1 | ROUGE-L avec appui > sans appui | non mesuré | — | — |
| H2 | 0 valeur non soutenue après contrôle, ≥ 1 sans | non mesuré | — | — |
| H2 | TFR < 5 % | non mesuré | — | — |
| H2 | Couv_ind ≥ 80 % | non mesuré | — | — |
| H3 | réduction du temps médian ≥ 50 % | non mesuré (séance humaine à conduire) | — | — |
| H3 | ≥ 80 % des notes satisfont ≥ 4 critères sur 5 | non mesuré (séance humaine à conduire) | — | — |

| Hypothèse | Verdict |
|---|---|
| H1 | **non validée** |
| H2 | **non concluante** |
| H3 | **non concluante** |

Règle : « validée » si tous les critères sont mesurés et atteints ; « non validée » si un critère mesuré n'est pas atteint ; « non concluante » si des critères restent non mesurés.

## Ce qu'il faut retenir, en français simple

- **Recherche dans les publications** : sur 52 questions, la bonne page figure parmi les 5 premiers résultats dans 79 % des cas avec la recherche hybride, contre 71 % (mots-clés seuls) et 75 % (recherche sémantique seule). Le seuil de 80 % n'est pas atteint.
- **Abstention** (validation croisée) : 90 % des questions hors sujet sont refusées ; 3 question(s) du corpus sur 52 sont refusées à tort. Seuil calibré : 0,489 (signal et critère : dense_max/refus_a_tort_max ; les autres combinaisons figurent dans resultats.json).
- **Rédaction avec modèle de langage (H1 ancrage, H2)** : non mesuré (aucun modèle de langage disponible : la comparaison avec/sans appui porte sur des sorties de modèle.).
- **Analyse complémentaire** (ce n'est pas H2) : dans les commentaires publiés de 2024, 67 valeurs sur 123 (54,5 %) se retrouvent telles quelles dans le tableau apparié ou les variations calculées ; les autres se répartissent en arrondi : 2, calcul : 42, chiffre d'un autre exercice : 5, invention : 7.
- **Temps de réponse du système** (poste de développement) : consultation : médiane 0,25 s, P90 0,51 s ; commentaire : médiane 0,01 s, P90 0,13 s ; note d'analyse : médiane 2,77 s, P90 4,18 s ; note stratégique : médiane 4,31 s, P90 4,83 s.

## Référence « gabarits » : le modèle de langage apporte-t-il quelque chose ?

Comparaison aux 13 commentaires publiés de 2024 (encodeur `repli-hors-ligne-tfidf-svd`).

| Rédaction | ROUGE-L | Similarité | Indicateurs commentés | Valeurs citées (moy.) | Mots (moy.) |
|---|---|---|---|---|---|
| Gabarits (sans LLM) | 0,16 | 0,43 | 1,00 | 6,4 | 110 |
| LLM ancré | non mesuré | — | — | — | — |

Côté LLM : non mesuré (aucun modèle de langage disponible). Les notes stratégiques des deux versions sont à noter dans h3_grille_evaluation.xlsx dès qu'un modèle est disponible.

## Choix des modèles (Tableaux 3.2 et 3.3)

- repli-hors-ligne-tfidf-svd : Succès@5 (hybride) 0,79, MRR 0,58, indexation 29,1 s
- BAAI/bge-m3 : Succès@5 (hybride) 0,88, MRR 0,69, indexation 9089,8 s, MRR contre repli : p = 0,016
- intfloat/multilingual-e5-large : Succès@5 (hybride) 0,87, MRR 0,68, indexation 4989,3 s, MRR contre repli : p = 0,015
- dangvantuan/sentence-camembert-base : Succès@5 (hybride) 0,71, MRR 0,48, indexation 447,6 s, MRR contre repli : p = 0,109
- sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 : Succès@5 (hybride) 0,81, MRR 0,51, indexation 136,2 s, MRR contre repli : p = 0,348
- ollama / gpt-oss:20b (retenu) : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé)
- ollama / llama3.1:8b : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé)
- ollama / qwen2.5:7b-instruct : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé)
- ollama / mistral:7b-instruct : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé)
- ollama / llama3.2:3b : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé)
- api:groq / openai/gpt-oss-20b : non mesuré : clé API absente : définir la variable d'environnement GROQ_API_KEY
- api:groq / openai/gpt-oss-120b — borne haute, non déployable : non mesuré : clé API absente : définir la variable d'environnement GROQ_API_KEY

## Ce qui reste à faire par l'étudiant

- valider les tables d'appariement (double lecture) puis relancer la reconstruction et l'évaluation ;
- faire annoter le jeu de questions par un second lecteur (kappa) et y ajouter les questions des cadres ;
- conduire la séance de chronométrage (≥ 3 cadres) et remplir h3_saisie_temps.xlsx ;
- faire noter les notes stratégiques par 2 lecteurs (h3_grille_evaluation.xlsx) ;
- relire l'échantillon h2_echantillon_relecture.csv (quand un modèle de langage est disponible) ;
- confirmer le statut de diffusion réel de chaque document auprès de la Cellule ;
- lancer l'évaluation sur le poste cible avec les modèles téléchargés (bge-m3, Ollama).