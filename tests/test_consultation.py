"""Étape 3 : service de consultation (filtre de statut, abstention, fusion RRF)."""
import pytest

from minpmeesa.retrieval import consultation, hybrid
from minpmeesa.retrieval.hybrid import fusion_rrf


@pytest.fixture(scope="module")
def moteur(base_complete):
    return hybrid.Moteur()


def _ids_internes(m):
    return {r[0] for r in m.con.execute(
        "SELECT passage_id FROM passages JOIN documents USING(doc_id) WHERE statut_diffusion='interne'")}


def test_filtre_statut_dans_la_requete(moteur):
    """Aucun passage interne n'est admissible : le filtre précède le classement."""
    internes = _ids_internes(moteur)
    assert internes, "le document de test interne doit être dans la base"
    autorises = moteur.autorises("publie")
    assert not internes & set(autorises)
    for mode in ("lexicale", "dense", "hybride"):
        res = moteur.rechercher("zorglubium indice ZETA trésorerie fictif", autorises, mode=mode, k=50)
        assert not {r.passage_id for r in res} & internes


def test_document_interne_trouvable_seulement_sans_filtre(moteur):
    # Contrôle du test : sans filtre, le mot témoin retrouve bien le document interne.
    tous = [r[0] for r in moteur.con.execute("SELECT passage_id FROM passages")]
    res = moteur.recherche_lexicale("zorglubium", tous, 5)
    assert res and res[0][0] in _ids_internes(moteur)


def test_consultation_n_expose_jamais_un_document_interne(moteur):
    r = consultation.consulter("Que dit le document fictif sur le zorglubium et l'indice ZETA ?",
                               moteur, journaliser=False)
    assert all(p["doc_id"] != "test_interne_fictif" for p in r["passages"])
    assert "zorglubium" not in " ".join(p["texte"] for p in r["passages"]).lower()


def test_abstention_hors_corpus(moteur):
    r = consultation.consulter("Quelle est la capitale de l'Australie ?", moteur, journaliser=False)
    assert r["abstention"] and r["message"] == consultation.MESSAGE_ABSTENTION and r["passages"] == []


def test_restitution_sourcee(moteur):
    r = consultation.consulter("Combien de PME ont été créées dans les CFCE en 2024 ?", moteur, journaliser=False)
    assert not r["abstention"] and len(r["passages"]) == 5
    p = r["passages"][0]
    assert {"doc_id", "page", "extrait", "fichier"} <= set(p)
    assert (p["doc_id"], p["page"]) == ("rapport_analyse_2024", 9)


def test_reponse_redigee_passe_par_le_controle(moteur):
    r = consultation.consulter("Combien de PME ont été créées dans les CFCE en 2024 ?", moteur,
                               journaliser=False, rediger=True)
    assert r["reponse"] is not None and "valeurs_ecartees" in r["reponse"]
    assert r["reponse"]["valeurs_ecartees"] == []       # réponse extractive : tout est sourcé


def test_fusion_rrf():
    lex = [(1, 9.0), (2, 5.0)]
    den = [(2, 0.9), (3, 0.8)]
    r = fusion_rrf(lex, den, 60)
    assert [x.passage_id for x in r] == [2, 1, 3]
    assert r[0].score == pytest.approx(1 / 62 + 1 / 61)


def test_expansion_lexique_seulement_requete_lexicale(moteur):
    ajout = moteur.lexique.etendre("Quel est le nombre de PME ?")
    assert ajout, "le lexique doit étendre « PME »"
    assert moteur.requete_lexicale("Quel est le nombre de PME ?", expansion=False) == ["nombre", "pme"]


class _Modele:
    nom = "faux"

    def __init__(self, rep):
        self.rep = rep

    def generer(self, systeme, utilisateur, json_attendu=True):
        return self.rep


def test_repli_extractif_si_le_modele_dit_ne_pas_savoir(moteur):
    q = "Combien de PME ont été créées dans les CFCE en 2024 ?"
    r = consultation.consulter(q, moteur, journaliser=False, rediger=True,
                               client=_Modele('{"reponse": "Les extraits ne permettent pas de répondre."}'))
    assert r["reponse"]["redaction"].startswith("extractive (repli")
    r = consultation.consulter(q, moteur, journaliser=False, rediger=True, client=_Modele("pas du json"))
    assert r["reponse"]["redaction"].startswith("extractive (repli")


def test_suggestions_de_reformulation_en_cas_de_refus(moteur):
    r = consultation.consulter("combien de pme en 2024 ?", moteur, journaliser=False)
    if r["abstention"]:                              # dépend de l'encodeur de la base
        assert r["suggestions"] and all("PME" in s for s in r["suggestions"])
        for s in r["suggestions"]:                   # chaque suggestion passe le seuil
            assert not consultation.consulter(s, moteur, journaliser=False)["abstention"]
    assert consultation.suggestions("quelle est la capitale du Japon ?", moteur) == []
