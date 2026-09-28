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
