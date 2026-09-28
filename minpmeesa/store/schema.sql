-- Schéma SQLite du prototype (mémoire v5, Tableaux 2.4 et 3.1).
-- Une base = un fichier ; aucun serveur, aucun mot de passe.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    doc_id           TEXT PRIMARY KEY,
    titre            TEXT NOT NULL,
    type             TEXT NOT NULL CHECK (type IN ('annuaire','rapport_analyse','note_conjoncture','contexte')),
    exercice         INTEGER NOT NULL,
    trimestre        TEXT,
    statut_diffusion TEXT NOT NULL CHECK (statut_diffusion IN ('publie','interne')),
    fichier          TEXT NOT NULL,
    nb_pages         INTEGER NOT NULL,
    sha256           TEXT NOT NULL,
    test_synthetique INTEGER NOT NULL DEFAULT 0   -- 1 = document de test exclu des mesures
);

CREATE TABLE IF NOT EXISTS passages (
    passage_id       INTEGER PRIMARY KEY,
    doc_id           TEXT NOT NULL REFERENCES documents(doc_id),
    page             INTEGER NOT NULL,
    page_fin         INTEGER NOT NULL,
    chapitre         TEXT NOT NULL,
    section          TEXT NOT NULL,
    nature           TEXT NOT NULL CHECK (nature IN ('texte','tableau','graphique')),
    code_indicateur  TEXT,
    numero           INTEGER,            -- n° du tableau ou du graphique, le cas échéant
    texte            TEXT NOT NULL,
    nb_tokens        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS valeurs (
    valeur_id        INTEGER PRIMARY KEY,
    doc_id           TEXT NOT NULL REFERENCES documents(doc_id),
    page             INTEGER NOT NULL,
    tableau_n        INTEGER,
    tableau_intitule TEXT,
    ligne            TEXT NOT NULL,
    colonne          TEXT NOT NULL,
    annee_colonne    INTEGER,            -- millésime lu dans l'en-tête de colonne
    sous_colonne     TEXT,               -- ex. « Effectif », « % »
    valeur_texte     TEXT NOT NULL,
    valeur_num       REAL,
    unite            TEXT,
    code_indicateur  TEXT
);

CREATE TABLE IF NOT EXISTS appariement (
    code_indicateur        TEXT NOT NULL,
    exercice               INTEGER NOT NULL,
    graphique_n            INTEGER,
    graphique_intitule     TEXT,
    tableau_n              INTEGER,
    tableau_intitule       TEXT,
    doc_annuaire           TEXT,
    doc_rapport            TEXT,
    passage_commentaire_id INTEGER,
    score                  REAL,
    statut                 TEXT NOT NULL CHECK (statut IN ('candidat','valide','rejete','a_verifier')),
    valide_par             TEXT,
    date_validation        TEXT,
    PRIMARY KEY (code_indicateur, exercice)
);

CREATE TABLE IF NOT EXISTS variations (
    code_indicateur  TEXT NOT NULL,
    exercice         INTEGER NOT NULL,
    exercice_ref     INTEGER NOT NULL,
    ligne            TEXT NOT NULL,
    sous_colonne     TEXT,
    valeur           REAL NOT NULL,
    valeur_ref       REAL NOT NULL,
    var_abs          REAL NOT NULL,
    var_abs_texte    TEXT NOT NULL,
    var_rel_pct      REAL,
    var_rel_texte    TEXT,
    unite            TEXT,
    valeur_id        INTEGER NOT NULL REFERENCES valeurs(valeur_id),
    valeur_ref_id    INTEGER NOT NULL REFERENCES valeurs(valeur_id)
);

CREATE TABLE IF NOT EXISTS productions (
    prod_id               INTEGER PRIMARY KEY,
    type                  TEXT NOT NULL CHECK (type IN ('consultation','commentaire','note_analyse','note_strategique')),
    entree                TEXT NOT NULL,
    sortie                TEXT NOT NULL,
    sources_json          TEXT,
    valeurs_ecartees_json TEXT,
    abstentions_json      TEXT,
    modele                TEXT,
    config_hash           TEXT,
    duree_s               REAL,
    horodatage            TEXT NOT NULL,
    statut_validation     TEXT NOT NULL DEFAULT 'a_relire' CHECK (statut_validation IN ('a_relire','valide','rejete')),
    valide_par            TEXT
);

CREATE INDEX IF NOT EXISTS idx_passages_doc  ON passages(doc_id);
CREATE INDEX IF NOT EXISTS idx_passages_code ON passages(code_indicateur);
CREATE INDEX IF NOT EXISTS idx_valeurs_doc   ON valeurs(doc_id, tableau_n);
CREATE INDEX IF NOT EXISTS idx_valeurs_code  ON valeurs(code_indicateur);
CREATE INDEX IF NOT EXISTS idx_variations    ON variations(code_indicateur, exercice);
