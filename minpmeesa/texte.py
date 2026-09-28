"""Outils de texte partagés : normalisation, tokens français, similarité."""
from __future__ import annotations

import re
import unicodedata

_MOT = re.compile(r"[a-z0-9]+")

MOTS_OUTILS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "d", "l", "et", "en", "au", "aux",
    "a", "dans", "par", "pour", "sur", "se", "sa", "son", "ses", "ce", "cette", "ces",
    "que", "qui", "quoi", "est", "sont", "ont", "ou", "plus", "moins", "entre", "selon",
    "the", "of", "il", "elle", "on", "y", "ne", "pas", "avec", "leur", "leurs", "comme",
    "quel", "quelle", "quels", "quelles", "combien", "t", "s", "n", "c", "qu", "j", "m",
}


def sans_accents(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in t if not unicodedata.combining(c))


def normaliser(texte: str) -> str:
    t = sans_accents(texte).lower()
    return t.replace("’", "'").replace("œ", "oe").replace("æ", "ae")


def tokens(texte: str, garder_nombres: bool = True) -> list[str]:
    """Tokens pour BM25 : minuscules, sans accents, mots-outils retirés,
    pluriels simples ramenés au singulier."""
    out = []
    for m in _MOT.findall(normaliser(texte)):
        if m in MOTS_OUTILS:
            continue
        if m.isdigit() and not garder_nombres:
            continue
        if len(m) > 4 and m.endswith(("s", "x")) and not m.endswith(("ss", "us", "is")):
            m = m[:-1]
        out.append(m)
    return out


def ensemble(texte: str) -> set[str]:
    return {t for t in tokens(texte, garder_nombres=False) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = ensemble(a), ensemble(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
