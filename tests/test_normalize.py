"""R0 : harmonisation des écritures numériques (au moins 20 cas) et liste
d'exclusion (années, numéros de tableau/page, ordinaux)."""
import pytest

from minpmeesa.guards.normalize import canon, cles, cles_valeur, extraire_nombres, formater_fr


def cle_unique(texte):
    ns = extraire_nombres(texte)
    assert len(ns) == 1, (texte, ns)
    return cles(ns[0])


@pytest.mark.parametrize("a,b", [
    ("7,8", "7.8"),
    ("12 500", "12500"),
    ("12 500", "12500"),              # espace insécable
    ("12 500", "12 500"),             # fine insécable
    ("12 500", "12500"),              # espace fine
    ("7,80", "7,8"),                       # zéro final non significatif
    ("393 954", "393954"),
    ("1 234 567", "1234567"),
    ("1.234.567", "1234567"),              # points de milliers répétés
    ("1.234,5", "1234,5"),                 # point de milliers + virgule décimale
    ("1,234.5", "1234.5"),                 # virgule de milliers + point décimal
    ("0,17", "0.17"),
    ("-3,2", "3,2"),                       # comparaison en valeur absolue
    ("+12,8", "12,8"),
    ("−4,5", "4,5"),                       # signe moins typographique
    ("100", "100,0"),
    ("48,5 %", "48,5"),
    ("48,5 pour cent", "48,5"),
    ("48,5%", "48,5 %"),
    ("21 132", "21132"),
])
def test_ecritures_equivalentes(a, b):
    assert cle_unique(a) & cle_unique(b)


@pytest.mark.parametrize("a,b", [
    ("7,8", "78"),
    ("12,5", "125"),
    ("0,17", "0,71"),
    ("393 954", "393 945"),
])
def test_ecritures_differentes(a, b):
    assert not (cle_unique(a) & cle_unique(b))


def test_ecriture_ambigue_deux_lectures():
    # « 12.500 » : 12,5 ou 12 500 selon la convention -> deux lectures.
    assert {"12.5", "12500"} <= cle_unique("12.500")


def test_pourcentage_repere():
    assert extraire_nombres("hausse de 7,8 %")[0].pourcentage
    assert extraire_nombres("hausse de 7,8 pour cent")[0].pourcentage
    assert not extraire_nombres("7 800 PME")[0].pourcentage


@pytest.mark.parametrize("texte", [
    "En 2024, le stock progresse.",
    "entre 2019 et 2030",
    "selon le tableau 17",
    "voir le graphique 2",
    "à la page 12",
    "p. 45",
    "le 1er trimestre",
    "au T3 2024",
    "le 3ème trimestre 2022",
    "la 14e édition",
    "au chapitre 2",
    "l'annexe 3",
])
def test_exclusions(texte):
    assert extraire_nombres(texte) == []


def test_valeur_et_annee_melangees():
    ns = extraire_nombres("En 2024, 21 132 PME ont été créées (tableau 7, p. 19), soit +7,5 %.")
    assert [n.texte for n in ns] == ["21 132", "+7,5"]


def test_nombre_2020_avec_espace_n_est_pas_un_millesime():
    assert cle_unique("2 020 PME") == {"2020"}


def test_canon_et_cles_valeur():
    from decimal import Decimal
    assert canon(Decimal("7.80")) == "7.8"
    assert cles_valeur("2024") == {"2024"}          # une valeur autorisée peut être un nombre à 4 chiffres


@pytest.mark.parametrize("x,d,attendu", [
    (12500.456, 1, "12 500,5"), (48.51, 1, "48,5"), (0.05, 1, "0,1"), (-3.25, 1, "-3,3"),
    (1481, 0, "1 481"), (7.0, 1, "7,0"),
])
def test_formater_fr(x, d, attendu):
    assert formater_fr(x, d) == attendu


@pytest.mark.parametrize("texte", ["la tranche de 30 à 40 ans", "moins de 20 ans", "les 20-30 ans"])
def test_bornes_d_age_exclues(texte):
    assert extraire_nombres(texte) == []
