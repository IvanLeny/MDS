"""Index lexical BM25 persistant (fichier sur disque)."""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from ..texte import tokens

FICHIER = "bm25.pkl"


class IndexBM25:
    def __init__(self, ids: list[int], corpus_tokens: list[list[str]]):
        self.ids = list(ids)
        self._pos = {pid: i for i, pid in enumerate(self.ids)}
        self._bm25 = BM25Okapi(corpus_tokens)

    @classmethod
    def construire(cls, passages: list[tuple[int, str]]) -> "IndexBM25":
        return cls([p for p, _ in passages], [tokens(t) for _, t in passages])

    def sauver(self, dossier: Path):
        with open(dossier / FICHIER, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def charger(dossier: Path) -> "IndexBM25":
        with open(dossier / FICHIER, "rb") as f:
            return pickle.load(f)

    def rechercher(self, requete_tokens: list[str], autorises: list[int], k: int) -> list[tuple[int, float]]:
        """Scores calculés UNIQUEMENT sur les passages autorisés (filtre avant classement)."""
        pos = [self._pos[p] for p in autorises if p in self._pos]
        if not pos or not requete_tokens:
            return []
        scores = np.asarray(self._bm25.get_batch_scores(requete_tokens, pos))
        ordre = np.argsort(-scores, kind="stable")[:k]
        return [(self.ids[pos[i]], float(scores[i])) for i in ordre if scores[i] > 0]
