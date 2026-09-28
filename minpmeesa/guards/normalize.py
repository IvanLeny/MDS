"""Harmonisation des écritures numériques (règle R0 du Tableau 3.5).

7,8 ≡ 7.8 ; 12 500 ≡ 12500 ≡ 12 500 (espace insécable ou fine) ; % ≡ pour cent ;
0,10 ≡ 0,1 (même valeur). Le signe est porté par les mots (« baisse de 3,2 % »),
la comparaison se fait donc sur la valeur absolue.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

ESPACES = "    "

# Nombre : groupes de milliers séparés par une espace, ou suite de chiffres,
# partie décimale éventuelle ; éventuellement suivi de « % » ou « pour cent ».
NOMBRE = re.compile(
    r"(?<![\w.,  ])"
    r"(?P<signe>[-+−])?"
    r"(?P<n>\d{1,3}(?:[    ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)"
    r"(?P<pct>\s?(?:%|pour\s?cent|p\.\s?c\.))?"
    r"(?![\w])", re.I)


def formes(n: str) -> set[Decimal]:
    """Valeurs possibles d'une écriture (ambiguïté du point : décimal ou milliers)."""
    t = n.strip()
    for e in ESPACES:
        t = t.replace(e, "")
    out: set[Decimal] = set()

    def ajoute(s: str):
        try:
            out.add(abs(Decimal(s)).normalize())
        except InvalidOperation:
            pass

    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            ajoute(t.replace(".", "").replace(",", "."))
        else:
            ajoute(t.replace(",", ""))
    elif "," in t:
        if t.count(",") == 1:
            ajoute(t.replace(",", "."))
        else:
            ajoute(t.replace(",", ""))
    elif "." in t:
        if t.count(".") > 1:
            ajoute(t.replace(".", ""))
        else:
            ajoute(t)                                    # 7.8 -> 7,8
            if re.fullmatch(r"\d{1,3}\.\d{3}", t):
                ajoute(t.replace(".", ""))               # 2.500 -> 2500 (milliers)
    else:
        ajoute(t)
    return out


def canon(n: str) -> Decimal | None:
    f = formes(n)
    return min(f) if f else None


def decimales(n: str) -> int:
    m = re.search(r"[.,](\d+)$", n.strip())
    return len(m.group(1)) if m else 0
