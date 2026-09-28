"""Abstention visible (section 3.3, BF5).

Un indicateur sans source suffisante n'est pas commenté : il apparaît avec la
mention « sources insuffisantes, à commenter manuellement » et le motif.
"""
from __future__ import annotations

MENTION = "sources insuffisantes, à commenter manuellement"


def resultat(code_: str, exercice_: int, motif: str, **extra) -> dict:
    d = {**extra}
    d.update({"code_indicateur": code_, "exercice": exercice_, "abstention": True,
              "mention": MENTION, "motif": motif, "enonces": []})
    d.setdefault("valeurs_ecartees", [])
    return d


def avant_generation(ctx) -> str | None:
    """Motif d'abstention avant toute génération (aucune valeur, aucun appariement)."""
    if ctx.abstention:
        return ctx.abstention
    if not ctx.valeurs:
        return "aucune valeur pour l'exercice traité"
    return None
