# Écarts entre le code et le mémoire v5

> Le fichier `Memoire_v5_complet.docx` n'a pas été fourni à cette session. Le prototype suit la
> spécification du document « PROMPT — Reconstruction du prototype (aligné sur le Mémoire v5) ».
> Les formulations ci-dessous sont **prêtes à coller**, sous réserve de vérifier les numéros de sections
> dans le mémoire.

## E1. Environnement de mesure (sections 3.1.4, 3.1.5, chapitre 4)

**Écart.** Les encodeurs candidats (bge-m3, e5-large, camembert) et les modèles de langage (via Ollama)
n'ont pas pu être téléchargés dans l'environnement de développement : l'accès aux serveurs de modèles
était refusé. Les mesures ont été faites avec un encodeur de repli hors ligne (TF-IDF + SVD, 256
dimensions), sans modèle de langage (mode extractif).

**Texte proposé.** « Les mesures présentées ont été obtenues avec un encodeur de repli hors ligne
(analyse sémantique latente : TF-IDF puis décomposition en valeurs singulières, 256 dimensions), les
modèles pré-entraînés n'étant pas disponibles sur le poste de mesure. Les résultats de la voie dense
constituent donc une borne basse. Les hypothèses dont la mesure suppose un modèle de langage (H1,
volet ancrage ; H2) sont à mesurer sur le poste cible, par la même commande
(`python -m minpmeesa.evaluation.run_all`). »

## E2. Taille des passages en tokens (section 2.3.3)

**Écart.** Le nombre de tokens est une approximation (mots et signes de ponctuation), et non le
découpage en sous-mots de l'encodeur, indisponible hors ligne. Dans les rapports d'analyse, la prose est
découpée **par commentaire de graphique** : les unités font souvent moins de 400 tokens (de 64 à 488 dans
le rapport 2024), pour que chaque commentaire reste une unité appariable.

**Texte proposé.** « Les passages de prose comptent de 400 à 800 tokens (mots et signes), avec un
recouvrement de 15 %. Dans les rapports d'analyse, l'unité de découpage est le commentaire d'un
graphique, quelle que soit sa longueur, afin de préserver le lien graphique–tableau–commentaire. »

## E3. Liste d'exclusion des millésimes (Tableau 3.5)

**Écart.** Le mémoire mentionne les années 2019 à 2030. Or le corpus contient des séries depuis 2010
(UPI) et 2016 (stock des PME). Les bornes retenues sont 2010-2035 (paramètre `annees_exclues`).

**Texte proposé.** « Les millésimes compris entre 2010 et 2035, non suivis du signe %, ne sont pas
traités comme des valeurs statistiques. »

## E4. Définition des couvertures (formule du 1.4.2)

**Écart.** Faute du texte exact de la formule du 1.4.2, les définitions opérationnelles retenues sont les
suivantes :
Couv = valeurs conservées après contrôle / valeurs citées avant contrôle ;
Couv_ind = indicateurs dont le commentaire conserve au moins un énoncé / indicateurs traités.
Exa = valeurs citées retrouvées dans les sources / valeurs citées.
**À aligner sur la formule du mémoire** : il suffit de modifier `evaluation/h2_controle.py` si elle diffère.

## E5. Calibration du seuil d'abstention (section 3.2.5)

**Écart.** Le mémoire prévoit un seuil « calibré sur les questions hors corpus ». Avec un seul critère
équilibré, le seuil refusait à tort 11 questions du corpus sur 52. Le critère retenu : le seuil le plus
haut qui refuse au plus 5 % des questions du corpus. Le signal retenu est le cosinus maximal de la voie
dense, choisi parmi 4 combinaisons comparées en validation croisée à 5 plis.

**Texte proposé.** « Le seuil d'abstention est calibré par validation croisée stratifiée à 5 plis sur
les 62 questions (dont 10 hors corpus). Il retient le seuil le plus élevé qui ne refuse pas plus de 5 %
des questions du corpus, puisqu'un refus à tort prive l'utilisateur d'une source, alors qu'une réponse
hors sujet ne montre que des passages sourcés. » **Réserve** : le choix du signal a été fait sur ce même
jeu. Il doit être refait avec l'encodeur définitif.

## E6. Expansion lexicale pondérée (section 3.2.5)

**Écart.** L'expansion est appliquée à la seule requête lexicale, comme prévu, mais les termes ajoutés
sont **pondérés à 0,3**. Sans pondération, elle dégradait la voie lexicale (mesure faite pendant le développement, sur une version antérieure de la base :
Succès@5 0,58 contre 0,71 sans lexique ; non reproduite dans data/results).

## E7. Score de sélection BN1

**Écart.** Le score mélange deux échelles : |var| / écart-type (sans unité) quand l'historique compte au
moins 3 points, |var_rel| en % sinon. C'est conforme au texte, mais les deux cas ne sont pas
comparables entre eux. Proposition : signaler dans le mémoire que les indicateurs à historique court sont
classés sur une autre échelle, ou normaliser |var_rel| par la médiane des écarts-types observés.

## E8. Objet commenté par la note d'analyse (section 3.5.1)

**Écart.** Pour couvrir un chapitre complet de l'Annuaire, les tableaux **sans graphique apparié** sont
commentés pour eux-mêmes (code `tableau-N`), à partir de leurs seules valeurs et variations calculées.
Les modèles de rédaction sont recherchés dans les rapports antérieurs, avec le même filtre temporel.

## E9. Table `productions`

**Ajout.** Colonnes `statut_validation` et `valide_par`, nécessaires pour que les notes n'assemblent que des
commentaires **validés** (BF9). Le statut « a_verifier » est aussi admis dans `appariement`, pour les
désaccords entre lecteurs.

## E10. Temps de réponse (H3)

**Écart.** Les temps rapportés ont été mesurés sur le poste de développement (Linux, 4 cœurs, 15,7 Go),
en mode extractif. Ils sont à refaire sur le poste cible Windows avec le modèle de langage retenu, qui
dominera le temps d'un commentaire.

## E11. (v5.1) Moteur `api` et contrainte « aucun appel réseau à l'exécution »

**Écart apparent.** Le moteur `api` (Groq) appelle un service distant, alors que le mémoire exige
l'absence d'appel réseau. Ce moteur n'est **jamais** celui du déploiement : `config.yaml` livre
`backend: ollama`, le test d'absence d'appel réseau porte sur ce réglage, et le moteur `api` exige une
clé fournie volontairement.

**Texte proposé.** « Pendant le développement, les commentaires ont pu être générés par un service
distant compatible OpenAI (Groq, modèle `openai/gpt-oss-20b`), sur les seules publications diffusées,
avec des poids ouverts identiques au modèle `gpt-oss:20b` exécuté localement par Ollama. En exploitation,
seul le moteur local est utilisé, et le poste ne fait aucun appel réseau. »

## E12. (v5.1) Mesures faites dans cette session

Le service Groq était injoignable depuis l'environnement de développement (connexion refusée par le
proxy) et aucune clé `GROQ_API_KEY` n'était définie. Ollama n'était pas installé. Par conséquent :
H1 (ancrage), H2, le côté « LLM ancré » de la référence gabarits et le Tableau 3.2 sont **non mesurés**.
Le côté « gabarits » est mesuré. Le couple initialement retenu (`llama3.1:8b` / `llama-3.1-8b-instant`, voir E15) était un
**choix arrêté par l'étudiant** (septembre 2026) : il n'est pas encore justifié par des mesures de ce
prototype. Relancer `run_all --llm api` avec la clé, puis `--llm ollama` sur le poste cible.

**Mise à jour (29/09/2026).** `run_all --llm api` a été exécuté sur le PC de l'étudiant (Groq
`openai/gpt-oss-20b`, voir E15) : H1 ancrage, H2, le côté « LLM ancré » et les lignes Groq du Tableau 3.2
sont désormais **mesurés** (`data/results/2026-09-28_api_gpt-oss-20b/`). Restent non mesurés : les lignes
Ollama du Tableau 3.2 et les temps sur le poste cible.

## E13. (v5.1) Quantification Q4_K_M de `llama3.1:8b` (candidat secondaire depuis E15)

Le nom `llama3.1:8b` dans Ollama désigne la variante quantifiée par défaut (Q4_K_M à la date de
rédaction). **À vérifier** avec `ollama show llama3.1:8b` sur le poste cible, et à reporter dans le Tableau 3.2.

## E14. (v5.1) Référence « gabarits »

Les gabarits (`--llm none`) sont des phrases déterministes construites à partir des valeurs et
variations autorisées. Ils ne reprennent pas le style des modèles de rédaction : leur ROUGE-L contre les
commentaires publiés est donc attendu faible. La comparaison vaut surtout pour la couverture et pour la
grille BN (notes stratégiques des deux versions, à noter par les lecteurs).

## E15. (v5.1, octobre 2026) Changement de modèle : `gpt-oss-20b` remplace `llama3.1:8b`

**Constat.** Le couple arrêté en septembre 2026 (`llama3.1:8b` / Groq `llama-3.1-8b-instant`) n'est plus
réalisable : Groq répond « model_not_found » pour `llama-3.1-8b-instant`, et la liste des modèles du compte
(`scripts/tester_groq.py --lister`) ne comporte plus aucun modèle Llama conversationnel. Parmi les
modèles proposés, seul `openai/gpt-oss-20b` réunit les deux conditions du mémoire : **poids ouverts**
(licence Apache 2.0) et **même modèle exécutable localement par Ollama** (`gpt-oss:20b`).

**Choix retenu (option A, décision de l'étudiant).** `api` = Groq `openai/gpt-oss-20b` (développement) ;
`ollama` = `gpt-oss:20b` (déploiement) ; borne haute non déployable : `openai/gpt-oss-120b`.

**Conséquences à reporter.** Le modèle compte 20 milliards de paramètres (architecture à mélange d'experts)
au lieu de 8 : le poste de la Cellule doit disposer de **16 Go de RAM** (la borne basse de 8 Go du
chapitre 2.2.2 ne suffit plus), et la rédaction d'un commentaire sur CPU prend plusieurs minutes.
Format de quantification : celui distribué par Ollama pour `gpt-oss:20b` (à relever avec
`ollama show gpt-oss:20b`), et non Q4_K_M.

**Texte proposé (Tableau 3.2 et 3.1.4).** « Le modèle de langage retenu est gpt-oss-20b (poids ouverts,
licence Apache 2.0). Pendant le développement, il est appelé via le service Groq (`openai/gpt-oss-20b`) ;
en exploitation, les mêmes poids sont exécutés localement par Ollama (`gpt-oss:20b`), sans connexion
réseau. Ce choix remplace llama3.1:8b, retiré du catalogue du service de développement ; il exige un poste
de 16 Go de mémoire vive. llama3.1:8b reste comparé comme candidat local plus léger. »

## E16. Version de Python du poste de mesure

**Écart.** Le mémoire prévoit Python 3.11. Le poste Windows de l'étudiant, qui a servi aux mesures
avec le moteur `api`, utilise Python 3.12 (3.11 non installé). La reconstruction de la base y donne
exactement les mêmes effectifs que sous Linux (904 passages, 16 211 valeurs, 572 variations,
58 appariements dont 10 « a_verifier »). La construction est donc reproductible d'un système à l'autre.

**Texte proposé.** « Le prototype a été développé pour Python 3.11 et exécuté sous Python 3.12 (Windows)
et 3.11 (Linux). Les deux systèmes produisent une base identique. »

## E17. Critère H2 « ≥ 1 valeur non soutenue sans contrôle »

**Constat.** Avec `openai/gpt-oss-20b` ancré sur les valeurs autorisées, l'exercice 2024 ne produit **aucune**
valeur non soutenue avant contrôle (0 sur 120). Le critère, qui sert à montrer que le contrôle est
nécessaire, n'est donc pas atteint en 2024. Il l'est en 2023 (2 sur 112, retirées par le contrôle). Appliquée
à la lettre, la règle du Tableau 4.1 classe H2 « non validée ». Le résultat n'a pas été ajusté.

**Texte proposé (4.4 / 4.6).** « Le critère de sûreté (aucune valeur non soutenue après contrôle) est atteint
sur les deux exercices. En revanche, le modèle ancré ne commet aucune erreur de citation sur l'exercice 2024 :
l'utilité du contrôle n'y est pas démontrée par l'échantillon, alors qu'elle l'est sur 2023 (2 valeurs sur 112)
et sur la borne haute gpt-oss-120b (3,3 % de valeurs écartées). H2 est donc déclarée non validée au sens strict
de la règle fixée a priori. Le contrôle reste un garde-fou dont le coût mesuré est faible (couverture de 98 à
100 %). » **À décider par l'étudiant** : conserver ce verdict strict, ou juger H2 sur les deux exercices
réunis (2 valeurs non soutenues sur 232 avant contrôle, 0 après), en le déclarant comme un écart au protocole.

## E18. Choix de l'encodeur et mesure de H1 sur le même jeu de questions

**Constat.** L'encodeur est retenu d'après son Succès@5 et son MRR sur les 52 questions du corpus, et H1 est
ensuite mesurée sur ces mêmes questions. Le score de l'encodeur retenu est donc légèrement **optimiste**
(biais de sélection), d'autant plus que les candidats sont nombreux et les écarts faibles.

**Parades mises en place.** (1) Le repli hors ligne est toujours mesuré comme référence, et chaque candidat lui
est comparé question par question (Wilcoxon, `tableau_3_3_par_question.csv`) : un écart non significatif ne
justifie pas de conclure à la supériorité d'un encodeur. (2) Le choix se fait **a priori** en faveur de bge-m3
(Tableau 3.3 du mémoire), sauf si un autre candidat fait significativement mieux. (3) Les questions que
poseront les cadres (tâche de l'étudiant) serviront de **jeu de test indépendant**, jamais utilisé pour choisir.

**Texte proposé.** « L'encodeur a été choisi sur le jeu de développement de 52 questions. Pour limiter le biais
de sélection, le choix par défaut (bge-m3) n'est remplacé que si un autre candidat l'améliore
significativement (Wilcoxon apparié, 5 %), et H1 est confirmée sur les questions formulées par les cadres,
qui n'ont servi à aucun réglage. »

## E19. Environnement de mesure des encodeurs (Tableau 3.3)

**Constat.** Le PC de l'étudiant ne peut pas télécharger les encodeurs (connexion d'environ 7 ko/s). La mesure
a été faite sur **Google Colab, sur CPU** (2 cœurs virtuels) : aucun GPU n'a été attribué au compte gratuit. Le
calcul a été lancé en arrière-plan, chaque encodeur étant enregistré dès sa fin (reprise possible après coupure).
Une première tentative, lancée au premier plan, avait été interrompue par la fermeture de la session Colab.

**Garanties.** Même branche du dépôt ; base reconstruite à l'identique (904 passages, 16 211 valeurs,
572 variations, 58 appariements, vérifiés dans `build_rapport.json`) ; les scores (Succès@5, MRR) ne dépendent
pas de la machine. Seuls les **temps d'indexation** sont propres à Colab (CPU partagé) ; ils donnent un ordre de
grandeur pour un poste sans GPU.

**Texte proposé.** « Les encodeurs ont été comparés sur une machine Google Colab (processeur seul), la base étant
reconstruite à l'identique depuis le dépôt. Les métriques de récupération ne dépendent pas du matériel ; les
temps d'indexation rapportés ne valent que pour cette machine. »
