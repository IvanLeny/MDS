"""Lecture de config.yaml (paramètres expérimentaux, chemins, graine)."""
from __future__ import annotations

import hashlib
import json
import os
import random
from functools import lru_cache
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent


LOCAL = "config.local.yaml"


def _fusionner(base: dict, ajout: dict) -> dict:
    out = dict(base)
    for k, v in ajout.items():
        out[k] = _fusionner(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@lru_cache(maxsize=4)
def charger(chemin: str | None = None) -> dict:
    """Renvoie la configuration sous forme de dictionnaire.

    Sans chemin explicite, un fichier `config.local.yaml` (propre au poste, non versionné)
    complète `config.yaml` : par exemple un modèle Ollama plus léger sur un poste de 8 Go.
    Il est signalé dans la configuration chargée (clé `config_locale`) et change config_hash.
    """
    explicite = chemin or os.environ.get("MINPMEESA_CONFIG")
    with open(explicite or RACINE / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    local = RACINE / LOCAL
    if not explicite and local.is_file():
        with open(local, encoding="utf-8") as f:
            ajout = yaml.safe_load(f) or {}
        cfg = _fusionner(cfg, ajout)
        cfg["config_locale"] = ajout
    return cfg


def chemin(cle: str) -> Path:
    """Chemin absolu d'une entrée de la section `chemins`."""
    p = Path(charger()["chemins"][cle])
    return p if p.is_absolute() else RACINE / p


def config_hash(cfg: dict | None = None) -> str:
    """Empreinte courte de la configuration (tracée dans le journal des productions)."""
    cfg = cfg or charger()
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def fixer_graine(graine: int | None = None) -> int:
    """Fixe la graine de tous les générateurs aléatoires utilisés."""
    graine = charger()["graine"] if graine is None else graine
    random.seed(graine)
    try:
        import numpy as np
        np.random.seed(graine)
    except ImportError:
        pass
    return graine
