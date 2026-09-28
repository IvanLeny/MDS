"""Contrôle de citation littérale (Tableau 3.5)."""
from minpmeesa.guards.literal_check import ValeurAutorisee, controler, valeurs_non_soutenues

AUTORISEES = [
    ValeurAutorisee("21 132", {"genre": "valeur", "valeur_id": 1, "page": 19, "tableau_n": 7}),
    ValeurAutorisee("19 651", {"genre": "valeur", "valeur_id": 2, "page": 19, "tableau_n": 7}),
    # Variation calculée par le programme (21 132 vs 19 651).
    ValeurAutorisee("7,5", {"genre": "variation", "valeur_id": 1, "valeur_ref_id": 2}),
    ValeurAutorisee("1 481", {"genre": "variation", "valeur_id": 1, "valeur_ref_id": 2}),
]


def test_valeur_inventee_ecartee():
    r = controler([{"type": "constat", "texte": "En 2024, 23 400 PME ont été créées dans les CFCE."}],
                  AUTORISEES)
    assert [e.valeur for e in r.ecartees] == ["23 400"]
    assert r.enonces == []                              # énoncé supprimé : plus rien à dire


def test_valeur_calculee_par_le_programme_acceptee():
    r = controler([{"type": "constat",
                    "texte": "Les créations passent de 19 651 à 21 132, soit une hausse de 7,5 %."}],
                  AUTORISEES)
    assert r.ecartees == []
    assert len(r.enonces[0].valeurs) == 3
    assert r.enonces[0].valeurs[0]["source"]["tableau_n"] == 7


def test_valeur_d_un_modele_de_redaction_anterieur_ecartee():
    # 14 229 figure dans le commentaire de 2019 (modèle de rédaction), pas dans
    # les rubriques autorisées : il est écarté.
    r = controler([{"type": "constat",
                    "texte": "En 2024, 21 132 PME ont été créées, contre 14 229 en 2019."}], AUTORISEES)
    assert [e.valeur for e in r.ecartees] == ["14 229"]


def test_reformulation_retire_la_parenthese():
    r = controler([{"type": "constat",
                    "texte": "Les créations atteignent 21 132 PME (soit 8,1 % de plus) en 2024."}],
                  AUTORISEES)
    assert r.enonces[0].texte == "Les créations atteignent 21 132 PME en 2024."
    assert r.ecartees[0].action == "reformule"


def test_reformulation_retire_la_proposition():
    r = controler([{"type": "constat",
                    "texte": "En 2024, les CFCE enregistrent 21 132 créations, soit 3 000 de plus qu'en 2022."}],
                  AUTORISEES)
    assert "3 000" not in r.enonces[0].texte
    assert "21 132" in r.enonces[0].texte


def test_perspective_controlee_aussi():
    r = controler([{"type": "perspective",
                    "texte": "Les créations pourraient dépasser 25 000 en 2025."}], AUTORISEES)
    assert [e.valeur for e in r.ecartees] == ["25 000"]


def test_valeur_declaree_hors_texte_controlee():
    r = controler([{"type": "constat", "texte": "Les créations progressent.", "valeurs": ["9,9"]}],
                  AUTORISEES)
    assert [e.valeur for e in r.ecartees] == ["9,9"]


def test_annees_et_references_non_controlees():
    r = controler([{"type": "constat",
                    "texte": "Selon le tableau 7 (p. 19), les créations de 2024 atteignent 21 132."}],
                  AUTORISEES)
    assert r.ecartees == []


def test_ecriture_differente_acceptee():
    assert valeurs_non_soutenues("21132 créations, +7.5 %", AUTORISEES) == []
    assert valeurs_non_soutenues("hausse de 7,5 pour cent", AUTORISEES) == []


def test_comptage():
    r = controler([{"type": "constat", "texte": "21 132 créations contre 18 000 attendues."}], AUTORISEES)
    assert r.n_valeurs_citees == 2 and r.n_valeurs_soutenues == 1
