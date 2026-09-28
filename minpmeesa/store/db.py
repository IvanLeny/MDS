"""Accès SQLite. Les filtres (statut de diffusion, exercice) s'écrivent dans le
WHERE des requêtes, jamais après coup (sections 3.2.4 et 3.2.5)."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

SCHEMA = Path(__file__).with_name("schema.sql")

# Métadonnées obligatoires d'un passage (Tableau 2.4).
CHAMPS_PASSAGE = ("doc_id", "page", "chapitre", "section", "nature", "texte")


class PassageIncomplet(ValueError):
    """Passage rejeté faute de métadonnées complètes (section 2.3.3)."""


class Base:
    def __init__(self, chemin: str | Path = ":memory:"):
        if str(chemin) != ":memory:":
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        self.chemin = str(chemin)
        self.conn = sqlite3.connect(self.chemin, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ #
    #  Écriture
    # ------------------------------------------------------------------ #
    def ajouter_document(self, d: dict) -> None:
        cols = ("doc_id", "titre", "type", "exercice", "trimestre",
                "statut_diffusion", "fichier", "nb_pages", "sha256")
        self.conn.execute(
            f"INSERT OR REPLACE INTO documents({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
            tuple(d.get(c) for c in cols))

    def ajouter_passage(self, p: dict) -> int:
        manquants = [c for c in CHAMPS_PASSAGE if p.get(c) in (None, "")]
        if manquants:
            raise PassageIncomplet(f"passage rejeté, métadonnées manquantes : {manquants}")
        cur = self.conn.execute(
            "INSERT INTO passages(doc_id,page,chapitre,section,nature,code_indicateur,texte,nb_tokens)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (p["doc_id"], p["page"], p["chapitre"], p["section"], p["nature"],
             p.get("code_indicateur"), p["texte"], p.get("nb_tokens", 0)))
        return int(cur.lastrowid)

    def ajouter_valeur(self, v: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO valeurs(doc_id,page,tableau_n,tableau_intitule,ligne,colonne,"
            "valeur_texte,valeur_num,unite,code_indicateur) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (v["doc_id"], v["page"], v.get("tableau_n"), v.get("tableau_intitule"),
             v["ligne"], v["colonne"], v["valeur_texte"], v.get("valeur_num"),
             v.get("unite"), v.get("code_indicateur")))
        return int(cur.lastrowid)

    def ajouter_appariement(self, a: dict) -> None:
        cols = ("code_indicateur", "exercice", "graphique_n", "graphique_intitule",
                "tableau_n", "tableau_intitule", "doc_annuaire", "passage_commentaire_id",
                "score", "statut", "valide_par", "date_validation")
        self.conn.execute(
            f"INSERT OR REPLACE INTO appariement({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
            tuple(a.get(c) for c in cols))

    def ajouter_variations(self, rows: Iterable[dict]) -> None:
        cols = ("code_indicateur", "ligne", "exercice", "exercice_ref", "valeur", "valeur_ref",
                "var_abs", "var_rel_pct", "var_abs_texte", "var_rel_texte",
                "valeur_id", "valeur_ref_id")
        self.conn.executemany(
            f"INSERT INTO variations({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
            [tuple(r.get(c) for c in cols) for r in rows])

    def journaliser(self, type_: str, entree, sortie, sources=None, ecartees=None,
                    abstentions=None, modele: str = "", config_hash: str = "",
                    duree_s: float = 0.0) -> int:
        """Écrit une production dans le journal (table productions)."""
        def js(x):
            return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
        cur = self.conn.execute(
            "INSERT INTO productions(type,entree,sortie,sources_json,valeurs_ecartees_json,"
            "abstentions_json,modele,config_hash,duree_s,horodatage) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (type_, js(entree), js(sortie), js(sources or []), js(ecartees or []),
             js(abstentions or []), modele, config_hash, round(duree_s, 3),
             datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()
        return int(cur.lastrowid)

    def valider_commentaire(self, code: str, exercice: int, enonces: list,
                            valide_par: str, prod_id: Optional[int] = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO commentaires_valides VALUES(?,?,?,?,?,?)",
            (code, exercice, prod_id, json.dumps(enonces, ensure_ascii=False), valide_par,
             time.strftime("%Y-%m-%d")))
        self.conn.commit()

    def commit(self) -> None:
        self.conn.commit()

    # ------------------------------------------------------------------ #
    #  Lecture
    # ------------------------------------------------------------------ #
    def q(self, sql: str, args: tuple = ()) -> List[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    def document(self, doc_id: str) -> Optional[sqlite3.Row]:
        r = self.q("SELECT * FROM documents WHERE doc_id=?", (doc_id,))
        return r[0] if r else None

    def documents(self) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM documents ORDER BY type, exercice, trimestre")

    def passages_publies(self) -> List[sqlite3.Row]:
        """Passages consultables : filtre de statut dans la requête (3.2.5)."""
        return self.q(
            "SELECT p.*, d.titre, d.type, d.exercice, d.trimestre FROM passages p "
            "JOIN documents d ON d.doc_id = p.doc_id "
            "WHERE d.statut_diffusion = 'publie' ORDER BY p.passage_id")

    def passages(self, ids: List[int]) -> List[sqlite3.Row]:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self.q(
            f"SELECT p.*, d.titre, d.type, d.exercice, d.trimestre, d.statut_diffusion "
            f"FROM passages p JOIN documents d ON d.doc_id = p.doc_id "
            f"WHERE p.passage_id IN ({marks})", tuple(ids))
        par_id = {r["passage_id"]: r for r in rows}
        return [par_id[i] for i in ids if i in par_id]

    def appariements(self, exercice: Optional[int] = None,
                     statuts: tuple = ("valide", "candidat")) -> List[sqlite3.Row]:
        marks = ",".join("?" * len(statuts))
        sql = f"SELECT * FROM appariement WHERE statut IN ({marks})"
        args: list = list(statuts)
        if exercice is not None:
            sql += " AND exercice = ?"
            args.append(exercice)
        return self.q(sql + " ORDER BY exercice, graphique_n", tuple(args))

    def valeurs_tableau(self, doc_id: str, tableau_n: int) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM valeurs WHERE doc_id=? AND tableau_n=? ORDER BY valeur_id",
                      (doc_id, tableau_n))

    def commentaires_anterieurs(self, code: str, exercice: int) -> List[sqlite3.Row]:
        """Commentaires publiés du même indicateur, exercices STRICTEMENT
        antérieurs (BF6) : le filtre temporel est dans le WHERE."""
        return self.q(
            "SELECT p.*, d.exercice, d.titre FROM appariement a "
            "JOIN passages p ON p.passage_id = a.passage_commentaire_id "
            "JOIN documents d ON d.doc_id = p.doc_id "
            "WHERE a.code_indicateur = ? AND a.exercice < ? AND d.exercice < ? "
            "AND a.statut != 'rejete' AND d.statut_diffusion = 'publie' "
            "ORDER BY d.exercice DESC", (code, exercice, exercice))

    def commentaires_valides(self, exercice: int) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM commentaires_valides WHERE exercice=?", (exercice,))

    def productions(self, type_: Optional[str] = None) -> List[sqlite3.Row]:
        if type_:
            return self.q("SELECT * FROM productions WHERE type=? ORDER BY prod_id", (type_,))
        return self.q("SELECT * FROM productions ORDER BY prod_id")

    def fermer(self) -> None:
        self.conn.close()
