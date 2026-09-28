"""Découpage en passages munis de leurs métadonnées (sections 2.3.3 et 3.2.1).

Trois natures de passage :
  - texte     : prose découpée en passages de 400 à 800 tokens (config.yaml),
                recouvrement de 10 à 20 %, sans franchir une frontière de page
                (chaque passage renvoie à UNE page, pour la traçabilité) ;
  - tableau   : un tableau linéarisé (« ligne | colonne = valeur ») ;
  - graphique : le commentaire publié d'un graphique d'un Rapport d'analyse.

Chaque passage porte document, page, chapitre, section et nature ; un passage
sans ces métadonnées est rejeté par la base (store/db.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .extract import Document, est_sommaire, lignes_courantes, texte_page

_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

_CHAPITRE = re.compile(
    r"^(CHAPITRE\s+[IVX\d]+\s*[:.\-–]?.*|INTRODUCTION(\s+G[ÉE]N[ÉE]RALE)?|AVANT-PROPOS|Avant-propos|"
    r"R[ÉE]SUM[ÉE]\s+EX[ÉE]CUTIF|CONCLUSION.*|ANNEXES?|BIBLIOGRAPHIE|[IVX]{1,4}\s*[.\-–]\s+[A-ZÉÈ].{3,})$")
# Intertitre numéroté : « 2. Titre », « 1.1 Titre », « 1.1. Titre » (au moins un point,
# pour exclure les notes de bas de page « 25 cas… », « 1 Taux… »).
_SECTION = re.compile(r"^(\d{1,2}\.(?:\d{1,2}\.?){0,3}\s+[A-ZÉÈÀÂÎÔÛ].{2,110})$")
_NUMERO_SEUL = re.compile(r"^\d{1,2}\.(?:\d{1,2}\.?){0,3}$")
_GRAPHIQUE = re.compile(r"^Graphique\s+(\d+)\s*[:.\-–]\s*(.*)$")
_NUMERIQUE = re.compile(r"^[\s\d,.%()+\-–eé]*$")


def compter_tokens(texte: str) -> int:
    """Nombre de tokens (mots et signes de ponctuation). Approximation
    indépendante de l'encodeur, documentée dans docs/ECARTS_MEMOIRE.md."""
    return len(_TOKEN.findall(texte))


@dataclass
class Ligne:
    page: int
    texte: str
    consommee: bool = False


@dataclass
class Graphique:
    numero: int
    intitule: str
    page: int
    commentaire: str
    chapitre: str
    section: str


@dataclass
class Passage:
    page: int
    chapitre: str
    section: str
    nature: str
    texte: str
    code_indicateur: Optional[str] = None
    extra: Dict = field(default_factory=dict)

    @property
    def nb_tokens(self) -> int:
        return compter_tokens(self.texte)


def lignes_document(doc: Document, zones_tableaux: Dict[int, List[tuple]], ratio: float) -> List[Ligne]:
    """Lignes du document dans l'ordre de lecture, hors sommaires, titres
    courants et contenu des tableaux (traités à part)."""
    courantes = lignes_courantes(doc, ratio)
    out: List[Ligne] = []
    for p in doc.pages:
        if est_sommaire(p):
            continue
        zones = zones_tableaux.get(p.numero, [])
        if zones:
            gardes = []
            for b in p.blocs:
                cx, cy = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
                if not any(z[0] - 2 <= cx <= z[2] + 2 and z[1] - 2 <= cy <= z[3] + 2 for z in zones):
                    gardes.append(b)
            p = type(p)(p.numero, p.largeur, p.hauteur, gardes)
        attente = ""
        for l in texte_page(p, courantes).splitlines():
            l = re.sub(r"\s+", " ", l).strip()
            if not l:
                continue
            if _NUMERO_SEUL.match(l):
                attente = l                      # « 1.1. » seul : le titre suit
                continue
            if attente:
                l, attente = f"{attente} {l}", ""
            out.append(Ligne(p.numero, l))
    return out


def _titre_suite(lignes: List[Ligne], i: int) -> Tuple[str, int]:
    """Intitulé d'un graphique : la légende et, si elle se poursuit, la ligne suivante."""
    m = _GRAPHIQUE.match(lignes[i].texte)
    titre, j = m.group(2).strip(), i
    if i + 1 < len(lignes):
        s = lignes[i + 1].texte
        if (len(s) < 70 and not s.lower().startswith("source") and
                (s[:1].islower() or re.match(r"^(de|à|du|des|et|par|selon|\(en)\b", s))):
            titre, j = f"{titre} {s}", i + 1
    return titre.strip(" ."), j


def _est_titre(l: str) -> bool:
    return bool(_CHAPITRE.match(l) or (_SECTION.match(l) and len(l) < 120 and not l.endswith(",")))


def graphiques_rapport(lignes: List[Ligne]) -> List[Graphique]:
    """Commentaire de chaque graphique : les lignes qui suivent la légende,
    débarrassées de la ligne « Source » et des étiquettes de données du
    graphique (nombres isolés, courtes suites de libellés), jusqu'à la légende
    suivante ou au prochain titre de section."""
    chap, sec = "Préambule", ""
    out: List[Graphique] = []
    i = 0
    while i < len(lignes):
        t = lignes[i].texte
        if _CHAPITRE.match(t):
            chap, sec = t, ""
        elif _SECTION.match(t) and len(t) < 120:
            sec = t
        m = _GRAPHIQUE.match(t)
        if not m:
            i += 1
            continue
        num = int(m.group(1))
        titre, j = _titre_suite(lignes, i)
        k = j + 1
        corps: List[Ligne] = []
        while k < len(lignes):
            s = lignes[k].texte
            if _GRAPHIQUE.match(s) or _est_titre(s):
                break
            corps.append(lignes[k])
            k += 1
        for x in lignes[i:k]:
            x.consommee = True
        texte = _nettoyer_commentaire([c.texte for c in corps])
        if num not in {g.numero for g in out}:
            out.append(Graphique(num, titre, lignes[i].page, texte, chap, sec or chap))
        i = k
    return out


def _nettoyer_commentaire(lignes: List[str]) -> str:
    gardees: List[str] = []
    courtes: List[str] = []

    def vider():
        # Une seule ligne courte = fin de paragraphe ; plusieurs = étiquettes de graphique.
        if len(courtes) == 1:
            gardees.append(courtes[0])
        courtes.clear()

    for l in lignes:
        if l.lower().startswith("source") or _NUMERIQUE.match(l):
            vider()
            continue
        if len(l) < 35:
            courtes.append(l)
            continue
        vider()
        gardees.append(l)
    vider()
    texte = " ".join(gardees)
    texte = re.sub(r"(\w)- (\w)", r"\1-\2", texte)
    return re.sub(r"\s+", " ", texte).strip()


def decouper(texte: str, min_tok: int, max_tok: int, recouvrement: float, min_absolu: int) -> List[str]:
    """Découpe un texte en passages de min_tok à max_tok tokens, aux frontières
    de phrase, avec un recouvrement (fraction) entre passages successifs."""
    phrases = [p for p in re.split(r"(?<=[.!?;])\s+", texte) if p.strip()]
    out: List[str] = []
    cour: List[str] = []
    n = 0
    for ph in phrases:
        k = compter_tokens(ph)
        if cour and n + k > max_tok and n >= min_tok:
            out.append(" ".join(cour))
            # Recouvrement : on reprend les dernières phrases jusqu'à la fraction voulue.
            garde, g = [], 0
            for x in reversed(cour):
                if g >= recouvrement * n:
                    break
                garde.insert(0, x)
                g += compter_tokens(x)
            cour, n = garde, g
        cour.append(ph)
        n += k
    if cour:
        reste = " ".join(cour)
        if out and compter_tokens(reste) < min_absolu:
            out[-1] = out[-1] + " " + reste
        else:
            out.append(reste)
    return out


def passages_texte(lignes: List[Ligne], cfg: dict, chapitre_defaut: str) -> List[Passage]:
    """Passages de prose : segments (page, chapitre, section) découpés en passages."""
    chap, sec = chapitre_defaut, ""
    segs: List[Tuple[int, str, str, List[str]]] = []
    for l in lignes:
        t = l.texte
        if _CHAPITRE.match(t):
            chap, sec = t[:150], ""
        elif _SECTION.match(t) and len(t) < 120:
            sec = t[:150]
        if l.consommee:
            continue
        if not segs or segs[-1][0] != l.page or segs[-1][1] != chap or segs[-1][2] != (sec or chap):
            segs.append((l.page, chap, sec or chap, []))
        segs[-1][3].append(t)
    out: List[Passage] = []
    for page, c, s, ls in segs:
        texte = re.sub(r"\s+", " ", " ".join(ls)).strip()
        if compter_tokens(texte) < 8:
            continue
        for morceau in decouper(texte, cfg["passage_min_tokens"], cfg["passage_max_tokens"],
                                cfg["recouvrement"], cfg["passage_min_absolu"]):
            out.append(Passage(page, c, s, "texte", morceau))
    return out


def section_de_page(lignes: List[Ligne], chapitre_defaut: str) -> Dict[int, Tuple[str, str]]:
    """Chapitre et section en vigueur au début de chaque page (pour les tableaux)."""
    chap, sec = chapitre_defaut, ""
    out: Dict[int, Tuple[str, str]] = {}
    for l in lignes:
        if _CHAPITRE.match(l.texte):
            chap, sec = l.texte[:150], ""
        elif _SECTION.match(l.texte) and len(l.texte) < 120:
            sec = l.texte[:150]
        out.setdefault(l.page, (chap, sec or chap))
    return out


def rubrique_pour(page: int, sections: Dict[int, Tuple[str, str]], defaut: str) -> Tuple[str, str]:
    """Rubrique de la page, ou de la dernière page précédente qui en a une."""
    prec = [p for p in sections if p <= page]
    return sections[max(prec)] if prec else (defaut, defaut)
