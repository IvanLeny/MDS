"""Métriques d'évaluation (chapitre 2.4). ROUGE-L repris de src/eval/metrics.py."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from ..retrieval.text import plat

_MOT = re.compile(r"[a-z0-9]+")


def _toks(t: str) -> List[str]:
    return _MOT.findall(plat(t))


# ---------------------------------------------------------------------------
#  Récupération (H1)
# ---------------------------------------------------------------------------
def rang_pertinent(resultats: Sequence[Tuple[str, int]], pertinents: Set[Tuple[str, int]]) -> int | None:
    """Rang (1-indexé) du premier résultat (doc_id, page) pertinent."""
    for i, r in enumerate(resultats, start=1):
        if tuple(r) in pertinents:
            return i
    return None


def succes_at(rang: int | None, k: int) -> float:
    return 1.0 if rang is not None and rang <= k else 0.0


def rr(rang: int | None) -> float:
    return 0.0 if rang is None else 1.0 / rang


def ndcg_at(resultats: Sequence[Tuple[str, int]], pertinents: Set[Tuple[str, int]], k: int = 5) -> float:
    """nDCG binaire ; un même (doc, page) ne compte qu'une fois."""
    vus, dcg = set(), 0.0
    for i, r in enumerate(resultats[:k], start=1):
        r = tuple(r)
        if r in pertinents and r not in vus:
            dcg += 1.0 / math.log2(i + 1)
            vus.add(r)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(pertinents), k) + 1))
    return dcg / idcg if idcg else 0.0


# ---------------------------------------------------------------------------
#  Rédaction (H1 ancrage)
# ---------------------------------------------------------------------------
def _lcs(a: Sequence, b: Sequence) -> int:
    if not a or not b:
        return 0
    dp = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        prev = 0
        for j in range(1, len(b) + 1):
            tmp = dp[j]
            dp[j] = prev + 1 if a[i - 1] == b[j - 1] else max(dp[j], dp[j - 1])
            prev = tmp
    return dp[len(b)]


def rouge_l(candidat: str, reference: str) -> float:
    """ROUGE-L, mesure F (β = 1) sur les mots sans accents."""
    a, b = _toks(candidat), _toks(reference)
    if not a or not b:
        return 0.0
    l = _lcs(a, b)
    if l == 0:
        return 0.0
    p, r = l / len(a), l / len(b)
    return 2 * p * r / (p + r)


def cosinus(u, v) -> float:
    import numpy as np
    u, v = np.asarray(u, dtype=float), np.asarray(v, dtype=float)
    d = float(np.linalg.norm(u) * np.linalg.norm(v))
    return float(u @ v / d) if d else 0.0


# ---------------------------------------------------------------------------
#  Exactitude et couverture (H2, formules du 1.4.2)
# ---------------------------------------------------------------------------
def exactitude(n_soutenues: int, n_citees: int) -> float | None:
    """Exa = valeurs citées soutenues / valeurs citées. None si aucune valeur citée."""
    return None if n_citees == 0 else n_soutenues / n_citees


def couverture_valeurs(n_citees_retenues: int, n_autorisees: int) -> float | None:
    """Couv = valeurs autorisées effectivement citées / valeurs autorisées."""
    return None if n_autorisees == 0 else min(n_citees_retenues, n_autorisees) / n_autorisees


def couverture_indicateurs(n_commentes: int, n_indicateurs: int) -> float | None:
    """Couv_ind = indicateurs dotés d'un commentaire non vide après contrôle / indicateurs traités."""
    return None if n_indicateurs == 0 else n_commentes / n_indicateurs


# ---------------------------------------------------------------------------
#  Accord inter-annotateurs
# ---------------------------------------------------------------------------
def kappa_cohen(a: Sequence, b: Sequence) -> float:
    """Kappa de Cohen entre deux séquences d'étiquettes de même longueur."""
    if len(a) != len(b) or not a:
        raise ValueError("séquences vides ou de longueurs différentes")
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def mediane(xs: Iterable[float]) -> float | None:
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def quantile(xs: Iterable[float], q: float) -> float | None:
    import numpy as np
    xs = list(xs)
    return float(np.quantile(xs, q)) if xs else None
