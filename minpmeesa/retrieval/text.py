"""Tokenisation française commune (BM25, expansion par le lexique, similarités)."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Set

import yaml

_MOT = re.compile(r"[a-z0-9]+")
VIDES: Set[str] = {
    "le", "la", "les", "un", "une", "des", "de", "du", "d", "l", "et", "en", "au", "aux", "a",
    "dans", "par", "pour", "sur", "se", "sa", "son", "ses", "ce", "cette", "ces", "que", "qui",
    "quel", "quelle", "quels", "quelles", "est", "sont", "ont", "ete", "il", "elle", "on", "y",
    "ou", "ne", "pas", "plus", "moins", "leur", "leurs", "avec", "entre", "selon", "the", "of",
    "combien", "comment", "quoi", "t", "s", "c", "qu", "n", "j", "m",
}


def plat(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower().replace("’", "'")


def tokens(t: str) -> List[str]:
    """Mots sans accents ni mots-outils ; les nombres sont gardés (utiles au BM25)."""
    return [m for m in _MOT.findall(plat(t)) if m not in VIDES]


def jaccard(a: str, b: str) -> float:
    x, y = set(tokens(a)), set(tokens(b))
    return len(x & y) / len(x | y) if x and y else 0.0


@lru_cache(maxsize=2)
def lexique(chemin: str) -> Dict[str, List[str]]:
    """Familles de synonymes métier : terme -> autres termes de la famille."""
    data = yaml.safe_load(open(chemin, encoding="utf-8")) or {}
    out: Dict[str, List[str]] = {}
    for fam in data.get("familles", []):
        termes = [plat(str(x)).replace("_", " ") for x in fam]
        for t in termes:
            out.setdefault(t, [])
            out[t] += [u for u in termes if u != t and u not in out[t]]
    return out


def etendre(requete: str, chemin_lexique: str, max_par_terme: int) -> List[str]:
    """Expansion de la requête LEXICALE par le lexique (jamais la requête dense,
    jamais les passages). Renvoie la liste de tokens étendue."""
    lex = lexique(chemin_lexique)
    q = plat(requete)
    toks = tokens(requete)
    ajout: List[str] = []
    for terme, syn in lex.items():
        motif = r"\b" + re.escape(terme) + r"\b"
        if re.search(motif, q):
            for s in syn[:max_par_terme]:
                ajout += tokens(s)
    return toks + [t for t in ajout if t not in toks]
