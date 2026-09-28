"""Extraction du texte, colonnes gérées, avec nettoyage (en-têtes, pieds, n° de page).

Reprise de l'ancien `src/ingestion/extract.py` (lecture positionnée des blocs,
repérage des lignes courantes par récurrence, ordre de lecture sur deux
colonnes), complétée par :
  - la taille de police de chaque ligne (repérage des titres) ;
  - l'exclusion des zones de tableaux (traitées par `tables.py`) ;
  - le repérage des pages de sommaire (points de conduite).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

_CHIFFRES = re.compile(r"\d+")
_ROMAIN = re.compile(r"^[ivxlcdm]+$", re.I)
_CONDUITE = re.compile(r"(\.\s?){5,}|…{2,}")


@dataclass
class Ligne:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    texte: str
    taille: float
    gras: bool
    bloc: int                          # n° du bloc PyMuPDF (paragraphe)


@dataclass
class Page:
    numero: int
    largeur: float
    hauteur: float
    lignes: list[Ligne] = field(default_factory=list)
    sommaire: bool = False             # page de sommaire / liste des tableaux


@dataclass
class Document:
    chemin: str
    pages: list[Page]

    def texte_complet(self) -> str:
        return "\n".join(l.texte for p in self.pages for l in p.lignes)


def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s.lower().strip())
    return _CHIFFRES.sub("#", s)


def lire(chemin: str | Path) -> Document:
    """Lit un PDF : lignes positionnées avec police, page par page."""
    doc = pymupdf.open(str(chemin))
    pages = []
    for i, p in enumerate(doc, start=1):
        lignes = []
        d = p.get_text("dict")
        for nb, b in enumerate(d["blocks"]):
            if b.get("type") != 0:
                continue
            for l in b["lines"]:
                spans = [s for s in l["spans"] if s["text"].strip()]
                if not spans:
                    continue
                texte = re.sub(r"\s+", " ", "".join(s["text"] for s in l["spans"])).strip()
                taille = max(s["size"] for s in spans)
                gras = all(("bold" in s["font"].lower()) or (s["flags"] & 16) for s in spans)
                x0, y0, x1, y1 = l["bbox"]
                lignes.append(Ligne(i, x0, y0, x1, y1, texte, round(taille, 1), bool(gras), nb))
        page = Page(i, p.rect.width, p.rect.height, lignes)
        n_conduite = sum(1 for l in lignes if _CONDUITE.search(l.texte))
        page.sommaire = n_conduite >= 5 or (lignes and n_conduite / len(lignes) > 0.25)
        pages.append(page)
    doc.close()
    return Document(str(chemin), pages)


_NUMEROTATION = re.compile(r"^([IVX]+|\d+(\.\d+)*)\s*[.)]?$|^[•\-–▪]$")


def fusionner_numerotation(doc: Document) -> Document:
    """Recolle un numéro isolé (« 1.1. », « I. ») au titre posé sur la même ligne."""
    for p in doc.pages:
        lignes = sorted(p.lignes, key=lambda l: (round(l.y0), l.x0))
        out: list[Ligne] = []
        for l in lignes:
            if (out and _NUMEROTATION.match(out[-1].texte)
                    and abs((out[-1].y0 + out[-1].y1) / 2 - (l.y0 + l.y1) / 2) < 3
                    and 0 <= l.x0 - out[-1].x1 < 80):
                a = out[-1]
                out[-1] = Ligne(a.page, a.x0, min(a.y0, l.y0), l.x1, max(a.y1, l.y1),
                                f"{a.texte} {l.texte}", max(a.taille, l.taille), a.gras or l.gras, a.bloc)
            else:
                out.append(l)
        p.lignes = out
    return doc


def lignes_courantes(doc: Document, ratio: float = 0.3) -> set[str]:
    """Titres courants et pieds de page : lignes courtes répétées (à numéro près)
    sur au moins `ratio` des pages, situées en haut ou en bas de page."""
    n = max(1, len(doc.pages))
    compte: Counter = Counter()
    for p in doc.pages:
        vues = set()
        for l in p.lignes:
            marge = l.y1 < p.hauteur * 0.12 or l.y0 > p.hauteur * 0.88
            if marge and len(l.texte) <= 120:
                k = _norm(l.texte)
                if k not in vues:
                    vues.add(k)
                    compte[k] += 1
    seuil = max(3, int(ratio * n))
    return {k for k, c in compte.items() if c >= seuil}


def est_numero_page(l: Ligne, p: Page) -> bool:
    t = l.texte.strip()
    marge = l.y1 < p.hauteur * 0.12 or l.y0 > p.hauteur * 0.88
    return marge and (t.isdigit() or bool(_ROMAIN.match(t))) and len(t) <= 5


def nettoyer(doc: Document, ratio: float = 0.3) -> Document:
    """Retire titres courants, pieds de page et numéros de page."""
    courantes = lignes_courantes(doc, ratio)
    for p in doc.pages:
        p.lignes = [l for l in p.lignes
                    if _norm(l.texte) not in courantes and not est_numero_page(l, p)]
    return doc


def dans_zone(l: Ligne, zones: list[tuple[float, float, float, float]], marge: float = 2.0) -> bool:
    cx, cy = (l.x0 + l.x1) / 2, (l.y0 + l.y1) / 2
    return any(x0 - marge <= cx <= x1 + marge and y0 - marge <= cy <= y1 + marge
               for x0, y0, x1, y1 in zones)


def ordre_lecture(p: Page, lignes: list[Ligne]) -> list[Ligne]:
    """Ordre de lecture : deux colonnes si des lignes se tiennent nettement de
    part et d'autre du milieu (sans le chevaucher), sinon haut -> bas."""
    if not lignes:
        return []
    milieu = p.largeur / 2
    gauche = [l for l in lignes if l.x1 <= milieu + p.largeur * 0.03]
    droite = [l for l in lignes if l.x0 >= milieu - p.largeur * 0.03]
    deux_col = (len(gauche) >= 5 and len(droite) >= 5
                and len(gauche) + len(droite) >= 0.8 * len(lignes))
    if deux_col:
        # Les lignes pleine largeur (titres) découpent la page en bandes ; dans
        # chaque bande on lit la colonne de gauche puis celle de droite.
        ids_g, ids_d = {id(l) for l in gauche}, {id(l) for l in droite}
        pleine = sorted((l for l in lignes if id(l) not in ids_g | ids_d), key=lambda l: l.y0)
        bornes = [l.y0 for l in pleine] + [float("inf")]
        sortie, haut = [], float("-inf")
        for i, borne in enumerate(bornes):
            bande = [l for l in lignes if id(l) in ids_g | ids_d and haut <= l.y0 < borne]
            sortie += sorted((l for l in bande if id(l) in ids_g), key=lambda l: (l.y0, l.x0))
            sortie += sorted((l for l in bande if id(l) in ids_d and id(l) not in ids_g),
                             key=lambda l: (l.y0, l.x0))
            if i < len(pleine):
                sortie.append(pleine[i])
            haut = borne
        return sortie
    return sorted(lignes, key=lambda l: (round(l.y0 / 3), l.x0))
