# Plan d'amélioration du prototype ANALYS'PME

Établi le 01/10/2026 après examen des sorties réelles du prototype (note stratégique 2024, note d'analyse du
chapitre I, commentaires, interface). Chaque point part d'un **constat vérifié** et fixe un **critère
d'acceptation** contrôlable. Ordre d'exécution : celui de la liste ; on ne passe au point suivant que lorsque
le critère du point en cours est atteint, testé et déposé sur GitHub.

Règle constante : aucun chiffre inventé. Toute amélioration de forme conserve la traçabilité de chaque valeur.

---

## Lot A — Fiabilité des chiffres (priorité absolue : un membre du jury peut vérifier une source)

### A1. Traçabilité exacte des variations — **défaut constaté**
- **Constat.** « Par rapport à 2023, ce total progresse de 7,5 % » est rattaché à la variation de **Yaoundé**
  (valeurs n° 10373/10372) au lieu de celle du **Total** (n° 10445/10444) : trois lignes du tableau 7 ont la même
  variation (7,5 %), et le rattachement prend la première trouvée. Même cas : « total +12,8 % » rattaché à « PME ».
- **Amélioration.** La phrase produite porte la variation qu'elle utilise (identifiants des deux valeurs) dès sa
  construction ; en cas d'égalité de valeur, le contrôle préfère la ligne nommée dans la phrase (ou « Total »).
- **Critère.** Sur les 13 indicateurs 2024, toute variation citée a pour source la ligne dont parle la phrase ;
  test automatique ajouté sur le cas Yaoundé/Douala/Total.

### A2. Ligne pertinente pour l'indicateur — **défaut constaté**
- **Constat.** Indicateur « VA des PME par typologie » (tableau 16) : le texte parle de « Stock des PME » (+12,8 %),
  car le tableau contient les deux lignes. L'évolution « la plus marquée » est choisie sans regarder le sujet de
  l'indicateur ; de même « Masculin » pour les UPA par région.
- **Amélioration.** Ligne principale = celle dont le libellé correspond à l'intitulé du graphique (VA, stock,
  créations…), sinon « Total ». L'évolution la plus marquée est cherchée parmi les lignes de **la même
  dimension** que l'indicateur (régions pour un indicateur régional), avec un effectif minimal.
- **Critère.** Les 6 indicateurs de la note stratégique 2024 parlent de la grandeur annoncée par leur titre.

### A3. Nature et unité de chaque chiffre
- **Constat.** « hausse de 26,1 % » sans préciser qu'il s'agit d'un effectif ; tableaux mixtes Effectif / % ;
  montants « en millions de FCFA » non signalés.
- **Amélioration.** Chaque phrase précise effectif, part ou montant (avec l'unité du titre) ; une évolution de
  **part** s'exprime en **points de pourcentage** (var_abs), jamais en % de la part.
- **Critère.** Aucune variation relative calculée sur une colonne « % » dans les sorties ; unité présente pour
  les montants.

### A4. Libellés hors contexte
- **Constat.** « l'évolution la plus marquée concerne « Primaire » », « « Art » » : le lecteur ne sait pas de quoi.
- **Amélioration.** Toujours « le secteur primaire (stock de PME) », « l'artisanat d'art (UPA) » : libellé + dimension
  + grandeur, construits à partir du titre du tableau.
- **Critère.** Relecture des messages clés : chacun se comprend sans le tableau sous les yeux.

## Lot B — Qualité de la note stratégique (le livrable phare)

### B1. Messages clés non répétitifs et hiérarchisés
- **Constat.** Les 3 messages commencent tous par « Par rapport à 2023, l'évolution la plus marquée concerne… ».
- **Amélioration.** 3 messages de structures différentes : (1) le fait principal de l'exercice (niveau et
  évolution du total), (2) la dynamique la plus forte, (3) le point de vigilance ; chacun avec son chiffre tracé.
- **Critère.** Aucun début de phrase identique entre deux messages ; chacun cite au moins un chiffre sourcé.

### B2. Pistes pour la décision différenciées
- **Constat.** 6 pistes sur deux modèles de phrase (« Poursuivre le suivi… », « Examiner les causes… »).
- **Amélioration.** Pistes typées (consolider / corriger / approfondir / cibler un territoire ou un secteur),
  rattachées à l'évolution et, s'il existe, à l'objectif documenté ; toujours sans chiffre (règle BN).
- **Critère.** Au moins 3 types de pistes différents sur la note 2024 ; contrôle BN4/BN5 toujours satisfait.

### B3. Encadré « chiffres clés » et note 2023
- **Amélioration.** Encadré de 4 à 6 chiffres clés en tête de note (stock, créations, UPA…), tous tracés.
  Note 2023 : expliquer pourquoi seules 2 évolutions sont retenues, ou élargir la sélection aux indicateurs
  calculables.
- **Critère.** Encadré présent dans l'interface et le Word ; note 2023 ≥ 4 évolutions ou explication explicite.

## Lot C — Interface : ce que le jury verra

### C1. Page d'accueil « tableau de bord »
- Chiffres clés de l'exercice choisi + petits graphiques d'évolution (séries des tableaux de l'Annuaire),
  chaque chiffre avec sa source ; présentation des 4 services en une ligne chacun.
- **Critère.** À l'ouverture, le jury voit en 5 secondes ce que fait l'outil et des chiffres vérifiables.

### C2. « Montrer la source » : la page du PDF avec le chiffre surligné
- Pour chaque valeur d'un commentaire, un bouton affiche la page de l'Annuaire avec la cellule **encadrée**
  (recherche du nombre sur la page, PyMuPDF).
- **Critère.** Sur un commentaire 2024, chaque valeur ouvre la bonne page avec le nombre encadré.

### C3. Graphique de l'indicateur dans « Commenter »
- La série de l'indicateur (lignes principales, années disponibles) tracée à côté du commentaire.
- **Critère.** Graphique affiché pour tout indicateur à au moins 2 années.

### C4. Consultation plus lisible
- Termes de la question surlignés dans les extraits ; filtres type de document et exercice ; en cas de refus,
  message expliquant pourquoi et suggestions de reformulation.
- **Critère.** Les 3 fonctions visibles et testées.

### C5. Mode de rédaction par défaut adapté au poste
- Si Ollama est absent, l'interface démarre en « gabarits » sans message d'erreur ; indicateur d'état clair
  (moteur, encodeur, base) dans la barre latérale.

## Lot D — Validation par la Cellule et démonstration

### D1. Page « Validation » dans l'interface
- Pour chaque appariement « candidat » : intitulé du graphique et du tableau côte à côte, valeurs, boutons
  Valider / Rejeter / À vérifier, nom du lecteur ; export vers les fichiers de double lecture (kappa).
- **Intérêt.** Simplifie la tâche de validation qui reste à faire, et montre au jury le contrôle humain.

### D2. Word soigné
- Page de garde (logo, titre, exercice, date), encadré chiffres clés, numérotation, sources en fin de note.

### D3. Scénario de démonstration de 10 minutes
- Document `docs/DEMONSTRATION.md` : enchaînement exact (question, refus hors sujet, commentaire avec source
  surlignée, note stratégique, export Word), questions préparées, captures de secours si le poste fait défaut.

---

## Hors périmètre (volontairement)
- Reformuler par le modèle de langage des textes que les gabarits produisent déjà correctement : risque sur H2.
- Ajouter des sources de données hors corpus (internet) : contraire à l'exigence « aucun appel réseau ».
- Changer k, le seuil ou l'encodeur après coup pour améliorer les scores : sur-ajustement (E18).

## Suivi

| Point | État | Commit |
|---|---|---|
| A1 | **fait** (01/10/2026), tests ajoutés | voir journal git |
| A2 | **fait** (01/10/2026), tests ajoutés | voir journal git |
| A3 | **fait** (01/10/2026), tests ajoutés | voir journal git |
| A4 | **fait** (01/10/2026), tests ajoutés | voir journal git |
| B1 | à faire | |
| B2 | à faire | |
| B3 | à faire | |
| C1 | à faire | |
| C2 | à faire | |
| C3 | à faire | |
| C4 | à faire | |
| C5 | à faire | |
| D1 | à faire | |
| D2 | à faire | |
| D3 | à faire | |
