"""Registre des documents : type, exercice, trimestre et statut de diffusion.

Le type et l'exercice se lisent dans le CONTENU, jamais dans le nom de fichier
ni dans le titre courant, tous deux trompeurs dans ce corpus (l'Annuaire 2024
porte « ANNUAIRE STATISTIQUE 2022 » en page de titre). Règles (reprises et
durcies depuis src/ingestion/metadata.py) :
  - type : intitulé explicite en tête de document (« note de conjoncture »,
    « rapport d'analyse », « annuaire statistique ») ; à défaut, contexte ;
  - exercice : trimestre pour une note de conjoncture ; année récente dominante
    du corps (bonus aux mentions « exercice 20XX ») pour un Annuaire ou un
    Rapport ; année de parution pour un document de contexte.
Le statut de diffusion ne se devine pas : il vient de
data/corpus/registre_corrections.yaml (défaut « publie », à confirmer par la Cellule).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Optional

import yaml

from .extract import Document

_ANNEE = re.compile(r"\b(20(?:1[0-9]|2[0-9]))\b")
_MOIS = (r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|"
         r"novembre|d[ée]cembre)")


def _plat(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("’", "'")
    return re.sub(r"\s+", " ", s)


def detecter_trimestre(tete: str) -> Optional[tuple]:
    t = _plat(tete)
    m = re.search(r"\b([1-4])\s*(?:er|eme|e|nd)?\s*trimestre\s*(?:de\s+l'annee\s+)?(20\d\d)", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\bt\s?([1-4])[\s_/-]*(20\d\d)\b", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def detecter_type(doc: Document) -> str:
    tete = _plat("\n".join(b.texte for p in doc.pages[:3] for b in p.blocs))
    if "note de conjoncture" in tete:
        return "note_conjoncture"
    if re.search(r"rapport d'analyse", tete):
        return "rapport_analyse"
    corps = doc.texte_complet()
    n_tab = len(set(re.findall(r"Tableau\s+(\d+)", corps)))
    n_graph = len(set(re.findall(r"Graphique\s+(\d+)", corps)))
    if "annuaire statistique" in tete and n_tab >= 10:
        return "annuaire"
    # Rapport sans intitulé lisible (couverture en image, cas du Rapport 2021) :
    # commentaire de l'Annuaire riche en graphiques et presque sans tableaux.
    if "annuaire statistique" in tete and n_graph >= 5 and n_tab < n_graph:
        return "rapport_analyse"
    return "contexte"


def annee_dominante(texte: str) -> Optional[int]:
    freq = Counter(int(y) for y in _ANNEE.findall(texte))
    for m in re.findall(r"exercice\s+(20\d\d)", texte, re.I):
        freq[int(m)] += 5
    if not freq:
        return None
    return max(freq.items(), key=lambda kv: (kv[1], kv[0]))[0]


def detecter_exercice(doc: Document, type_: str) -> tuple:
    """Renvoie (exercice, trimestre|None)."""
    tete = "\n".join(b.texte for p in doc.pages[:2] for b in p.blocs)
    if type_ == "note_conjoncture":
        tr = detecter_trimestre(tete) or detecter_trimestre(doc.texte_complet()[:6000])
        if tr:
            return tr[1], f"T{tr[0]}"
    if type_ == "contexte":
        t = _plat(tete)
        m = re.search(r"n\s?[0o°]\s*\d+\s*/\s*(20\d\d)", t) or re.search(_MOIS + r"\s+(20\d\d)", t)
        if m:
            return int(m.groups()[-1]), None
    return annee_dominante(doc.texte_complet()), None


def titre_canonique(type_: str, exercice: int, trimestre: Optional[str], tete: str) -> str:
    if type_ == "annuaire":
        return f"Annuaire statistique {exercice} sur les PMEESA"
    if type_ == "rapport_analyse":
        return f"Rapport d'analyse de l'Annuaire statistique {exercice}"
    if type_ == "note_conjoncture":
        return f"Note de conjoncture {trimestre} {exercice}"
    # Contexte : première ligne en capitales significative, sinon générique.
    for l in tete.splitlines():
        l = l.strip()
        if 20 <= len(l) <= 140 and not re.search(r"REPUBLI|MINIST|B\.P|Tel|Tél|Fax|Email|DIVISION|Paix", l, re.I):
            return l[:120]
    return f"Document de contexte {exercice}"


def doc_id(type_: str, exercice: int, trimestre: Optional[str], sha: str) -> str:
    if type_ == "note_conjoncture":
        return f"note_conjoncture_{exercice}_{trimestre}"
    if type_ == "contexte":
        return f"contexte_{exercice}_{sha[:6]}"
    return f"{type_}_{exercice}"


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def charger_corrections(corpus: Path) -> dict:
    p = corpus / "registre_corrections.yaml"
    if not p.exists():
        return {}
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("documents", {}) or {}


def decrire(chemin: Path, doc: Document, corrections: dict) -> dict:
    """Fiche registre d'un PDF (détection par le contenu, puis corrections
    manuelles éventuelles, repérées par l'empreinte sha256 du fichier)."""
    sha = sha256(chemin)
    type_ = detecter_type(doc)
    ex, tr = detecter_exercice(doc, type_)
    tete = "\n".join(b.texte for p in doc.pages[:2] for b in p.blocs)
    fiche = {
        "type": type_, "exercice": ex, "trimestre": tr, "statut_diffusion": "publie",
        "fichier": chemin.name, "nb_pages": len(doc.pages), "sha256": sha,
        "titre": titre_canonique(type_, ex, tr, tete),
    }
    corr = corrections.get(sha) or corrections.get(chemin.name) or {}
    fiche.update({k: v for k, v in corr.items() if k in fiche})
    fiche["doc_id"] = corr.get("doc_id") or doc_id(fiche["type"], fiche["exercice"],
                                                    fiche["trimestre"], sha)
    return fiche
