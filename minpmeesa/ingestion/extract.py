"""Extraction du texte, consciente des colonnes, et nettoyage (section 3.2.1).

Repris du prototype antérieur (src/ingestion/extract.py) : blocs positionnés,
ordre de lecture sur deux colonnes, repérage des titres courants et numéros
de page par récurrence. Ajouts : repérage des pages de sommaire (points de
conduite) et retrait des lignes « Source : … ».
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pymupdf

try:  # message d'information de PyMuPDF sans intérêt pour l'utilisateur
    pymupdf.TOOLS.set_small_glyph_heights(False)
    pymupdf.no_recommend_layout()  # type: ignore[attr-defined]
except Exception:
    pass


@dataclass
class Bloc:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    texte: str


@dataclass
class Page:
    numero: int                   # numéro de page du PDF (1-indexé)
    largeur: float
    hauteur: float
    blocs: List[Bloc] = field(default_factory=list)


@dataclass
class Document:
    chemin: str
    pages: List[Page]

    def texte_complet(self) -> str:
        return "\n".join(b.texte for p in self.pages for b in p.blocs)


def extraire(chemin: str | Path) -> Document:
    """Ouvre un PDF et renvoie ses pages avec blocs positionnés."""
    doc = pymupdf.open(str(chemin))
    pages: List[Page] = []
    for i, page in enumerate(doc, start=1):
        blocs = []
        for b in page.get_text("blocks"):
            t = (b[4] or "").strip()
            if t and b[6] == 0:                   # blocs de texte uniquement
                blocs.append(Bloc(i, b[0], b[1], b[2], b[3], t))
        pages.append(Page(i, page.rect.width, page.rect.height, blocs))
    doc.close()
    return Document(str(chemin), pages)


def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s.lower().strip())
    return re.sub(r"\d+", "#", s)                 # numéros de page masqués


def lignes_courantes(doc: Document, ratio: float = 0.5) -> set:
    """Titres courants et numéros de page : lignes courtes répétées (à numéro
    près) sur au moins `ratio` des pages."""
    n = max(1, len(doc.pages))
    c: Counter = Counter()
    for p in doc.pages:
        vues = set()
        for b in p.blocs:
            for l in b.texte.splitlines():
                l = l.strip()
                if l and len(l) <= 90:
                    k = _norm(l)
                    if k not in vues:
                        vues.add(k)
                        c[k] += 1
    seuil = max(3, int(ratio * n))
    out = {k for k, v in c.items() if v >= seuil}
    out.add("#")                                  # numéro de page seul
    return out


_ROMAIN = re.compile(r"^[ivxlc]+$", re.I)


def est_sommaire(page: Page) -> bool:
    """Page de sommaire ou de liste (tableaux, graphiques) : points de conduite."""
    lignes = [l for b in page.blocs for l in b.texte.splitlines() if l.strip()]
    if not lignes:
        return False
    conduite = sum(1 for l in lignes if re.search(r"\.{5,}", l))
    return conduite >= 4 and conduite / len(lignes) >= 0.2


def texte_page(page: Page, courantes: set) -> str:
    """Texte de la page dans l'ordre de lecture, titres courants, numéros de
    page et lignes « Source : » retirés. Deux colonnes gérées."""
    def garder(l: str) -> bool:
        s = l.strip()
        if not s or _norm(s) in courantes or _ROMAIN.match(s):
            return False
        return not re.match(r"^sources?\s*:", s, re.I)

    blocs = []
    for b in page.blocs:
        lignes = [l for l in b.texte.splitlines() if garder(l)]
        if lignes:
            blocs.append(Bloc(b.page, b.x0, b.y0, b.x1, b.y1, "\n".join(lignes)))
    if not blocs:
        return ""
    mid = page.largeur / 2.0
    g = [b for b in blocs if b.x1 <= mid + page.largeur * 0.05]
    d = [b for b in blocs if b.x0 >= mid - page.largeur * 0.05]
    deux_col = len(g) >= 2 and len(d) >= 2 and (len(g) + len(d)) >= 0.7 * len(blocs)
    if deux_col:
        ordre = sorted(g, key=lambda b: b.y0) + sorted(d, key=lambda b: b.y0)
        reste = [b for b in blocs if b not in g and b not in d]
        ordre = sorted(reste, key=lambda b: b.y0) + ordre
    else:
        ordre = sorted(blocs, key=lambda b: (round(b.y0), b.x0))
    return "\n".join(b.texte for b in ordre)
