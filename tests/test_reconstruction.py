"""Reconstruction complète de la base depuis les 18 PDF (sans index dense,
pour rester rapide) : la base est entièrement reconstructible."""
from pathlib import Path

import pytest

from minpmeesa.ingestion.build import construire

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def base_complete(tmp_path_factory):
    d = tmp_path_factory.mktemp("reconstruction")
    r = construire(chemin_base=Path(":memory:"), dense=False, verbeux=False,
                   dossier_appariement=d / "pairing")
    return r


def test_tous_les_documents(base_complete):
    b = base_complete["base"]
    docs = {r["doc_id"]: r for r in b.documents()}
    assert len(docs) == 18
    assert {d["type"] for d in docs.values()} == {"annuaire", "rapport_analyse", "note_conjoncture", "contexte"}
    for ex in (2021, 2022, 2023, 2024):
        assert f"annuaire_{ex}" in docs and f"rapport_analyse_{ex}" in docs


def test_metadonnees_completes(base_complete):
    b = base_complete["base"]
    manques = b.q("SELECT COUNT(*) n FROM passages WHERE page IS NULL OR chapitre = '' OR section = '' "
                  "OR nature IS NULL OR texte = ''")[0]["n"]
    assert manques == 0


def test_contenu(base_complete):
    b = base_complete["base"]
    assert base_complete["valeurs"] > 10000
    assert b.q("SELECT COUNT(*) n FROM appariement WHERE exercice=2024")[0]["n"] >= 10
    assert b.q("SELECT COUNT(*) n FROM variations")[0]["n"] > 0
    # Le chiffre publié « 48,5 % » (créations CFCE 2019-2024) est retrouvé par le calcul.
    assert b.q("SELECT COUNT(*) n FROM variations WHERE exercice=2024 AND exercice_ref=2019 "
               "AND var_rel_texte='48,5'")[0]["n"] >= 1


def test_corpus_manquant_signale(base_complete):
    assert "note de conjoncture T4 2024 absente" in base_complete["manquants"]
