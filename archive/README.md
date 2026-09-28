# Archive de l'ancien prototype

Éléments repris du dépôt `IvanLeny/Modele_de_reconnaissance_facial`, branche
`claude/rag-system-memoir-ra02r7`, et **abandonnés** par le prototype aligné sur le mémoire v5 :

- `rag_minpmeesa/` : ancienne génération du système ;
- `src_ancien/` : ancien code canonique. Certains modules ont été relus et repris dans
  `minpmeesa/` (détection de l'exercice, extraction, tableaux, garde-fous, métriques) ;
- `postgres/` : PostgreSQL/pgvector (`pg_store.py`, `ingest_postgres.py`, `schema_pg.sql`).
  Le mémoire (Tableaux 3.1 et 3.4) retient SQLite et FAISS sur disque, sans serveur ;
- `src.rar`, `data.rar` : archives d'origine ;
- `pairing_candidats_ancien/` : anciennes tables d'appariement, toutes au statut
  « candidat » et en partie fausses (ex. 2024, graphique 2 apparié au tableau 17).
  Elles sont remplacées par `data/pairing/`.

Rien dans ce dossier n'est importé par le prototype.
