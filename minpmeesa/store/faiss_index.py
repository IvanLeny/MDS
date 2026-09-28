"""Index dense FAISS persistant sur disque (produit scalaire sur vecteurs
normalisés = cosinus). Un index par encodeur : data/base/index/<modèle>.faiss."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np

from .. import config
from ..retrieval.embeddings import encodeur, encodeur_disponible


def _chemins(nom: str, dossier: Path | None = None) -> Tuple[Path, Path]:
    d = dossier or config.chemin("index")
    s = nom.replace("/", "__")
    return d / f"{s}.faiss", d / f"{s}.ids.json"


class IndexDense:
    def __init__(self, nom: str, index, ids: List[int]):
        self.nom, self.index, self.ids = nom, index, ids

    def chercher(self, requete: str, k: int) -> List[Tuple[int, float]]:
        q = encodeur(self.nom).requetes([requete])
        scores, pos = self.index.search(q, min(k, len(self.ids)))
        return [(self.ids[p], float(s)) for s, p in zip(scores[0], pos[0]) if p >= 0]


def _empreinte(texte: str) -> str:
    return hashlib.sha1(texte.encode("utf-8")).hexdigest()


def _cache(nom: str, dossier: Path | None) -> Path:
    return (dossier or config.chemin("index")) / f"{nom.replace('/', '__')}.cache.npz"


def vecteurs_passages(nom: str, textes: List[str], dossier: Path | None = None) -> Tuple[np.ndarray, int]:
    """Vecteurs des passages, avec un cache par empreinte du texte : seuls les
    passages nouveaux ou modifiés sont encodés. Renvoie (vecteurs, nb encodés)."""
    fc = _cache(nom, dossier)
    cache = {}
    if fc.exists():
        z = np.load(fc)
        cache = dict(zip(z["cles"].tolist(), z["vecs"]))
    cles = [_empreinte(t) for t in textes]
    manquants = [i for i, k in enumerate(cles) if k not in cache]
    if manquants:
        nouveaux = encodeur(nom).passages([textes[i] for i in manquants])
        for i, v in zip(manquants, nouveaux):
            cache[cles[i]] = v
    vecs = np.vstack([cache[k] for k in cles]).astype("float32") if cles else np.zeros((0, 1), "float32")
    fc.parent.mkdir(parents=True, exist_ok=True)
    np.savez(fc, cles=np.array(list(cache.keys())), vecs=np.vstack(list(cache.values())))
    return vecs, len(manquants)


def construire_faiss(base, nom: str | None = None, dossier: Path | None = None) -> dict:
    nom = nom or encodeur_disponible()
    if nom is None:
        raise RuntimeError("aucun encodeur dense présent dans models/")
    rows = base.passages_publies()
    t0 = time.time()
    vecs, n_encodes = vecteurs_passages(nom, [r["texte"] for r in rows], dossier)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    f_idx, f_ids = _chemins(nom, dossier)
    f_idx.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(f_idx))
    f_ids.write_text(json.dumps([r["passage_id"] for r in rows]), encoding="utf-8")
    info = {"modele": nom, "passages": len(rows), "passages_encodes": n_encodes,
            "dimension": int(vecs.shape[1]), "duree_indexation_s": round(time.time() - t0, 1)}
    f_idx.with_suffix(".info.json").write_text(json.dumps(info), encoding="utf-8")
    return info


def charger_faiss(nom: str | None = None) -> IndexDense:
    nom = nom or encodeur_disponible()
    if nom is None:
        raise FileNotFoundError("aucun encodeur dense disponible")
    f_idx, f_ids = _chemins(nom)
    if not f_idx.exists():
        raise FileNotFoundError(f"index dense absent pour {nom} : reconstruire la base")
    return IndexDense(nom, faiss.read_index(str(f_idx)), json.loads(f_ids.read_text(encoding="utf-8")))
