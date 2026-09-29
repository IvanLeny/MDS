"""Téléchargement UNIQUE des modèles, sur un poste connecté (section 2.2.2).

    python scripts/telecharger_modeles.py            # encodeurs + modèles de langage
    python scripts/telecharger_modeles.py --embeddings
    python scripts/telecharger_modeles.py --llm
    python scripts/telecharger_modeles.py --etat                 # ce qui est déjà présent
    python scripts/telecharger_modeles.py --modele BAAI/bge-m3   # un seul encodeur

Connexion lente : télécharger un encodeur à la fois, du plus léger au plus
lourd. Un téléchargement interrompu reprend là où il s'était arrêté (cache
Hugging Face) : relancer la même commande.

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


# Taille approximative des fichiers à télécharger (ordre de grandeur, pour prévoir la connexion).
TAILLES = {
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": "≈ 0,5 Go",
    "dangvantuan/sentence-camembert-base": "≈ 0,5 Go",
    "intfloat/multilingual-e5-large": "≈ 2,2 Go",
    "BAAI/bge-m3": "≈ 2,3 Go",
}


def _noms(cfg):
    return list(dict.fromkeys(cfg["embeddings"]["candidats"] + [cfg["embeddings"]["repli_leger"]]))


def etat(cfg):
    for nom in _noms(cfg):
        print(f"{'présent ' if dossier_modele(nom).exists() else 'absent  '} {nom:<62} {TAILLES.get(nom, '')}")


def embeddings(cfg, seulement=None):
    noms = _noms(cfg)
    if seulement:
        inconnus = [n for n in seulement if n not in noms]
        if inconnus:
            sys.exit(f"encodeur(s) absent(s) de config.yaml (embeddings) : {inconnus}")
        noms = seulement
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        sys.exit("sentence-transformers n'est pas installé : pip install sentence-transformers==6.1.0")
    for nom in noms:
        dest = dossier_modele(nom)
        if dest.exists():
            print(f"déjà présent : {nom}")
            continue
        print(f"téléchargement : {nom} ({TAILLES.get(nom, 'taille inconnue')}) -> {dest}", flush=True)
        tmp = dest.with_name(dest.name + ".partiel")
        m = SentenceTransformer(nom, device="cpu")
        m.save(str(tmp))
        # vérification : le modèle enregistré se recharge et encode une phrase
        v = SentenceTransformer(str(tmp), device="cpu").encode(["Stock des PME par région"], normalize_embeddings=True)
        tmp.rename(dest)                     # présent seulement s'il est complet et lisible
        print(f"  OK : dimension {v.shape[1]}")


def llm(cfg):
    for nom in cfg["llm"]["ollama"]["candidats"]:
        print(f"ollama pull {nom}")
        subprocess.run(["ollama", "pull", nom], check=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--embeddings", action="store_true")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--modele", nargs="*", default=None, help="encodeur(s) à télécharger (noms de config.yaml)")
    ap.add_argument("--etat", action="store_true", help="afficher les encodeurs présents et absents")
    a = ap.parse_args()
    cfg = config.charger()
    if a.etat:
        etat(cfg)
        sys.exit(0)
    if a.modele:
        embeddings(cfg, a.modele)
        sys.exit(0)
    tout = not (a.embeddings or a.llm)
    if a.embeddings or tout:
        embeddings(cfg)
    if a.llm or tout:
        llm(cfg)
