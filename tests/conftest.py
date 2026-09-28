"""Fixtures partagées. La base complète est construite une fois (≈ 2 min) si absente."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


@pytest.fixture(scope="session")
def base_complete():
    """Connexion à la base construite depuis data/corpus (construite si absente)."""
    from minpmeesa import config
    from minpmeesa.store import db
    if not db.chemin_base().exists():
        from minpmeesa.ingestion.build import construire
        construire(verbeux=False)
    con = db.connecter()
    yield con
    con.close()
