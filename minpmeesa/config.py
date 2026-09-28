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


@lru_cache(maxsize=4)
def charger(chemin: str | None = None) -> dict:
    """Renvoie la configuration sous forme de dictionnaire."""
    chemin = chemin or os.environ.get("MINPMEESA_CONFIG") or str(RACINE / "config.yaml")
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
