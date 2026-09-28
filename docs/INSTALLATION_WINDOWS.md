# Installation sur le poste de la Cellule (Windows, sans réseau en exploitation)

Poste visé : Windows 10/11, 8 à 16 Go de mémoire, sans carte graphique. Deux temps :
**préparation** sur un poste connecté, puis **copie** sur le poste de la Cellule.

## 1. Sur un poste connecté à Internet (une seule fois)

1. Installer **Python 3.11** (64 bits) depuis python.org. Cocher « Add python.exe to PATH ».
2. Installer **Ollama pour Windows** (ollama.com). Il tourne en tâche de fond et n'écoute que sur `127.0.0.1`.
3. Copier le dossier du projet (par exemple `C:\MINPMEESA\`), puis ouvrir une invite de commandes dans ce dossier :
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python scripts\telecharger_modeles.py
   ```
   Le script enregistre les encodeurs dans `models\embeddings\`. Il tire aussi les modèles de langage
   candidats avec `ollama pull`.
4. Pour préparer une installation **entièrement hors ligne** : `pip download -r requirements.txt -d paquets`
   (copier ensuite le dossier `paquets`).

## 2. Sur le poste de la Cellule

1. Installer Python 3.11 et Ollama (installeurs copiés sur clé USB).
2. Copier le dossier du projet, y compris `models\` et, si besoin, `paquets\`.
3. Copier les modèles Ollama : dossier `%USERPROFILE%\.ollama\models` du poste connecté.
4. Installer les dépendances sans réseau :
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install --no-index --find-links paquets -r requirements.txt
   ```
5. Construire la base : `python -m minpmeesa.ingestion.build` (2 à 5 minutes).
6. Lancer l'outil : **double-clic sur `demarrer.bat`**. Le navigateur s'ouvre sur `http://127.0.0.1:8501`.

## 3. Réglages

- `config.yaml`, section `llm` : `backend: ollama` sur le poste de la Cellule (modèle `llama3.1:8b`,
  à installer avec `ollama pull llama3.1:8b`) ; `backend: none` pour travailler sans modèle de langage
  (mode extractif, signalé).
- Moteur `api` (**développement seulement**, jamais sur le poste de la Cellule) : Groq, modèle
  `llama-3.1-8b-instant`, mêmes poids que `llama3.1:8b`. Définir la clé dans une variable
  d'environnement, jamais dans un fichier du projet :
  `setx GROQ_API_KEY "votre_cle"` (Windows) ou `export GROQ_API_KEY=...` (Linux). Puis `backend: api`.
  Les réponses sont gardées en cache (`data/cache/llm`, hors Git) : un appel réussi n'est jamais refait.
- `config.yaml`, section `embeddings` : `modele` = l'encodeur retenu (Tableau 3.3). Après un changement
  d'encodeur, **reconstruire la base**.

## 4. Erreurs fréquentes

| Message ou symptôme | Cause | Solution |
|---|---|---|
| « Base absente… » | la base n'est pas construite | `python -m minpmeesa.ingestion.build` |
| « repli en mode extractif : Ollama indisponible » | Ollama n'est pas lancé, ou le modèle n'est pas installé | lancer Ollama ; `ollama list` doit afficher le modèle de `config.yaml` |
| `'python' n'est pas reconnu…` | Python absent du PATH | réinstaller Python en cochant « Add to PATH » |
| Le navigateur ne s'ouvre pas | pare-feu ou navigateur par défaut | ouvrir `http://127.0.0.1:8501` à la main |
| Réponses très lentes | modèle 8B trop lourd pour le poste | essayer `llama3.2:3b` (`llm.ollama.modele`) |
| « clé API absente : définir la variable d'environnement GROQ_API_KEY » | moteur `api` choisi sans clé | définir la clé, ou revenir à `backend: ollama` |
| Appels `api` ralentis | limite du compte gratuit atteinte | normal : le client attend la réinitialisation et met les appels en file |
| `MemoryError` à la construction | mémoire insuffisante avec bge-m3 | réduire `embeddings.taille_lot` à 4 |
| « Aucune source suffisante » trop fréquent | seuil d'abstention trop strict | relancer `run_all` sur le poste pour recalibrer le seuil |
