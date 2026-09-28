"""Index lexical BM25 persistant (fichier pickle à côté de la base).

Seuls les passages de documents « publie » sont indexés pour la consultation :
le filtre de statut est appliqué dans la requête SQL qui alimente l'index
(Base.passages_publies), avant tout classement.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from .. import config
from ..retrieval.text import tokens


def _chemin() -> Path:
    return config.chemin("index") / "bm25.pkl"


class IndexBM25:
    def __init__(self, ids: List[int], corpus_tokens: List[List[str]]):
        self.ids = ids
        self.bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None

    def chercher(self, requete_tokens: List[str], k: int, ajouts: List[str] | None = None,
                 poids_ajouts: float = 1.0) -> List[Tuple[int, float]]:
        """Classement BM25. `ajouts` : termes issus de l'expansion par le lexique,
        pondérés par `poids_ajouts` (1 = même poids que les mots de la question)."""
        if not self.bm25 or not requete_tokens:
            return []
        scores = self.bm25.get_scores(requete_tokens)
        if ajouts:
            scores = scores + poids_ajouts * self.bm25.get_scores(ajouts)
        ordre = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [(self.ids[i], float(scores[i])) for i in ordre if scores[i] > 0]


def construire_bm25(base, chemin: Path | None = None) -> IndexBM25:
    rows = base.passages_publies()
    idx = IndexBM25([r["passage_id"] for r in rows], [tokens(r["texte"]) for r in rows])
    p = chemin or _chemin()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        pickle.dump(idx, f)
    return idx


def charger_bm25(chemin: Path | None = None) -> IndexBM25:
    with open(chemin or _chemin(), "rb") as f:
        return pickle.load(f)
