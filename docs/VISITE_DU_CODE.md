# Visite du code — si le jury demande « montrez-nous le code »

## 1. Ouvrir le projet (avant la soutenance)

- Installer **Visual Studio Code** (gratuit), puis, dans le terminal du projet :
  `code C:\Users\IvanLeny\Documents\MDS`
- Ouvrir à l'avance les 5 fichiers de la section 3, chacun dans un onglet.
- Raccourcis utiles : **Ctrl + P** (ouvrir un fichier par son nom), **Ctrl + G** (aller à la ligne),
  **Ctrl + clic** sur une fonction (aller à sa définition), **Ctrl + Maj + F** (chercher dans tout le projet).

## 2. Le plan du code (environ 7 500 lignes de Python, 120 tests)

| Dossier | Rôle | Chapitre du mémoire |
|---|---|---|
| `minpmeesa/ingestion/` | Lecture des PDF, découpage en passages, extraction des tableaux, appariement graphique ↔ tableau, construction de la base | 2.3, 3.2 |
| `minpmeesa/store/` | Base SQLite, index FAISS, encodeurs | 3.2 |
| `minpmeesa/retrieval/` | Recherche hybride (BM25 + vecteurs, fusion RRF), abstention, contexte d'un indicateur | 3.2.5, H1 |
| `minpmeesa/compute/` | Calcul des variations par le programme (jamais par le modèle) | 3.3.3 |
| `minpmeesa/guards/` | **Contrôle de citation littérale**, normalisation des nombres, traçabilité | 3.3.4, H2 |
| `minpmeesa/generation/` | Commentaire, note d'analyse, note stratégique, appel au modèle de langage | 3.3, 3.5 |
| `minpmeesa/evaluation/` | Mesures H1, H2, H3, choix de l'encodeur et du modèle | Chapitre 4 |
| `minpmeesa/app/` | Interface Streamlit | 3.4 |
| `tests/` | Tests automatiques | — |
| `config.yaml` | Tous les paramètres (k = 60, seuils, modèles) : rien n'est caché dans le code | — |

## 3. Les 5 endroits à montrer (dans cet ordre)

1. **Le cœur de H2 : le contrôle de citation** — `minpmeesa/guards/literal_check.py`, fonction `controler`
   (ligne 175). Chaque nombre d'un texte produit est cherché parmi les valeurs autorisées (cellules du tableau,
   variations calculées) ; s'il n'y est pas, il est retiré et consigné dans « valeurs écartées ».
   La fonction `trouver` (ligne 134) choisit la bonne source quand plusieurs cellules ont la même valeur.
2. **La recherche hybride (H1)** — `minpmeesa/retrieval/hybrid.py` : `rechercher` (ligne 99) interroge les
   deux voies ; `fusion_rrf` (ligne 141) les fusionne par rangs réciproques (k = 60, fixé a priori dans
   `config.yaml`) ; `signal_confiance` (ligne 130) donne le signal d'abstention.
3. **L'abstention** — `minpmeesa/retrieval/consultation.py`, fonction `consulter` (ligne 110) : si le signal
   est sous le seuil calibré, l'outil refuse et propose des reformulations ; il ne répond jamais sans source.
4. **Les variations calculées par le programme** — `minpmeesa/compute/variations.py`, fonction `calculer`
   (ligne 63) : taux d'évolution et écarts calculés en Python, puis stockés avec les identifiants des deux
   valeurs de l'Annuaire. Le modèle de langage ne calcule rien.
5. **Le commentaire** — `minpmeesa/generation/commentary.py`, fonction `commenter` (ligne 291) : contexte de
   l'indicateur → modèle de langage (ou gabarits, fonction `extractif`, ligne 175) → contrôle littéral →
   traçabilité ; si la réponse du modèle est inexploitable, repli signalé sur les gabarits.

## 4. Démonstrations en direct (si on vous le demande)

Dans le terminal `(.venv)` du projet :

- **Les tests passent** (environ 2 minutes) : `python -m pytest -q` → « 120 passed ».
- **Un test précis**, par exemple qu'une valeur inventée est écartée :
  `python -m pytest -q tests/test_commentaire.py -k inventee`
  (le test donne au contrôle un texte avec « 25 000 PME », absent de l'Annuaire : la valeur est retirée).
- **Le contrôle sur un exemple** (dans `python`) :
  ```python
  from minpmeesa.guards import literal_check as lc
  aut = [{"texte": "21 132", "source": {"nature": "valeur"}}]
  r = lc.controler([{"type": "constat", "texte": "Les CFCE ont enregistré 21 132 PME, et 30 000 en 2025."}], aut)
  [e["valeur"] for e in r.ecartees]   # -> ['30 000'] : absent de l'Annuaire, écarté
  [e["texte"] for e in r.enonces]     # -> ['Les CFCE ont enregistré 21 132 PME.'] : la phrase est réparée
  ```

## 5. Questions probables et réponses courtes

- **« Qui a écrit le code ? »** — Répondez honnêtement : l'architecture, les choix méthodologiques (contrôle
  littéral, variations calculées, abstention, protocole d'évaluation) et la validation sont les vôtres ;
  l'écriture a été assistée par un outil d'IA, ce qui est cohérent avec le sujet. L'important est de savoir
  **expliquer chaque bloc** : c'est l'objet de ce guide.
- **« Comment êtes-vous sûr qu'aucun chiffre n'est inventé ? »** — Par construction (section 3, point 1) et
  par les tests ; tout chiffre affiché a une source cliquable (tableau, page).
- **« Pourquoi k = 60 ? »** — Valeur usuelle de la littérature (RRF), fixée avant les mesures et non réajustée
  (`config.yaml`) ; k = 10 donnait un MRR un peu meilleur, mais le changer après coup serait du sur-ajustement.
- **« Pourquoi SQLite et FAISS plutôt que PostgreSQL ? »** — Un fichier, sans serveur, installable hors
  ligne sur le poste de la Cellule ; volume modeste (moins de 1 000 passages).
- **« Que se passe-t-il si le modèle de langage se trompe ? »** — Le contrôle retire la valeur ; si le texte
  devient trop pauvre, le commentaire est rédigé par les gabarits, et c'est signalé.
- **« Comment ajouter un nouvel Annuaire ? »** — Page Base documentaire : ajouter le PDF, la base est
  reconstruite automatiquement.
