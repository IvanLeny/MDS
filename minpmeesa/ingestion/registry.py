"""Registre des documents : type, exercice, trimestre, statut, fichier.

Deux sources, confrontées à chaque reconstruction :
  - `data/corpus/registre.yaml` : ce que la Cellule déclare (dont le statut de
    diffusion, qui ne se devine pas) ;
  - la détection **par le contenu** (reprise de l'ancien `metadata.py`) : le nom
    de fichier et le titre courant sont trompeurs dans ce corpus (l'Annuaire
    2023 porte le titre courant « Annuaire statistique 2022 »).
Un désaccord est signalé ; la valeur déclarée prévaut, puisqu'elle a été vérifiée.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml

TYPES = ("annuaire", "rapport_analyse", "note_conjoncture", "contexte")
_ANNEE = re.compile(r"\b(20(?:1[0-9]|2[0-9]))\b")
_EXERCICE = re.compile(r"exercice\s+(20(?:1[0-9]|2[0-9]))", re.I)


@dataclass
class EntreeRegistre:
    doc_id: str
    fichier: str
    titre: str
    type: str
    exercice: int
    trimestre: str | None
    statut_diffusion: str
    test_synthetique: bool = False
    statut_confirme: bool = False     # confirmé auprès de la Cellule ?
    remarque: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


# ------------------------------------------------------------- détection
def detecter_trimestre(texte: str) -> str | None:
    tete = texte[:3000]
    m = re.search(r"\b([1-4])\s*(?:er|ème|eme|e)\s+trimestre\s+(20\d{2})", tete, re.I)
    if m:
        return f"T{m.group(1)}"
    m = re.search(r"(?<![A-Za-z])T\s?([1-4])\s+(20\d{2})", tete)
    return f"T{m.group(1)}" if m else None


def detecter_exercice(texte: str, type_: str) -> int | None:
    """Année dominante du corps, renforcée par « exercice 20XX ». Pour une note de
    conjoncture, l'année du trimestre annoncé en tête prévaut."""
    if type_ == "note_conjoncture":
        m = re.search(r"trimestre\s+(20\d{2})", texte[:3000], re.I)
        if m:
            return int(m.group(1))
    freq = Counter(int(a) for a in _ANNEE.findall(texte))
    if not freq:
        return None
    for a in _EXERCICE.findall(texte):
        freq[int(a)] += 5
    return max(freq.items(), key=lambda kv: (kv[1], kv[0]))[0]


def detecter_type(texte: str) -> str:
    """Type lu dans la STRUCTURE du document, pas dans le nom de fichier."""
    tete = texte[:2500].lower()
    n_graph = len(set(re.findall(r"graphique\s+(\d+)", texte, re.I)))
    n_tab = len(set(re.findall(r"tableau\s+(\d+)", texte, re.I)))
    if "note de conjoncture" in re.sub(r"\s+", " ", tete) or re.search(r"trimestre\s+20\d\d", tete):
        if n_tab < 20:
            return "note_conjoncture"
    if "rapport d" in tete and "analyse" in tete:
        return "rapport_analyse"
    if "bulletin" in tete or "note de perspective" in tete or "perspective" in tete[:800]:
        if n_tab < 20:
            return "contexte"
    if n_tab >= 20 and n_tab > n_graph:
        return "annuaire"
    if n_graph >= 5:
        return "rapport_analyse"
    return "contexte"


def detecter(texte: str) -> dict:
    type_ = detecter_type(texte)
    return {"type": type_, "exercice": detecter_exercice(texte, type_),
            "trimestre": detecter_trimestre(texte) if type_ == "note_conjoncture" else None}


# ------------------------------------------------------------- registre
def charger_registre(chemin: Path) -> dict[str, EntreeRegistre]:
    with open(chemin, encoding="utf-8") as f:
        brut = yaml.safe_load(f) or {}
    out = {}
    for d in brut.get("documents", []):
        e = EntreeRegistre(**d)
        if e.type not in TYPES:
            raise ValueError(f"{e.doc_id} : type inconnu {e.type}")
        if e.statut_diffusion not in ("publie", "interne"):
            raise ValueError(f"{e.doc_id} : statut inconnu {e.statut_diffusion}")
        out[e.fichier] = e
    return out


def confronter(entree: EntreeRegistre, detecte: dict) -> list[str]:
    """Liste des désaccords entre le registre et la détection par le contenu."""
    ecarts = []
    for cle in ("type", "exercice", "trimestre"):
        if detecte.get(cle) != getattr(entree, cle):
            ecarts.append(f"{cle}: registre={getattr(entree, cle)!r} contenu={detecte.get(cle)!r}")
    return ecarts
