"""Étape 5 : note d'analyse, note stratégique, exports."""
import pytest

from minpmeesa.export import docx_export
from minpmeesa.generation import analysis_note, commentary, strategic_note
from minpmeesa.guards import literal_check as lc
from minpmeesa.retrieval.hybrid import Moteur


@pytest.fixture(scope="module")
def m(base_complete):
    return Moteur()


def test_note_analyse_assemble_sans_valeur_nouvelle(base_complete, m):
    note = analysis_note.rediger(base_complete, 2024, chapitre=r"CHAPITRE I\b", moteur=m, journaliser=False)
    assert note["sections"]
    nums = [s["tableau_n"] for s in note["sections"]]
    assert nums == sorted(nums)                           # ordre du plan de l'Annuaire
    for s in note["sections"]:
        seul = commentary.commenter(base_complete, s["code"], 2024, None, journaliser=False, moteur=m)
        assert [e["texte"] for e in s["commentaire"]["enonces"]] == [e["texte"] for e in seul["enonces"]]


def test_note_analyse_prefere_les_commentaires_valides(base_complete, m):
    code = "pme-creees-sur-periode"
    res = commentary.commenter(base_complete, code, 2024, None, journaliser=True, moteur=m)
    analysis_note.valider_production(base_complete, res["prod_id"], "test")
    v = analysis_note.commentaire_valide(base_complete, code, 2024)
    assert v and v["prod_id"] == res["prod_id"] and v["valide"]
    note = analysis_note.rediger(base_complete, 2024, codes=[code], moteur=m, journaliser=False)
    assert note["sections"][0]["valide"] and not note["commentaires_non_valides"]
    analysis_note.valider_production(base_complete, res["prod_id"], "test", "a_relire")


def test_note_strategique_bn(base_complete, m):
    note = strategic_note.rediger(base_complete, 2024, None, m, journaliser=False)
    assert 1 <= note["nb_evolutions"] <= 7
    assert list(note["rubriques"]) == strategic_note.RUBRIQUES
    v = strategic_note.verifier_bn4_bn5(note)
    assert v["BN4_toute_valeur_tracee"] and v["BN5_longueur_ok"] and v["BN5_messages_cles_3"]
    # pistes pour la décision : aucun chiffre
    assert all(not lc.nombres(b["texte"]) for b in note["rubriques"]["Pistes pour la décision"])
    # chaque variation retenue est tracée à ses deux valeurs sources
    for c in note["selection"]:
        assert sum(1 for t in note["tracabilite"] if t["code_indicateur"] == c["code"] and t["variation"]) == 2
    # un objectif n'est rattaché que s'il est documenté (avec page)
    for c in note["selection"]:
        assert c["objectif"] is None or (c["objectif"]["page"] and c["objectif"]["doc_id"])


def test_qualification_tendance():
    assert "tendance à la hausse" in strategic_note.qualifier([1.0, 2.0, 3.0], 3)
    assert "ponctuelle" in strategic_note.qualifier([1.0, -2.0, 3.0], 3)
    assert "trop court" in strategic_note.qualifier([1.0], 3)


def test_exports_word(base_complete, m, tmp_path):
    from docx import Document
    res = commentary.commenter(base_complete, "pme-creees-sur-periode", 2024, None, journaliser=False)
    p = docx_export.exporter_commentaire(res, tmp_path / "c.docx")
    texte = "\n".join(x.text for x in Document(p).paragraphs)
    assert "MODE EXTRACTIF" in texte and "21 132" in texte
    note = strategic_note.rediger(base_complete, 2024, None, m, journaliser=False)
    p = docx_export.exporter_note_strategique(note, tmp_path / "n.docx")
    t = "\n".join(x.text for x in Document(p).paragraphs)
    assert all(r in t for r in strategic_note.RUBRIQUES)
