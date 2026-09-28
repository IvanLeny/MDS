"""Tests statistiques (repris de src/eval/stats.py) : Wilcoxon apparié avec
décompte gagne / perd / égalité."""
from __future__ import annotations

from typing import List


def wilcoxon_apparie(a: List[float], b: List[float], alternative: str = "two-sided") -> dict:
    """Test des rangs signés de Wilcoxon apparié (a vs b). Les paires à
    différence nulle sont écartées (méthode « wilcox »)."""
    from scipy.stats import wilcoxon
    n = len(a)
    gagne = sum(1 for x, y in zip(a, b) if x - y > 1e-12)
    perd = sum(1 for x, y in zip(a, b) if y - x > 1e-12)
    out = {"n": n, "gagne": gagne, "perd": perd, "egalite": n - gagne - perd,
           "moyenne_a": sum(a) / n if n else None, "moyenne_b": sum(b) / n if n else None,
           "p_value": None, "statistique": None}
    if gagne + perd == 0:
        out["remarque"] = "aucune différence : test non applicable"
        return out
    try:
        r = wilcoxon(a, b, zero_method="wilcox", alternative=alternative)
        out["p_value"], out["statistique"] = float(r.pvalue), float(r.statistic)
    except ValueError as e:
        out["remarque"] = str(e)
    return out
