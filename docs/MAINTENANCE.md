# Maintenance

## Ajouter une nouvelle édition (Annuaire, rapport, note)

1. Déposer le PDF dans `data/corpus/`, sous un nom explicite (ex. `annuaire_2025.pdf`).
2. L'inscrire dans `data/corpus/registre.yaml` : `doc_id`, `fichier`, `titre`, `type`
   (`annuaire | rapport_analyse | note_conjoncture | contexte`), `exercice`, `trimestre`,
   `statut_diffusion` (`publie | interne`). On peut aussi passer par la page « Base documentaire ».
   **L'exercice se lit dans le contenu**, pas dans le titre courant : plusieurs éditions portent un titre erroné.
3. Reconstruire : `python -m minpmeesa.ingestion.build`. La reconstruction compare le registre à la
   détection automatique et affiche tout désaccord dans les avertissements. Vérifier aussi
   `data/corpus/inventaire.csv`.
4. Si un couple Annuaire + Rapport de la même année est présent, un fichier
   `data/pairing/a_valider_AAAA.xlsx` est produit : il faut le valider (ci-dessous).

## Valider l'appariement (double lecture, section 2.3.2)

1. Ouvrir `data/pairing/a_valider_AAAA.xlsx`. Chaque ligne associe un graphique du rapport à un tableau
   proposé de l'Annuaire, avec les extraits et le score.
2. Le **lecteur 1** remplit la colonne `lecteur_1_decision` (`valide | rejete | corrige`), puis le
   **lecteur 2** remplit la sienne, sans regarder la première. Avec `corrige`, indiquer le bon numéro de tableau.
3. Importer les décisions :
   `python -m minpmeesa.ingestion.pairing importer data/pairing/a_valider_AAAA.xlsx`.
   En cas d'accord, le statut devient `valide` ou `rejete` ; en cas de désaccord, `a_verifier`.
   Le kappa de Cohen est écrit dans `data/pairing/accord_AAAA.json`.
4. Arbitrer les lignes `a_verifier` directement dans `appariement_AAAA.csv` : statut `valide` ou `rejete`.
5. Reconstruire la base. Les décisions humaines du CSV sont conservées d'une reconstruction à l'autre.
6. Relancer l'évaluation : `python -m minpmeesa.evaluation.run_all`. Une fois des lignes `valide`
   présentes, seules ces lignes servent à l'évaluation, et la mention PROVISOIRE disparaît.

## Reconstruire la base

`python -m minpmeesa.ingestion.build` efface `data/base/` et la recrée à partir des seuls PDF, du
registre et des décisions d'appariement. Il faut reconstruire après tout ajout de document, tout
changement d'encodeur ou toute validation d'appariement.

## Changer de modèle

- Encodeur : `config.yaml > embeddings.modele`, puis reconstruire.
- Modèle de langage : `config.yaml > llm.modele` (nom Ollama), sans reconstruction.
- Choisir sur mesures : `run_all` remplit `tableau_3_2_modeles_langage.json` et `tableau_3_3_encodeurs.json`.

## Jeu de questions de consultation

`scripts/construire_jeu_consultation.py` régénère `data/gold/consultation.json`. Les pages sont localisées
automatiquement à partir d'extraits exacts. Pour ajouter les questions des cadres, les ajouter au script
avec `source: "cellule"`. Le second lecteur renseigne `annotateur_2` : la liste des `(doc_id, pages)` qu'il
juge pertinents. Le kappa est alors calculé par `run_all`.
