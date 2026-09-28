"""Harmonisation numérique (R0) : au moins 20 cas, et liste d'exclusion."""
from decimal import Decimal

import pytest

from minpmeesa.guards.literal_check import nombres
from minpmeesa.guards.normalize import formes

EQUIVALENTS = [
    ("7,8", "7.8"), ("12 500", "12500"), ("12 500", "12500"), ("12 500", "12 500"),
    ("0,10", "0,1"), ("100", "100,0"), ("443 524", "443524"), ("1 234 567", "1234567"),
    ("3,50", "3.5"), ("-3,2", "3,2"), ("−3,2", "3,2"), ("1.234,5", "1234,5"), ("1,234.5", "1234.5"),
    ("2.500", "2500"), ("0,05", "0.05"), ("99,8", "99.80"), ("21 132", "21132"), ("7", "7,0"),
    ("1 000 000", "1000000"), ("48,46", "48.46"),
]
DIFFERENTS = [("7,8", "7,83"), ("12 500", "1 250"), ("0,1", "0,01"), ("85,3", "85,4"), ("26,8", "268")]


@pytest.mark.parametrize("a,b", EQUIVALENTS)
def test_ecritures_equivalentes(a, b):
    assert formes(a.lstrip("-−")) & formes(b), (a, b)


@pytest.mark.parametrize("a,b", DIFFERENTS)
def test_ecritures_differentes(a, b):
    assert not formes(a) & formes(b)


def test_pour_cent_equivaut_au_symbole():
    assert nombres("hausse de 7,5 pour cent") == ["7,5"]
    assert nombres("hausse de 7,5 %") == ["7,5"]


@pytest.mark.parametrize("texte", [
    "En 2024, sur la période 2022-2024,", "le tableau 17 page 27", "au 1er trimestre", "le 3ème trimestre",
    "la 14ième édition", "T3_2024 et le T4", "la SND30 et le CSP 2022-2024", "Graphique 2 : répartition",
    "chapitre 4, annexe 2, section 1",
])
def test_liste_exclusion(texte):
    assert nombres(texte) == [], texte


def test_valeurs_statistiques_conservees():
    assert nombres("En 2024, 21 132 PME, soit +7,5 % ; 2 067 en 2022 à 2 501") == ["21 132", "7,5", "2 067", "2 501"]
