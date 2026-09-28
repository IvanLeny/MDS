-- Schéma SQLite du prototype (mémoire v5, section 3.1 et Tableau 2.4).
-- Aucune installation de serveur : la base tient dans un fichier copiable.

CREATE TABLE IF NOT EXISTS documents(
    doc_id           TEXT PRIMARY KEY,
    titre            TEXT NOT NULL,
    type             TEXT NOT NULL CHECK (type IN ('annuaire','rapport_analyse','note_conjoncture','contexte')),
    exercice         INTEGER NOT NULL,
    trimestre        TEXT,
    statut_diffusion TEXT NOT NULL CHECK (statut_diffusion IN ('publie','interne')),
    fichier          TEXT NOT NULL,
    nb_pages         INTEGER NOT NULL,
    sha256           TEXT NOT NULL
);

-- Un passage sans métadonnées complètes est rejeté (section 2.3.3) :
-- doc_id, page, chapitre, section, nature et texte sont obligatoires.
CREATE TABLE IF NOT EXISTS passages(
    passage_id      INTEGER PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id),
    page            INTEGER NOT NULL CHECK (page >= 1),
    chapitre        TEXT NOT NULL CHECK (length(chapitre) > 0),
    section         TEXT NOT NULL CHECK (length(section) > 0),
    nature          TEXT NOT NULL CHECK (nature IN ('texte','tableau','graphique')),
    code_indicateur TEXT,
    texte           TEXT NOT NULL CHECK (length(texte) > 0),
    nb_tokens       INTEGER NOT NULL
);

-- Triplets (valeur, ligne, colonne) des tableaux (section 3.2.2).
CREATE TABLE IF NOT EXISTS valeurs(
    valeur_id        INTEGER PRIMARY KEY,
    doc_id           TEXT NOT NULL REFERENCES documents(doc_id),
    page             INTEGER NOT NULL,
    tableau_n        INTEGER,
    tableau_intitule TEXT,
    ligne            TEXT NOT NULL,
    colonne          TEXT NOT NULL,
    valeur_texte     TEXT NOT NULL,
    valeur_num       REAL,
    unite            TEXT,
    code_indicateur  TEXT
);

CREATE TABLE IF NOT EXISTS appariement(
    code_indicateur        TEXT NOT NULL,
    exercice               INTEGER NOT NULL,
    graphique_n            INTEGER,
    graphique_intitule     TEXT,
    tableau_n              INTEGER,
    tableau_intitule       TEXT,
    doc_annuaire           TEXT,
    passage_commentaire_id INTEGER,
    score                  REAL,
    statut                 TEXT NOT NULL CHECK (statut IN ('candidat','valide','rejete')),
    valide_par             TEXT,
    date_validation        TEXT,
    PRIMARY KEY (code_indicateur, exercice)
);

-- Chaque variation garde les deux identifiants de valeurs sources (3.3.3).
CREATE TABLE IF NOT EXISTS variations(
    code_indicateur TEXT NOT NULL,
    ligne           TEXT NOT NULL,
    exercice        INTEGER NOT NULL,
    exercice_ref    INTEGER NOT NULL,
    valeur          REAL NOT NULL,
    valeur_ref      REAL NOT NULL,
    var_abs         REAL NOT NULL,
    var_rel_pct     REAL,
    var_abs_texte   TEXT NOT NULL,
    var_rel_texte   TEXT,
    valeur_id       INTEGER NOT NULL REFERENCES valeurs(valeur_id),
    valeur_ref_id   INTEGER NOT NULL REFERENCES valeurs(valeur_id)
);

-- Journal de toutes les sorties (alimente le chapitre 4).
CREATE TABLE IF NOT EXISTS productions(
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
    horodatage            TEXT NOT NULL
);

-- Commentaires validés par un cadre (point de départ des notes, 3.5).
CREATE TABLE IF NOT EXISTS commentaires_valides(
    code_indicateur TEXT NOT NULL,
    exercice        INTEGER NOT NULL,
    prod_id         INTEGER REFERENCES productions(prod_id),
    enonces_json    TEXT NOT NULL,
    valide_par      TEXT NOT NULL,
    date_validation TEXT NOT NULL,
    PRIMARY KEY (code_indicateur, exercice)
);

CREATE INDEX IF NOT EXISTS idx_passages_doc  ON passages(doc_id);
CREATE INDEX IF NOT EXISTS idx_passages_code ON passages(code_indicateur);
CREATE INDEX IF NOT EXISTS idx_valeurs_doc   ON valeurs(doc_id, tableau_n);
CREATE INDEX IF NOT EXISTS idx_valeurs_code  ON valeurs(code_indicateur);
CREATE INDEX IF NOT EXISTS idx_var_code      ON variations(code_indicateur, exercice);
