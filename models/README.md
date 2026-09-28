# Modèles locaux (hors Git)

Ce dossier reçoit les modèles téléchargés **une seule fois** par
`python scripts/telecharger_modeles.py` (poste connecté), puis copiés sur le poste de la Cellule.
À l'exécution, aucun modèle n'est téléchargé : ils sont lus ici.

- `models/embeddings/<nom>` : encodeurs (sentence-transformers) ;
- les modèles de langage sont gérés par Ollama (`ollama pull ...`), stockés par Ollama.
