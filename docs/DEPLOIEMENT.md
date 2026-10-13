# Déploiement d'ANALYS'PME

Deux déploiements complémentaires :

| | A. Version de démonstration en ligne | B. Installation en réseau interne (Cellule) |
|---|---|---|
| Pour qui | Le jury, tout visiteur muni de l'adresse | Les cadres de la Cellule, sur le réseau du ministère |
| Accès | **https://analyspme-minpmeesa.streamlit.app/** | `http://<adresse du poste serveur>:8501` |
| Rédaction | Gabarits seulement | Gabarits + modèle de langage local (Ollama) |
| Ajout de documents, validation | Désactivés (lecture seule) | Oui |
| Données | Corpus public du dépôt GitHub | Restent sur le poste du ministère (aucun envoi extérieur) |

---

## A. Version de démonstration en ligne (Streamlit Community Cloud, gratuit)

**En ligne depuis le 13/10/2026 : https://analyspme-minpmeesa.streamlit.app/** (branche `claude/vigilant-lamport-hi28is`, fichier `deploiement/streamlit_app.py`).

Préparé dans le dépôt : `deploiement/streamlit_app.py` (point d'entrée : mode démonstration, construction
automatique de la base au premier démarrage) et `deploiement/requirements.txt` (dépendances allégées, sans
encodeur neuronal ni modèle de langage).

1. Ouvrir **https://share.streamlit.io** et cliquer sur **« Continue with GitHub »** (compte qui possède le dépôt
   `IvanLeny/MDS`) ; autoriser l'accès demandé.
2. **« Create app »**, puis **« Deploy a public app from GitHub »**, et remplir :
   - *Repository* : `IvanLeny/MDS`
   - *Branch* : `claude/vigilant-lamport-hi28is` (ou `main` si la branche y a été fusionnée)
   - *Main file path* : `deploiement/streamlit_app.py`
   - *App URL* : par exemple `analyspme` (adresse finale : `https://analyspme.streamlit.app`)
   - **Advanced settings** → *Python version* : **3.11**
3. **« Deploy »**. Le premier démarrage prend 5 à 8 minutes : installation des paquets, puis construction de la
   base (environ 2 minutes ; mémoire maximale mesurée : environ 1 Go, puis environ 620 Mo en fonctionnement).
4. Communiquer l'adresse au jury. Chaque nouveau `git push` sur la branche met l'application à jour.

**Le jour de la soutenance** : une application gratuite se met en veille après quelques jours sans visite.
L'ouvrir 15 minutes avant la soutenance (bouton « Yes, get this app back up! » si elle dort) ; si le serveur a
été recyclé, la base est reconstruite automatiquement (environ 3 minutes).

**Ce que voit un visiteur** : accueil, les quatre services en mode gabarits, la base en exploration, la page
Validation en consultation. Un encadré « Version de démonstration » le signale dans la barre latérale.

**Si l'hébergement refuse faute de mémoire** : utiliser Hugging Face Spaces (gratuit, 16 Go de mémoire) —
*New Space* → SDK *Streamlit*, relier le dépôt GitHub, même fichier d'entrée et même `requirements.txt`.

---

## B. Installation en réseau interne de la Cellule

Un poste de la Cellule sert de serveur ; les collègues ouvrent l'outil dans leur navigateur. Rien ne sort du
réseau du ministère, conformément au mémoire.

1. **Poste serveur** : installer le prototype comme indiqué dans `docs/INSTALLATION_WINDOWS.md` (Python, `.venv`,
   dépendances, `python -m minpmeesa.ingestion.build`) ; pour le modèle de langage, Ollama et `gpt-oss:20b`
   (16 Go de RAM).
2. **Ouvrir le port 8501 dans le pare-feu Windows** (une seule fois ; invite de commandes en administrateur) :
   ```
   netsh advfirewall firewall add rule name="ANALYS'PME" dir=in action=allow protocol=TCP localport=8501 profile=domain,private
   ```
3. **Lancer** : double-clic sur **`demarrer_reseau.bat`**. La fenêtre affiche l'adresse à communiquer, par exemple
   `http://192.168.1.25:8501`.
4. **Les collègues** ouvrent cette adresse dans leur navigateur (Chrome, Edge), sur le même réseau.
5. Recommandations :
   - demander au service informatique une **adresse IP fixe** pour le poste serveur (l'adresse ne change plus) ;
   - laisser le poste allumé et la fenêtre ouverte pendant les heures de travail ;
   - ne jamais ouvrir le port 8501 vers Internet (box, routeur) : l'outil est conçu pour le réseau interne ;
   - plusieurs personnes peuvent travailler en même temps (une connexion à la base par utilisateur) ; les
     rédactions avec modèle de langage, plus lourdes, se font de préférence une à la fois.
6. **Mise à jour** : sur le poste serveur, `git pull`, puis relancer `demarrer_reseau.bat`.

`demarrer.bat` reste disponible pour un usage sur un seul poste (adresse `127.0.0.1`, inaccessible aux autres).
