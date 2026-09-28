"""Métriques d'évaluation (chapitre 2.4 ; formules du 1.4.2).

Récupération : Succès@k, MRR, nDCG@5 (pertinence au niveau (document, page)).
Rédaction    : ROUGE-L (F1 sur la plus longue sous-séquence commune de mots).
Chiffres     : exactitude (Exa), couverture des valeurs (Couv) et des
               indicateurs (Couv_ind), taux de faux rejets (TFR).
"""
from __future__ import annotations

import math
import re
from typing import Sequence

from ..texte import normaliser

_MOT = re.compile(r"[a-z0-9]+(?:[.,]\d+)?")


# ------------------------------------------------------------ récupération
def est_pertinent(passage: dict, pertinents: list[dict]) -> bool:
    """Un passage est pertinent s'il couvre une page pertinente du bon document."""
    for r in pertinents:
        if passage["doc_id"] == r["doc_id"] and any(
                passage["page"] <= p <= passage.get("page_fin", passage["page"]) for p in r["pages"]):
            return True
    return False


def succes_a_k(pert: Sequence[bool], k: int) -> float:
    return 1.0 if any(pert[:k]) else 0.0


def rr(pert: Sequence[bool]) -> float:
    for i, p in enumerate(pert, start=1):
        if p:
            return 1.0 / i
    return 0.0


def ndcg_a_k(pert: Sequence[bool], k: int, n_pertinents: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, p in enumerate(pert[:k], start=1) if p)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, max(1, n_pertinents)) + 1))
    return dcg / idcg if idcg else 0.0


# ------------------------------------------------------------ rédaction
def mots(texte: str) -> list[str]:
    return _MOT.findall(normaliser(texte))


def _lcs(a: Sequence, b: Sequence) -> int:
    if not a or not b:
        return 0
    dp = [0] * (len(b) + 1)
    for x in a:
        prev = 0
        for j, y in enumerate(b, start=1):
            tmp = dp[j]
            dp[j] = prev + 1 if x == y else max(dp[j], dp[j - 1])
            prev = tmp
    return dp[-1]


def rouge_l(candidat: str, reference: str) -> float:
    """ROUGE-L F1 (β = 1)."""
    a, b = mots(candidat), mots(reference)
    l = _lcs(a, b)
    if not l:
        return 0.0
    p, r = l / len(a), l / len(b)
    return 2 * p * r / (p + r)


def cosinus(u, v) -> float:
    import numpy as np
    u, v = np.asarray(u, dtype=float).ravel(), np.asarray(v, dtype=float).ravel()
    n = np.linalg.norm(u) * np.linalg.norm(v)
    return float(u @ v / n) if n else 0.0


# ------------------------------------------------------------ chiffres
def exactitude(n_soutenues: int, n_citees: int) -> float | None:
    """Exa = valeurs citées soutenues par une source / valeurs citées."""
    return None if n_citees == 0 else n_soutenues / n_citees


def couverture(n_citees_soutenues_distinctes: int, n_disponibles: int) -> float | None:
    """Couv = valeurs autorisées effectivement mobilisées / valeurs autorisées clés."""
    return None if n_disponibles == 0 else min(1.0, n_citees_soutenues_distinctes / n_disponibles)


def taux(n: int, d: int) -> float | None:
    return None if d == 0 else n / d
