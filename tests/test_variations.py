"""Calcul déterministe des variations (3.3.3) : arrondi, zéro, valeur manquante,
identifiants des deux valeurs sources, aucune valeur postérieure."""
import pytest

from minpmeesa.compute.variations import calculer_pour_indicateur, recalculer_tout
from minpmeesa.store.db import Base


def base_test(valeurs):
    b = Base(":memory:")
    b.ajouter_document({"doc_id": "annuaire_2024", "titre": "A", "type": "annuaire", "exercice": 2024,
                        "statut_diffusion": "publie", "fichier": "a.pdf", "nb_pages": 1, "sha256": "x"})
    for ligne, col, txt, num, unite in valeurs:
        b.ajouter_valeur({"doc_id": "annuaire_2024", "page": 5, "tableau_n": 7, "tableau_intitule": "T7",
                          "ligne": ligne, "colonne": col, "valeur_texte": txt, "valeur_num": num,
                          "unite": unite})
    b.ajouter_appariement({"code_indicateur": "pme-crees-cfce", "exercice": 2024, "tableau_n": 7,
                           "doc_annuaire": "annuaire_2024", "statut": "candidat"})
    return b


def test_variation_et_arrondi():
    b = base_test([("Total", "2019", "14 229", 14229, ""), ("Total", "2023", "19 651", 19651, ""),
                   ("Total", "2024", "21 132", 21132, "")])
    v = {r["exercice_ref"]: r for r in calculer_pour_indicateur(b, "pme-crees-cfce", 2024)}
    assert v[2023]["var_abs"] == 1481 and v[2023]["var_abs_texte"] == "1 481"
    assert v[2023]["var_rel_texte"] == "7,5"              # 7,536… arrondi à 1 décimale
    assert v[2019]["var_rel_texte"] == "48,5"             # chiffre publié dans le Rapport 2024
    ids = {r["valeur_id"] for r in b.q("SELECT valeur_id FROM valeurs")}
    assert v[2023]["valeur_id"] in ids and v[2023]["valeur_ref_id"] in ids
    assert v[2023]["valeur_id"] != v[2023]["valeur_ref_id"]


def test_division_par_zero():
    b = base_test([("Edéa", "2023", "0", 0, ""), ("Edéa", "2024", "40", 40, "")])
    v = calculer_pour_indicateur(b, "pme-crees-cfce", 2024)[0]
    assert v["var_abs"] == 40 and v["var_rel_pct"] is None and v["var_rel_texte"] is None


def test_valeur_manquante():
    b = base_test([("Garoua", "2024", "579", 579, ""), ("Garoua", "2023", "…", None, "")])
    assert calculer_pour_indicateur(b, "pme-crees-cfce", 2024) == []


def test_aucune_valeur_posterieure():
    b = base_test([("Total", "2023", "19 651", 19651, ""), ("Total", "2024", "21 132", 21132, ""),
                   ("Total", "2025", "25 000", 25000, "")])
    vs = calculer_pour_indicateur(b, "pme-crees-cfce", 2023)
    # L'appariement porte sur 2024 : rien pour 2023 ; et en 2024, pas de 2025.
    assert vs == []
    vs = calculer_pour_indicateur(b, "pme-crees-cfce", 2024)
    assert {r["exercice_ref"] for r in vs} == {2023}
    assert all(r["exercice"] == 2024 for r in vs)


def test_decimales_des_sources_et_pourcentage():
    b = base_test([("Tertiaire", "2023 · %", "79,6", 79.6, "%"), ("Tertiaire", "2024 · %", "77,2", 77.2, "%")])
    v = calculer_pour_indicateur(b, "pme-crees-cfce", 2024)[0]
    assert v["var_abs_texte"] == "-2,4"                   # points de pourcentage, 1 décimale
    assert v["ligne"].endswith("(%)")


def test_serie_ambigue_ignoree():
    # Deux valeurs pour la même série et la même année : aucune variation calculée.
    b = base_test([("Total", "2023", "19 651", 19651, ""), ("Total", "2024", "21 132", 21132, ""),
                   ("Total", "2024", "3", 3, "")])
    assert calculer_pour_indicateur(b, "pme-crees-cfce", 2024) == []


def test_recalculer_tout():
    b = base_test([("Total", "2023", "19 651", 19651, ""), ("Total", "2024", "21 132", 21132, "")])
    assert recalculer_tout(b) == 1
    assert b.q("SELECT COUNT(*) n FROM variations")[0]["n"] == 1
