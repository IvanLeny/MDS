"""Lecture de config.yaml (seule source des paramètres expérimentaux)."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RACINE = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=4)
def charger(chemin: str | None = None) -> dict:
    """Charge la configuration (mise en cache)."""
    p = Path(chemin) if chemin else RACINE / "config.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get(cle: str, defaut: Any = None, cfg: dict | None = None) -> Any:
    """Accès pointé : get("recherche.rrf_k")."""
    node: Any = cfg if cfg is not None else charger()
    for part in cle.split("."):
        if not isinstance(node, dict) or part not in node:
            return defaut
        node = node[part]
    return node


def chemin(cle: str) -> Path:
    """Chemin absolu d'une entrée de la rubrique `chemins`."""
    return RACINE / get(f"chemins.{cle}")


def config_hash(cfg: dict | None = None) -> str:
    """Empreinte courte de la configuration, journalisée avec chaque production."""
    cfg = cfg if cfg is not None else charger()
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
