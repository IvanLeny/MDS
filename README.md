# Aide à la décision à partir des publications statistiques du MINPMEESA

Prototype du mémoire de Master 2 MDSMS (ISSEA) d'Ivan Leny ABONDO MEMANG : *« Conception d'un
système d'aide à la décision fondé sur les publications statistiques du MINPMEESA : de la génération
assistée des commentaires à la note d'analyse stratégique »*.

**En 10 lignes, pour un non-informaticien :**

1. L'outil lit les publications du ministère (Annuaires, rapports d'analyse, notes de conjoncture, bulletins).
2. Il fonctionne sur un ordinateur de bureau, **sans Internet** et sans carte graphique.
3. **Consulter** : on pose une question en français ; il montre les 5 passages les plus utiles, avec le document et la page.
4. S'il ne trouve rien de solide, il le dit (« Aucune source suffisante… ») au lieu d'inventer.
5. **Commenter un indicateur** : il rédige le commentaire d'un tableau de l'Annuaire.
6. Il **ne recopie que des chiffres présents dans l'Annuaire**, ou des variations qu'il a calculées lui-même ; tout autre chiffre est retiré et signalé.
7. Sous chaque phrase, il indique d'où vient chaque chiffre (tableau, page).
8. **Note d'analyse** : il assemble les commentaires validés d'un chapitre, dans l'ordre de l'Annuaire.
9. **Note stratégique** : il sélectionne les 5 à 7 évolutions les plus marquantes, en 1 à 2 pages, avec des pistes pour la décision.
10. Tout s'exporte en Word ; le lancement se fait par un double-clic sur `demarrer.bat`.

## Démarrage rapide

```bash
pip install -r requirements.txt
python -m minpmeesa.ingestion.build          # reconstruit la base depuis data/corpus (≈ 2 min)
./demarrer.sh                                # ou demarrer.bat sous Windows
python -m minpmeesa.evaluation.run_all       # évaluation complète -> data/results/AAAA-MM-JJ/
python -m pytest                             # tests
```

## Où trouver quoi

| Besoin | Emplacement |
|---|---|
| Installation sur le poste de la Cellule | `docs/INSTALLATION_WINDOWS.md` |
| Utilisation (4 parcours, captures) | `docs/GUIDE_UTILISATEUR.md` |
| Nouvelle édition, validation de l'appariement | `docs/MAINTENANCE.md` |
| Difficultés et solutions (Tableau 3.6) | `docs/JOURNAL.md` |
| Écarts entre le code et le mémoire v5 | `docs/ECARTS_MEMOIRE.md` |
| Valeurs à insérer dans le mémoire | `docs/POUR_LE_MEMOIRE.md` |
| Résultats de l'évaluation | `data/results/AAAA-MM-JJ/resume.md` |
| Exemples demandés par l'encadreur | `data/outputs/` |

## État actuel (à lire)

- Les résultats sont **PROVISOIRES** tant que les tables d'appariement (`data/pairing/a_valider_20XX.xlsx`)
  n'ont pas été validées par double lecture.
- Les modèles (bge-m3, modèles de langage via Ollama) n'ont pas pu être téléchargés dans
  l'environnement de développement (accès réseau refusé) : la voie dense utilise un encodeur de repli
  hors ligne, et la rédaction se fait en **mode extractif** (gabarits), signalé dans chaque sortie.
  H1 (ancrage) et H2 sont donc « non mesurés » pour l'instant ; ils se mesurent sur le poste cible
  après `python scripts/telecharger_modeles.py`.
