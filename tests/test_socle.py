"""Étape 1 : configuration, schéma, registre, reconstruction complète de la base."""
import shutil
import sqlite3

import pytest

from minpmeesa import config
from minpmeesa.ingestion import chunk, registry
from minpmeesa.store import db


def test_config_graine_et_parametres():
    cfg = config.charger()
    assert cfg["graine"] == 42
    assert cfg["llm"]["temperature"] == 0
    assert 400 <= cfg["ingestion"]["passage_tokens_min"] < cfg["ingestion"]["passage_tokens_max"] <= 800
    assert 0.10 <= cfg["ingestion"]["recouvrement"] <= 0.20


def test_schema_sqlite(tmp_path):
    con = db.connecter(tmp_path, creer=True)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"documents", "passages", "valeurs", "appariement", "variations", "productions"} <= tables
    with pytest.raises(sqlite3.IntegrityError):   # statut de diffusion contrôlé
        con.execute("INSERT INTO documents VALUES ('x','t','annuaire',2024,NULL,'secret','f',1,'h',0)")


def test_registre_complet_et_statuts():
    reg = registry.charger_registre(config.chemin("registre"))
    pdfs = {p.name for p in config.chemin("corpus").glob("*.pdf")}
    assert pdfs == set(reg), "chaque PDF du corpus doit figurer au registre"
    reels = [e for e in reg.values() if not e.test_synthetique]
    assert len(reels) == 18
    assert all(e.statut_diffusion == "publie" for e in reels)
    tests = [e for e in reg.values() if e.test_synthetique]
    assert [e.doc_id for e in tests] == ["test_interne_fictif"]
    assert tests[0].statut_diffusion == "interne"


def test_passage_incomplet_rejete():
    p = chunk.Passage("d", 1, 1, "Chap", "", "texte", "un texte " * 30)
    assert "section" in chunk.valider(p, 20)
    p.section = "S"
    assert chunk.valider(p, 20) is None
    assert "trop court" in chunk.valider(chunk.Passage("d", 1, 1, "C", "S", "texte", "court"), 20)


def _mini_corpus(dest):
    src = config.chemin("corpus")
    for f in ["note_conjoncture_T3_2024.pdf", "contexte_bulletin_2024.pdf", "test_interne_fictif.pdf"]:
        shutil.copy(src / f, dest / f)
    import yaml
    reg = yaml.safe_load((src / "registre.yaml").read_text(encoding="utf-8"))
    reg["documents"] = [d for d in reg["documents"] if (dest / d["fichier"]).exists()]
    (dest / "registre.yaml").write_text(yaml.safe_dump(reg, allow_unicode=True), encoding="utf-8")


def test_reconstruction_complete_deterministe(tmp_path):
    """La base se recrée de zéro, à l'identique, à partir des seuls PDF."""
    from minpmeesa.ingestion.build import construire
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _mini_corpus(corpus)
    empreintes = []
    for k in range(2):
        base = tmp_path / f"base{k}"
        r = construire(dossier_base=base, verbeux=False, corpus=corpus)
        assert r["nb_documents"] == 3
        con = db.connecter(base)
        n_pass = con.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
        assert n_pass > 0
        # aucun passage sans métadonnées complètes
        assert con.execute("SELECT COUNT(*) FROM passages WHERE chapitre='' OR section='' OR page IS NULL").fetchone()[0] == 0
        empreintes.append(con.execute("SELECT group_concat(texte, '|') FROM passages ORDER BY passage_id").fetchone()[0])
        assert (base / "bm25.pkl").exists() and (base / "dense.faiss").exists()
        con.close()
    assert empreintes[0] == empreintes[1]
    assert (corpus / "inventaire.csv").exists()


def test_config_locale_completer_sans_ecraser(tmp_path, monkeypatch):
    from minpmeesa import config
    (tmp_path / "config.yaml").write_text("a: 1\nllm:\n  ollama:\n    modele: gros\n    url: u\n", encoding="utf-8")
    (tmp_path / "config.local.yaml").write_text("llm:\n  ollama:\n    modele: leger\n", encoding="utf-8")
    monkeypatch.setattr(config, "RACINE", tmp_path)
    monkeypatch.delenv("MINPMEESA_CONFIG", raising=False)
    config.charger.cache_clear()
    try:
        c = config.charger()
        assert c["llm"]["ollama"] == {"modele": "leger", "url": "u"} and c["a"] == 1
        assert c["config_locale"] == {"llm": {"ollama": {"modele": "leger"}}}
        # chemin explicite : le fichier local est ignoré
        assert config.charger(str(tmp_path / "config.yaml"))["llm"]["ollama"]["modele"] == "gros"
    finally:
        config.charger.cache_clear()
