"""Encodeur dense chargé EXCLUSIVEMENT depuis models/ (aucun appel réseau).

Deux formats de dossier sont reconnus dans models/<organisation>__<modèle>/ :
  - ONNX (model.onnx + tokenizer.json) : exécuté par onnxruntime, sans PyTorch ;
  - sentence-transformers (dossier sauvegardé par scripts/telecharger_modeles.py).
Préfixes et agrégation propres à chaque modèle (fiches des modèles) :
  - e5 : « query: » / « passage: », moyenne des états cachés ;
  - bge-m3 : pas de préfixe, vecteur du jeton [CLS] ;
  - camembert, MiniLM : pas de préfixe, moyenne.
Vecteurs normalisés L2 (cosinus = produit scalaire).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

from .. import config


class ModeleAbsent(RuntimeError):
    pass


def dossier_modele(nom: str) -> Path:
    return config.chemin("modeles") / nom.replace("/", "__")


def _profil(nom: str) -> dict:
    n = nom.lower()
    if "e5" in n:
        return {"q": "query: ", "p": "passage: ", "pool": "mean"}
    if "bge-m3" in n:
        return {"q": "", "p": "", "pool": "cls"}
    return {"q": "", "p": "", "pool": "mean"}


class Encodeur:
    def __init__(self, nom: str | None = None):
        self.nom = nom or config.get("embeddings.modele")
        self.dossier = dossier_modele(self.nom)
        self.profil = _profil(self.nom)
        self.longueur = int(config.get("embeddings.longueur_max", 512))
        self.lot = int(config.get("embeddings.taille_lot", 16))
        if (self.dossier / "model.onnx").exists():
            self._init_onnx()
        elif (self.dossier / "modules.json").exists() or (self.dossier / "config.json").exists():
            self._init_st()
        else:
            raise ModeleAbsent(f"modèle {self.nom} absent de {self.dossier} "
                               f"(lancer scripts/telecharger_modeles.py)")

    def _init_onnx(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.mode = "onnx"
        self.tok = Tokenizer.from_file(str(self.dossier / "tokenizer.json"))
        self.tok.enable_truncation(self.longueur)
        pad = self.tok.token_to_id("<pad>")
        self.tok.enable_padding(pad_id=pad if pad is not None else 0,
                                pad_token="<pad>" if pad is not None else "[PAD]")
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(self.dossier / "model.onnx"), opts,
                                         providers=["CPUExecutionProvider"])
        self.entrees = {i.name for i in self.sess.get_inputs()}

    def _init_st(self):
        from sentence_transformers import SentenceTransformer
        self.mode = "sentence-transformers"
        self.st = SentenceTransformer(str(self.dossier), device="cpu")
        self.st.max_seq_length = self.longueur

    def _encoder(self, textes: List[str]) -> np.ndarray:
        if self.mode == "sentence-transformers":
            return np.asarray(self.st.encode(textes, batch_size=self.lot, normalize_embeddings=True),
                              dtype="float32")
        out = []
        for i in range(0, len(textes), self.lot):
            enc = self.tok.encode_batch(textes[i:i + self.lot])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            att = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": att}
            if "token_type_ids" in self.entrees:
                feed["token_type_ids"] = np.zeros_like(ids)
            h = self.sess.run(None, feed)[0]
            if self.profil["pool"] == "cls":
                v = h[:, 0]
            else:
                m = att[..., None].astype(np.float32)
                v = (h * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
            v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
            out.append(v.astype("float32"))
        return np.vstack(out) if out else np.zeros((0, 1), dtype="float32")

    def requetes(self, textes: List[str]) -> np.ndarray:
        return self._encoder([self.profil["q"] + t for t in textes])

    def passages(self, textes: List[str]) -> np.ndarray:
        return self._encoder([self.profil["p"] + t for t in textes])


_CACHE: dict = {}


def encodeur(nom: str | None = None) -> Encodeur:
    nom = nom or config.get("embeddings.modele")
    if nom not in _CACHE:
        _CACHE[nom] = Encodeur(nom)
    return _CACHE[nom]


def encodeur_disponible(nom: str | None = None) -> str | None:
    """Premier encodeur disponible localement : le modèle configuré, sinon le
    premier candidat présent dans models/. None si aucun."""
    noms = [nom or config.get("embeddings.modele")] + list(config.get("embeddings.candidats", []))
    for n in noms:
        d = dossier_modele(n)
        if (d / "model.onnx").exists() or (d / "modules.json").exists():
            return n
    return None
