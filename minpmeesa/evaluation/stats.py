"""Tests statistiques : Wilcoxon apparié, kappa de Cohen, résumés."""
from __future__ import annotations

import statistics as st


def wilcoxon(a: list[float], b: list[float], alternative: str = "two-sided") -> dict:
    """Test des rangs signés de Wilcoxon apparié, avec décompte gagne/perd/égalité."""
    from scipy.stats import wilcoxon as w
    d = [x - y for x, y in zip(a, b)]
    gagne = sum(1 for x in d if x > 1e-12)
    perd = sum(1 for x in d if x < -1e-12)
    res = {"n": len(d), "moyenne_a": _moy(a), "moyenne_b": _moy(b),
           "delta_moyen": _moy(d), "gagne": gagne, "perd": perd,
           "egalite": len(d) - gagne - perd, "statistique": None, "p_value": None}
    if gagne + perd == 0:
        res["remarque"] = "aucune différence : test non applicable"
        return res
    s = w(a, b, zero_method="wilcox", alternative=alternative)
    res["statistique"] = float(s.statistic)
    res["p_value"] = float(s.pvalue)
    return res


def _moy(x):
    return round(st.mean(x), 4) if x else None


def kappa_cohen(a: list, b: list) -> float | None:
    from collections import Counter
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def mediane_p90(x: list[float]) -> dict:
    import numpy as np
    if not x:
        return {"n": 0, "mediane": None, "p90": None}
    return {"n": len(x), "mediane": round(float(np.median(x)), 3),
            "p90": round(float(np.percentile(x, 90)), 3), "max": round(max(x), 3)}
