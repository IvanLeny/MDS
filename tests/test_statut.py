"""Filtre de statut : aucun document interne en consultation.

Le document interne est SYNTHÉTIQUE et clairement nommé (test_interne_fictif.pdf),
fabriqué pour le test ; il n'appartient pas au corpus et n'entre dans aucune mesure.
"""
import shutil
from pathlib import Path

import pymupdf
import pytest

from minpmeesa.ingestion.build import construire
from minpmeesa.retrieval.consultation import consulter
from minpmeesa.retrieval.hybrid import Recherche
from minpmeesa.store.bm25_index import IndexBM25
from minpmeesa.retrieval.text import tokens

RACINE = Path(__file__).resolve().parent.parent
PHRASE = ("Le chiffre secret de la cellule zorglub est de 777 777 entreprises fictives "
          "zorglub zorglub pour la note interne de simulation.")


def fabriquer_interne(chemin: Path):
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), "DOCUMENT DE TEST SYNTHETIQUE - NE PAS DIFFUSER - juin 2024", fontsize=11)
        page.insert_textbox(pymupdf.Rect(72, 100, 520, 700), (PHRASE + " ") * 6, fontsize=10)
    doc.save(chemin)


@pytest.fixture(scope="module")
def base_mixte(tmp_path_factory):
    d = tmp_path_factory.mktemp("corpus")
    shutil.copy(RACINE / "data/corpus/contexte_bulletin_2024.pdf", d)
    fabriquer_interne(d / "test_interne_fictif.pdf")
    (d / "registre_corrections.yaml").write_text(
        "documents:\n  test_interne_fictif.pdf:\n    doc_id: test_interne_fictif\n"
        "    titre: Document interne fictif (test)\n    statut_diffusion: interne\n", encoding="utf-8")
    r = construire(corpus=d, chemin_base=Path(":memory:"), dense=False, verbeux=False,
                   dossier_appariement=d / "pairing")
    return r["base"]


def test_document_interne_bien_enregistre(base_mixte):
    doc = base_mixte.document("test_interne_fictif")
    assert doc is not None and doc["statut_diffusion"] == "interne"
    assert base_mixte.q("SELECT COUNT(*) n FROM passages WHERE doc_id='test_interne_fictif'")[0]["n"] > 0


def test_aucun_passage_interne_consultable(base_mixte):
    ids = {r["doc_id"] for r in base_mixte.passages_publies()}
    assert ids and "test_interne_fictif" not in ids


def test_consultation_ne_restitue_jamais_l_interne(base_mixte):
    rows = base_mixte.passages_publies()
    bm25 = IndexBM25([r["passage_id"] for r in rows], [tokens(r["texte"]) for r in rows])
    rech = Recherche(base_mixte, bm25, None)
    rep = consulter(rech, "chiffre secret zorglub entreprises fictives", mode="lexicale", journal=False)
    assert all(s.doc_id != "test_interne_fictif" for s in rep.sources)
    # La requête ne porte que sur le document interne : le système s'abstient.
    assert rep.abstention
