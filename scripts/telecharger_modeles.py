"""Téléchargement UNIQUE des modèles, sur un poste connecté (section 2.2.2).

    python scripts/telecharger_modeles.py            # encodeurs + modèles de langage
    python scripts/telecharger_modeles.py --embeddings
    python scripts/telecharger_modeles.py --llm

Les encodeurs sont enregistrés dans models/embeddings/<nom> ; les modèles de
langage sont tirés par Ollama (`ollama pull`). Copier ensuite le dossier
models/ (et le dossier des modèles Ollama) sur le poste de la Cellule : à
l'exécution, plus aucun accès réseau n'est nécessaire.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from minpmeesa import config  # noqa: E402
from minpmeesa.store.encodeur import dossier_modele  # noqa: E402


def embeddings(cfg):
    from sentence_transformers import SentenceTransformer
    noms = list(dict.fromkeys(cfg["embeddings"]["candidats"] + [cfg["embeddings"]["repli_leger"]]))
    for nom in noms:
        dest = dossier_modele(nom)
        if dest.exists():
            print(f"déjà présent : {nom}")
            continue
        print(f"téléchargement : {nom} -> {dest}")
        SentenceTransformer(nom, device="cpu").save(str(dest))


def llm(cfg):
    for nom in cfg["llm"]["candidats"]:
        print(f"ollama pull {nom}")
        subprocess.run(["ollama", "pull", nom], check=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--embeddings", action="store_true")
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    cfg = config.charger()
    tout = not (a.embeddings or a.llm)
    if a.embeddings or tout:
        embeddings(cfg)
    if a.llm or tout:
        llm(cfg)
