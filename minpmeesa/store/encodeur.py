"""Encodeur de passages pour la voie dense (Tableau 3.3).

Ordre de préférence, sans aucun téléchargement à l'exécution :
  1. un modèle sentence-transformers présent dans models/embeddings/<nom>
     (BAAI/bge-m3, intfloat/multilingual-e5-large, sentence-camembert-base,
     ou le repli léger MiniLM) ;
  2. à défaut, un encodeur HORS LIGNE : TF-IDF (mots + n-grammes de caractères)
     réduit par SVD (analyse sémantique latente), ajusté sur le corpus.
Le nom de l'encodeur effectivement utilisé est tracé dans toutes les sorties.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from .. import config

NOM_REPLI = "repli-hors-ligne-tfidf-svd"


def dossier_modele(nom: str) -> Path:
    return config.chemin("modeles") / "embeddings" / nom.replace("/", "__")


class Encodeur:
    nom: str = ""
    dim: int = 0

    def encoder_passages(self, textes: list[str]) -> np.ndarray:
        raise NotImplementedError

    def encoder_requete(self, texte: str) -> np.ndarray:
        raise NotImplementedError


class EncodeurST(Encodeur):
    """Modèle sentence-transformers chargé depuis le disque."""

    def __init__(self, nom: str, taille_lot: int = 16):
        from sentence_transformers import SentenceTransformer
        self.nom = nom
        self._m = SentenceTransformer(str(dossier_modele(nom)), device="cpu")
        dim = getattr(self._m, "get_embedding_dimension", None) or self._m.get_sentence_embedding_dimension
        self.dim = dim()
        self.lot = taille_lot
        e5 = "e5" in nom.lower()
        self._pp, self._pq = ("passage: ", "query: ") if e5 else ("", "")

    def encoder_passages(self, textes):
        v = self._m.encode([self._pp + t for t in textes], batch_size=self.lot,
                           normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype="float32")

    def encoder_requete(self, texte):
        v = self._m.encode([self._pq + texte], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype="float32")


class EncodeurLSA(Encodeur):
    """Repli hors ligne : TF-IDF + SVD tronquée, vecteurs normalisés."""

    nom = NOM_REPLI

    def __init__(self, dims: int = 256, graine: int = 42):
        self.dims, self.graine = dims, graine
        self._vw = self._vc = self._svd = None

    def ajuster(self, textes: list[str]) -> "EncodeurLSA":
        from scipy.sparse import hstack
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from ..texte import normaliser
        self._vw = TfidfVectorizer(preprocessor=normaliser, ngram_range=(1, 2), min_df=1,
                                   sublinear_tf=True, max_features=60000)
        self._vc = TfidfVectorizer(preprocessor=normaliser, analyzer="char_wb", ngram_range=(3, 5),
                                   min_df=2, sublinear_tf=True, max_features=80000)
        x = hstack([self._vw.fit_transform(textes), self._vc.fit_transform(textes)]).tocsr()
        k = max(2, min(self.dims, x.shape[0] - 1, x.shape[1] - 1))
        self._svd = TruncatedSVD(n_components=k, random_state=self.graine).fit(x)
        self.dim = k
        return self

    def _tr(self, textes):
        from scipy.sparse import hstack
        x = hstack([self._vw.transform(textes), self._vc.transform(textes)]).tocsr()
        v = self._svd.transform(x).astype("float32")
        n = np.linalg.norm(v, axis=1, keepdims=True)
        return v / np.where(n == 0, 1, n)

    def encoder_passages(self, textes):
        return self._tr(textes)

    def encoder_requete(self, texte):
        return self._tr([texte])

    def sauver(self, chemin: Path):
        with open(chemin, "wb") as f:
            pickle.dump(self, f)


def disponibles(cfg: dict) -> list[str]:
    """Modèles sentence-transformers présents sur le disque."""
    e = cfg["embeddings"]
    noms = list(dict.fromkeys(e["candidats"] + [e["repli_leger"]]))
    return [n for n in noms if dossier_modele(n).exists()]


def construire(cfg: dict, textes: list[str], nom: str | None = None) -> Encodeur:
    """Encodeur pour la construction de l'index (ajusté si repli hors ligne)."""
    e = cfg["embeddings"]
    nom = nom or e["modele"]
    ordre = [nom] if nom != NOM_REPLI else []
    ordre += [n for n in [e["repli_leger"]] if n not in ordre]
    if nom != NOM_REPLI:
        for n in ordre:
            if dossier_modele(n).exists():
                try:
                    return EncodeurST(n, e["taille_lot"])
                except ImportError:
                    break
    return EncodeurLSA(e["repli_hors_ligne_dims"], cfg["graine"]).ajuster(textes)


def charger(dossier_base: Path, nom: str) -> Encodeur:
    """Encodeur utilisé pour l'index existant (le même qu'à la construction)."""
    if nom == NOM_REPLI:
        with open(dossier_base / "encodeur_lsa.pkl", "rb") as f:
            return pickle.load(f)
    return EncodeurST(nom, config.charger()["embeddings"]["taille_lot"])
