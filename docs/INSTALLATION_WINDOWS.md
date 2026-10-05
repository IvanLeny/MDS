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

- `config.yaml`, section `llm` : `backend: ollama` sur le poste de la Cellule (modèle `gpt-oss:20b`,
  à installer avec `ollama pull gpt-oss:20b` ; **16 Go de RAM requis**, rédaction lente sur CPU) ; `backend: none` pour travailler sans modèle de langage
  (mode extractif, signalé).
- Moteur `api` (**développement seulement**, jamais sur le poste de la Cellule) : Groq, modèle
  `openai/gpt-oss-20b`, mêmes poids ouverts que `gpt-oss:20b`. Tester : `python scripts\tester_groq.py`. Définir la clé dans une variable
  d'environnement, jamais dans un fichier du projet :
  `setx GROQ_API_KEY "votre_cle"` (Windows) ou `export GROQ_API_KEY=...` (Linux). Puis `backend: api`.
  Les réponses sont gardées en cache (`data/cache/llm`, hors Git) : un appel réussi n'est jamais refait.
- `config.yaml`, section `embeddings` : `modele` = l'encodeur retenu (Tableau 3.3). Après un changement
  d'encodeur, **reconstruire la base**.

- **Réglage propre à un poste : `config.local.yaml`** (à la racine du projet, non versionné). Il complète
  `config.yaml` sans le modifier. Exemple pour un PC de 8 Go de RAM, où `gpt-oss:20b` ne tient pas :
  ```yaml
  llm:
    ollama:
      modele: llama3.2:3b
  commentaire:
    max_valeurs_contexte: 60      # contexte plus court : rédaction environ deux fois plus rapide
    nb_modeles_redaction: 1
  ```
  Sur processeur seul, un commentaire rédigé par le modèle prend plusieurs minutes ; dans l'interface,
  au-delà de `delai_interface_s` (240 s), le commentaire est rédigé par les gabarits (repli signalé).
  Le modèle utilisé s'affiche dans la barre latérale de l'interface ; le réglage local est recopié dans les
  résultats (`config_locale`). Supprimer le fichier pour revenir au réglage du dépôt.

## 3 bis. Mesurer les modèles de langage installés (Tableau 3.2)

Ollama lancé, modèle(s) installé(s) (`ollama list`) :
```
python -m minpmeesa.evaluation.choix_llm
```
Chaque candidat Ollama de `config.yaml` installé sur le poste rédige les commentaires de 20 indicateurs ; les
autres sont déclarés « non mesuré ». Résultat : `data/results/AAAA-MM-JJ_choix_llm_poste/` (avec la machine :
cœurs, RAM). Sur un processeur à 4 cœurs, compter de l'ordre de la minute par commentaire pour un modèle de 3B.

## 4. Mesurer les encodeurs (Tableau 3.3) sur un PC de développement

Durée : téléchargements (≈ 5,5 Go en tout) puis 5 à 60 min de calcul par encodeur sur CPU. Aucun appel au
modèle de langage : pas besoin de la clé Groq.

1. Installer la bibliothèque (≈ 1 Go avec torch CPU) :
   ```bat
   pip install --timeout 120 --retries 10 sentence-transformers==6.1.0
   ```
2. Télécharger **un encodeur à la fois**, du plus léger au plus lourd. Un téléchargement interrompu reprend si
   l'on relance la même commande ; le modèle n'est déclaré présent qu'une fois complet et vérifié :
   ```bat
   python scripts\telecharger_modeles.py --etat
   python scripts\telecharger_modeles.py --modele sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
   python scripts\telecharger_modeles.py --modele dangvantuan/sentence-camembert-base
   python scripts\telecharger_modeles.py --modele intfloat/multilingual-e5-large
   python scripts\telecharger_modeles.py --modele BAAI/bge-m3
   ```
3. Comparer les encodeurs présents (la base existante suffit ; le repli est toujours mesuré comme référence) :
   ```bat
   python -m minpmeesa.evaluation.choix_encodeur
   ```
   Sortie : `data\results\<date>_encodeurs\` (`tableau_3_3_encodeurs.json`, `tableau_3_3_par_question.csv`,
   avec le test de Wilcoxon de chaque encodeur contre le repli).
4. Reporter l'encodeur retenu dans `config.yaml` (`embeddings.modele`), **reconstruire la base**, puis relancer
   l'évaluation sans modèle de langage (rapide) dans un dossier nommé. Elle recalibre aussi le seuil
   d'abstention, qui dépend de l'encodeur : ne pas utiliser l'interface entre la reconstruction et cette étape.
   ```bat
   python -m minpmeesa.ingestion.build
   python -m minpmeesa.evaluation.run_all --llm none --sortie <date>_bge-m3_sans-llm
   ```
5. Déposer les dossiers de résultats sur GitHub (`git add data/results`, `git commit`, `git push`).
   Le dossier `models\` n'est **pas** versionné (trop lourd) : le copier sur clé USB pour le poste de la Cellule.

## 5. Erreurs fréquentes

| Message ou symptôme | Cause | Solution |
|---|---|---|
| « Base absente… » | la base n'est pas construite | `python -m minpmeesa.ingestion.build` |
| « repli en mode extractif : Ollama indisponible » | Ollama n'est pas lancé, ou le modèle n'est pas installé | lancer Ollama ; `ollama list` doit afficher le modèle de `config.yaml` |
| `'python' n'est pas reconnu…` | Python absent du PATH | réinstaller Python en cochant « Add to PATH » |
| Le navigateur ne s'ouvre pas | pare-feu ou navigateur par défaut | ouvrir `http://127.0.0.1:8501` à la main |
| Réponses très lentes, ou « délai dépassé » | gpt-oss:20b sur CPU | normal (plusieurs minutes) ; si le poste a moins de 16 Go, voir `docs/ECARTS_MEMOIRE.md` E15 |
| « HTTP 404 … model_not_found » (moteur api) | modèle retiré par Groq | `python scripts\tester_groq.py --lister`, puis adapter `llm.api.modele` |
| « clé API absente : définir la variable d'environnement GROQ_API_KEY » | moteur `api` choisi sans clé | définir la clé, ou revenir à `backend: ollama` |
| Appels `api` ralentis | limite du compte gratuit atteinte | normal : le client attend la réinitialisation et met les appels en file |
| « sentence-transformers n'est pas installé » | étape 1 de la section 4 non faite | `pip install sentence-transformers==6.1.0` |
| Téléchargement interrompu (réseau) | connexion instable | relancer la même commande `--modele` : elle reprend |
| `MemoryError` à la construction | mémoire insuffisante avec bge-m3 | réduire `embeddings.taille_lot` à 4 |
| « Aucune source suffisante » trop fréquent | seuil d'abstention trop strict | relancer `run_all` sur le poste pour recalibrer le seuil |
