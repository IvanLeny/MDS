"""Accès à la base SQLite (un fichier, sans serveur)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .. import config

SCHEMA = Path(__file__).with_name("schema.sql")
NOM_BASE = "minpmeesa.sqlite"


def chemin_base(dossier: Path | None = None) -> Path:
    return (dossier or config.chemin("base")) / NOM_BASE


def connecter(dossier: Path | None = None, creer: bool = False) -> sqlite3.Connection:
    """Ouvre la base. `creer=True` applique le schéma (base vide)."""
    p = chemin_base(dossier)
    if not creer and not p.exists():
        raise FileNotFoundError(
            f"Base absente ({p}). Lancez : python -m minpmeesa.ingestion.build")
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if creer:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con


# ------------------------------------------------------------------ écriture
def inserer(con: sqlite3.Connection, table: str, ligne: dict) -> int:
    cles = list(ligne)
    sql = f"INSERT INTO {table} ({','.join(cles)}) VALUES ({','.join('?' * len(cles))})"
    return con.execute(sql, [ligne[k] for k in cles]).lastrowid


def inserer_plusieurs(con: sqlite3.Connection, table: str, lignes: Iterable[dict]) -> int:
    lignes = list(lignes)
    if not lignes:
        return 0
    cles = list(lignes[0])
    sql = f"INSERT INTO {table} ({','.join(cles)}) VALUES ({','.join('?' * len(cles))})"
    con.executemany(sql, [[l[k] for k in cles] for l in lignes])
    return len(lignes)


def journaliser(con: sqlite3.Connection, type_: str, entree: dict, sortie: dict,
                sources=None, ecartees=None, abstentions=None, modele: str = "",
                duree_s: float = 0.0) -> int:
    """Journal de toutes les productions (alimente le chapitre 4)."""
    pid = inserer(con, "productions", {
        "type": type_,
        "entree": json.dumps(entree, ensure_ascii=False),
        "sortie": json.dumps(sortie, ensure_ascii=False),
        "sources_json": json.dumps(sources or [], ensure_ascii=False),
        "valeurs_ecartees_json": json.dumps(ecartees or [], ensure_ascii=False),
        "abstentions_json": json.dumps(abstentions or [], ensure_ascii=False),
        "modele": modele,
        "config_hash": config.config_hash(),
        "duree_s": round(duree_s, 3),
        "horodatage": datetime.now().isoformat(timespec="seconds"),
    })
    con.commit()
    return pid


# ------------------------------------------------------------------ lecture
def documents(con, statut: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM documents"
    args: list = []
    if statut:
        sql += " WHERE statut_diffusion = ?"
        args.append(statut)
    return con.execute(sql + " ORDER BY type, exercice, trimestre", args).fetchall()


def passage(con, passage_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT p.*, d.titre, d.type, d.exercice, d.statut_diffusion, d.fichier "
        "FROM passages p JOIN documents d USING(doc_id) WHERE passage_id = ?",
        (passage_id,)).fetchone()


def ids_passages_autorises(con, statut: str = "publie", exercice_max: int | None = None,
                           types: tuple[str, ...] | None = None,
                           exclure_tests: bool = False) -> list[int]:
    """Identifiants des passages admissibles. Le filtre est appliqué DANS la
    requête SQL ; la recherche n'est ensuite menée que sur ces identifiants."""
    sql = ("SELECT p.passage_id FROM passages p JOIN documents d USING(doc_id) "
           "WHERE d.statut_diffusion = ?")
    args: list = [statut]
    if exercice_max is not None:
        sql += " AND d.exercice <= ?"
        args.append(exercice_max)
    if types:
        sql += f" AND d.type IN ({','.join('?' * len(types))})"
        args.extend(types)
    if exclure_tests:
        sql += " AND d.test_synthetique = 0"
    return [r[0] for r in con.execute(sql, args)]
