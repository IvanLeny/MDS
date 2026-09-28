# Résumé de l'évaluation — 102.6 s d'exécution

> **Résultats PROVISOIRES** : les tables d'appariement ne sont pas encore validées par double lecture ; l'évaluation utilise les appariements « candidats ».
> Encodeur utilisé : `repli-hors-ligne-tfidf-svd`. Modèle de langage : repli en mode extractif : Ollama indisponible ou modèle qwen2.5:7b-instruct-q4_K_M absent ; fichier GGUF absent (models/llm/modele.gguf).

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
- **Rédaction avec modèle de langage (H1 ancrage, H2)** : aucun modèle de langage disponible : la comparaison avec/sans appui porte sur des sorties de modèle.
- **Analyse complémentaire** (ce n'est pas H2) : dans les commentaires publiés de 2024, 61 valeurs sur 123 (49,6 %) se retrouvent telles quelles dans le tableau apparié ou les variations calculées ; les autres se répartissent en arrondi : 1, calcul : 49, chiffre d'un autre exercice : 5, invention : 7.
- **Temps de réponse du système** (poste de développement) : consultation : médiane 0,20 s, P90 0,46 s ; commentaire : médiane 0,01 s, P90 0,38 s ; note d'analyse : médiane 2,19 s, P90 2,31 s ; note stratégique : médiane 1,70 s, P90 1,86 s.

## Choix des modèles (Tableaux 3.2 et 3.3)

- BAAI/bge-m3 : non mesuré : modèle absent de models/embeddings (à télécharger avec scripts/telecharger_modeles.py sur un poste connecté)
- intfloat/multilingual-e5-large : non mesuré : modèle absent de models/embeddings (à télécharger avec scripts/telecharger_modeles.py sur un poste connecté)
- dangvantuan/sentence-camembert-base : non mesuré : modèle absent de models/embeddings (à télécharger avec scripts/telecharger_modeles.py sur un poste connecté)
- sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 : non mesuré : modèle absent de models/embeddings (à télécharger avec scripts/telecharger_modeles.py sur un poste connecté)
- repli-hors-ligne-tfidf-svd : Succès@5 (hybride) 0,79, MRR 0,58, indexation 22,0 s
- qwen2.5:3b-instruct-q4_K_M : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé) sur ce poste
- qwen2.5:7b-instruct-q4_K_M : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé) sur ce poste
- llama3.2:3b-instruct-q4_K_M : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé) sur ce poste
- mistral:7b-instruct-q4_K_M : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé) sur ce poste
- phi3.5:3.8b-mini-instruct-q4_K_M : non mesuré : modèle non installé dans Ollama (ou Ollama non lancé) sur ce poste

## Ce qui reste à faire par l'étudiant

- valider les tables d'appariement (double lecture) puis relancer la reconstruction et l'évaluation ;
- faire annoter le jeu de questions par un second lecteur (kappa) et y ajouter les questions des cadres ;
- conduire la séance de chronométrage (≥ 3 cadres) et remplir h3_saisie_temps.xlsx ;
- faire noter les notes stratégiques par 2 lecteurs (h3_grille_evaluation.xlsx) ;
- relire l'échantillon h2_echantillon_relecture.csv (quand un modèle de langage est disponible) ;
- confirmer le statut de diffusion réel de chaque document auprès de la Cellule ;
- lancer l'évaluation sur le poste cible avec les modèles téléchargés (bge-m3, Ollama).