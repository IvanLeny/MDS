"""Index dense FAISS persistant (fichier sur disque, sans serveur)."""
from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np

FICHIER = "dense.faiss"


def construire(ids: list[int], vecteurs: np.ndarray) -> faiss.Index:
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(vecteurs.shape[1]))
    index.add_with_ids(np.ascontiguousarray(vecteurs, dtype="float32"), np.asarray(ids, dtype="int64"))
    return index


def sauver(index: faiss.Index, dossier: Path):
    faiss.write_index(index, str(dossier / FICHIER))


def charger(dossier: Path) -> faiss.Index:
    return faiss.read_index(str(dossier / FICHIER))


def rechercher(index: faiss.Index, requete: np.ndarray, autorises: list[int], k: int) -> list[tuple[int, float]]:
    """Recherche restreinte aux identifiants autorisés via un sélecteur FAISS :
    le filtre est appliqué pendant la recherche, jamais après."""
    if not autorises:
        return []
    sel = faiss.IDSelectorBatch(np.asarray(autorises, dtype="int64"))
    params = faiss.SearchParameters(sel=sel)
    k = min(k, len(autorises))
    d, i = index.search(np.ascontiguousarray(requete, dtype="float32"), k, params=params)
    return [(int(pid), float(s)) for pid, s in zip(i[0], d[0]) if pid != -1]
