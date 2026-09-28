"""Découpage en passages (section 2.3.3, Tableau 2.4).

Trois natures de passage :
  - `texte`     : prose, fenêtres de 400 à 800 tokens avec 10-20 % de
                  recouvrement, sans franchir une frontière de chapitre ;
                  dans un Rapport d'analyse, la prose est découpée PAR GRAPHIQUE
                  (le commentaire d'un graphique = une unité, cf. appariement) ;
  - `tableau`   : un tableau linéarisé (« ligne | colonne = valeur ») ;
  - `graphique` : légende, source et valeurs affichées d'un graphique.

Chaque passage porte les métadonnées du Tableau 2.4 (document, page, chapitre,
section, nature, indicateur). Un passage incomplet est rejeté.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import Document, Ligne, dans_zone, ordre_lecture
from .tables import TableauExtrait, est_nombre

_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_CHAPITRE = re.compile(r"^(CHAPITRE|Chapitre|PARTIE|Partie)\s+([IVX]+|\d+)\b\s*[:.\-–]?\s*(.*)$")
_CHAP_ROMAIN = re.compile(r"^([IVX]+)\s*[.\-–]\s+([A-ZÉÈÀÇ][^a-z]{3,})$")
_CHAP_NOMME = re.compile(r"^(INTRODUCTION( GÉNÉRALE| GENERALE)?|CONCLUSION( GÉNÉRALE| GENERALE)?|"
                         r"AVANT[- ]PROPOS|RÉSUMÉ EXÉCUTIF|RESUME EXECUTIF|ANNEXES?|BIBLIOGRAPHIE|"
                         r"Introduction|Conclusion|Avant-Propos)\s*$")
_SECTION = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s+([A-ZÉÈÀÇa-zé][^\n]{2,130})$")
_GRAPHIQUE = re.compile(r"^(Graphique|Figure)\s+(\d+)\s*[:.\-–]\s*(.*)$", re.I)
_TABLEAU = re.compile(r"^Tableau\s+(\d+)\s*[:.\-–]", re.I)
_SOURCE = re.compile(r"^Sources?\s*:", re.I)


def compter_tokens(texte: str) -> int:
    """Nombre de tokens (mots et signes). Approximation hors ligne du découpage
    en sous-mots de l'encodeur (voir docs/ECARTS_MEMOIRE.md)."""
    return len(_TOKEN.findall(texte))


@dataclass
class Passage:
    doc_id: str
    page: int
    page_fin: int
    chapitre: str
    section: str
    nature: str
    texte: str
    code_indicateur: str | None = None
    numero: int | None = None
    nb_tokens: int = 0

    def __post_init__(self):
        self.nb_tokens = self.nb_tokens or compter_tokens(self.texte)


REQUIS = ("doc_id", "page", "page_fin", "chapitre", "section", "nature", "texte")


def valider(p: Passage, plancher: int) -> str | None:
    """Motif de rejet, ou None si le passage est complet (2.3.3)."""
    for champ in REQUIS:
        if getattr(p, champ) in (None, ""):
            return f"métadonnée manquante : {champ}"
    if p.nature not in ("texte", "tableau", "graphique"):
        return f"nature inconnue : {p.nature}"
    if p.nb_tokens < plancher:
        return f"trop court ({p.nb_tokens} tokens)"
    return None


@dataclass
class _Etat:
    chapitre: str = "Partie liminaire"
    section: str = "(début du document)"


@dataclass
class _Unite:
    lignes: list[Ligne] = field(default_factory=list)
    chapitre: str = ""
    section: str = ""
    graphique: int | None = None       # graphique dont cette prose est le commentaire
    frontiere_suivante: str = ""       # 'graphique' | 'section' | 'chapitre' | 'fin'


@dataclass
class _Graphique:
    numero: int
    titre: str
    page: int
    y: float
    chapitre: str
    section: str
    source: str = ""
    etiquettes: list[str] = field(default_factory=list)


def _titre(l: Ligne, taille_corps: float = 11.0) -> tuple[str, str] | None:
    """('chapitre'|'section', libellé) si la ligne est un titre."""
    t = l.texte.strip()
    if _CONDUITE_RE.search(t):
        return None
    m = _CHAPITRE.match(t)
    if m:
        return "chapitre", re.sub(r"\s+", " ", t)
    if _CHAP_NOMME.match(t) or (_CHAP_ROMAIN.match(t) and len(t) < 120):
        return "chapitre", t
    m = _SECTION.match(t)
    if m and len(t) < 135 and not t.endswith((",", ";")):
        premier = int(m.group(1).split(".")[0])
        reste = m.group(2)
        if premier <= 12 and not est_nombre(reste.split()[0]) and not re.match(r"^(%|ans?\b|mois\b)", reste):
            marque = l.gras or l.taille > taille_corps + 0.4
            numero_pointe = "." in m.group(1) or bool(re.match(r"^\d+\.\s", t))
            if marque or (numero_pointe and len(t) < 100 and not t.endswith(".")):
                return "section", t
    return None


_CONDUITE_RE = re.compile(r"(\.\s?){5,}")


def _est_etiquette(l: Ligne) -> bool:
    """Ligne typique d'étiquette de graphique : nombre, année, libellé très court."""
    t = l.texte.strip()
    mots = t.split()
    return est_nombre(t) or len(mots) <= 3 and not t.endswith((".", ":", ";"))


def segmenter(doc: Document, doc_id: str, type_doc: str, tableaux: list[TableauExtrait],
              cfg: dict) -> tuple[list[Passage], list[_Graphique], list[tuple[Passage, str]]]:
    """Découpe un document. Renvoie (passages valides, graphiques, rejets)."""
    etat = _Etat()
    unites: list[_Unite] = [_Unite(chapitre=etat.chapitre, section=etat.section)]
    graphiques: list[_Graphique] = []
    reperes: list[tuple[int, float, str, str]] = []   # (page, y, chapitre, section)
    zones = {}
    for t in tableaux:
        zones.setdefault(t.page, []).append(t.bbox)

    def nouvelle_unite(frontiere: str, graphique: int | None = None):
        unites[-1].frontiere_suivante = frontiere
        unites.append(_Unite(chapitre=etat.chapitre, section=etat.section, graphique=graphique))

    tailles = sorted(l.taille for p in doc.pages for l in p.lignes if len(l.texte) > 40)
    taille_corps = tailles[len(tailles) // 2] if tailles else 11.0
    for p in doc.pages:
        if p.sommaire:
            continue
        lignes = [l for l in p.lignes if not dans_zone(l, zones.get(p.numero, []))]
        lignes = ordre_lecture(p, lignes)
        # Blocs d'étiquettes : blocs dont la plupart des lignes sont des nombres
        # ou des libellés très courts (valeurs affichées d'un graphique).
        par_bloc: dict[int, list[Ligne]] = {}
        for l in lignes:
            par_bloc.setdefault(l.bloc, []).append(l)
        bloc_etiq = {b: (sum(len(x.texte.split()) for x in ls) < 8
                         or sum(_est_etiquette(x) for x in ls) >= 0.6 * len(ls))
                     for b, ls in par_bloc.items()}
        graph_page = [g for g in graphiques if g.page == p.numero]
        i = 0
        while i < len(lignes):
            l = lignes[i]
            t = l.texte.strip()
            titre = _titre(l, taille_corps)
            mg = _GRAPHIQUE.match(t)
            if mg:
                titre_g = mg.group(3).strip()
                # la légende peut se poursuivre sur la ligne suivante
                if i + 1 < len(lignes) and 0 <= lignes[i + 1].y0 - l.y1 < 10 and len(lignes[i + 1].texte) < 100 \
                        and not _SOURCE.match(lignes[i + 1].texte) and not est_nombre(lignes[i + 1].texte):
                    titre_g += " " + lignes[i + 1].texte.strip()
                    i += 1
                g = _Graphique(int(mg.group(2)), titre_g.strip(" ."), p.numero, l.y0,
                               etat.chapitre, etat.section)
                graphiques.append(g)
                graph_page.append(g)
                nouvelle_unite("graphique", graphique=g.numero)
            elif _TABLEAU.match(t):
                pass                                   # tableaux traités à part
            elif _SOURCE.match(t):
                cible = max((g for g in graph_page if g.y <= l.y0 + 1), key=lambda g: g.y, default=None)
                if cible and not cible.source:
                    cible.source = t
            elif titre:
                genre, lib = titre
                if genre == "chapitre":
                    # le titre du chapitre peut se poursuivre sur la ligne suivante
                    if i + 1 < len(lignes) and lignes[i + 1].texte.isupper() and 0 <= lignes[i + 1].y0 - l.y1 < 8:
                        lib += " " + lignes[i + 1].texte.strip()
                        i += 1
                    etat.chapitre, etat.section = lib, "(introduction du chapitre)"
                else:
                    etat.section = lib
                reperes.append((p.numero, l.y0, etat.chapitre, etat.section))
                nouvelle_unite(genre)
            elif bloc_etiq.get(l.bloc) and _est_etiquette(l):
                if graph_page:
                    cible = min(graph_page, key=lambda g: abs(g.y - l.y0) if g.y <= l.y0 else 1e9 + g.y)
                    cible.etiquettes.append(t)
                # sinon : fragment isolé (en-tête résiduel), ignoré
            else:
                unites[-1].lignes.append(l)
            i += 1
    unites[-1].frontiere_suivante = "fin"

    ing = cfg["ingestion"]
    passages: list[Passage] = []
    if type_doc == "rapport_analyse":
        passages += _prose_par_graphique(unites, doc_id, ing)
    else:
        passages += _fenetres(unites, doc_id, ing)
    passages += _passages_graphiques(graphiques, doc_id)
    passages += _passages_tableaux(tableaux, doc_id, reperes, ing)

    valides, rejets = [], []
    for ps in passages:
        motif = valider(ps, ing["passage_tokens_plancher"])
        (rejets.append((ps, motif)) if motif else valides.append(ps))
    return valides, graphiques, rejets


def _texte(lignes: list[Ligne]) -> str:
    """Recolle les lignes, coupures de mots en fin de ligne comprises."""
    out = ""
    for l in lignes:
        t = l.texte.strip()
        if out.endswith("-") and t[:1].islower():
            out = out[:-1] + t
        else:
            out = f"{out} {t}" if out else t
    return re.sub(r"\s+", " ", out).strip()


def _fenetres(unites: list[_Unite], doc_id: str, ing: dict,
              graphique: int | None = None) -> list[Passage]:
    """Fenêtres glissantes de 400 à 800 tokens, par chapitre, avec recouvrement."""
    tmax, tmin = ing["passage_tokens_max"], ing["passage_tokens_min"]
    recouv = ing["recouvrement"]
    out: list[Passage] = []
    # Regroupe les unités consécutives d'un même chapitre.
    groupes: list[list[_Unite]] = []
    for u in unites:
        if not u.lignes:
            continue
        if groupes and groupes[-1][-1].chapitre == u.chapitre:
            groupes[-1].append(u)
        else:
            groupes.append([u])
    for g in groupes:
        # phrases avec leur page et leur section
        phrases: list[tuple[str, int, str]] = []
        for u in g:
            for l in u.lignes:
                phrases.append((l.texte.strip(), l.page, u.section))
        debut = 0
        while debut < len(phrases):
            fin, n = debut, 0
            while fin < len(phrases) and (n < tmin or n + compter_tokens(phrases[fin][0]) <= tmax):
                n += compter_tokens(phrases[fin][0])
                fin += 1
            morceau = phrases[debut:fin]
            texte = _texte([_L(t) for t, _, _ in morceau])
            out.append(Passage(doc_id, morceau[0][1], morceau[-1][1], g[0].chapitre,
                               morceau[0][2] or "(sans section)", "texte", texte,
                               numero=graphique))
            if fin >= len(phrases):
                break
            # recouvrement : on recule d'environ `recouv` de la fenêtre
            recul, k = 0, fin
            while k > debut + 1 and recul < recouv * n:
                k -= 1
                recul += compter_tokens(phrases[k][0])
            debut = max(k, debut + 1)
    return out


class _L:
    """Ligne minimale pour `_texte`."""
    def __init__(self, texte: str):
        self.texte = texte


def _prose_par_graphique(unites: list[_Unite], doc_id: str, ing: dict) -> list[Passage]:
    """Rapport d'analyse : le commentaire d'un graphique = la prose qui le suit,
    plus l'introduction de section qui précède directement le premier graphique."""
    # Rattache l'introduction de section au graphique qui suit immédiatement.
    for k, u in enumerate(unites[:-1]):
        if u.graphique is None and u.frontiere_suivante == "graphique" and u.lignes:
            u.graphique = unites[k + 1].graphique
    par_graph: dict[int, list[_Unite]] = {}
    libres: list[_Unite] = []
    for u in unites:
        if not u.lignes:
            continue
        if u.graphique is not None:
            par_graph.setdefault(u.graphique, []).append(u)
        else:
            libres.append(u)
    out = _fenetres(libres, doc_id, ing)
    for n, us in par_graph.items():
        lignes = [l for u in us for l in u.lignes]
        texte = _texte(lignes)
        if compter_tokens(texte) <= ing["passage_tokens_max"]:
            out.append(Passage(doc_id, lignes[0].page, lignes[-1].page, us[0].chapitre,
                               us[0].section, "texte", texte, numero=n))
        else:
            out += _fenetres(us, doc_id, ing, graphique=n)
    return out


def _passages_graphiques(graphiques: list[_Graphique], doc_id: str) -> list[Passage]:
    out = []
    for g in graphiques:
        corps = [f"Graphique {g.numero} : {g.titre}"]
        if g.source:
            corps.append(g.source)
        if g.etiquettes:
            corps.append("Valeurs et libellés affichés : " + " ; ".join(g.etiquettes))
        out.append(Passage(doc_id, g.page, g.page, g.chapitre, g.section, "graphique",
                           "\n".join(corps), numero=g.numero))
    return out


def _repere(reperes, page: int, y: float) -> tuple[str, str]:
    avant = [r for r in reperes if (r[0], r[1]) <= (page, y)]
    if not avant:
        return "Partie liminaire", "(début du document)"
    return avant[-1][2], avant[-1][3]


def _passages_tableaux(tableaux: list[TableauExtrait], doc_id: str, reperes, ing: dict) -> list[Passage]:
    out = []
    tmax = ing["passage_tokens_max"]
    for t in tableaux:
        chap, sect = _repere(reperes, t.page, t.bbox[1])
        titre = (f"Tableau {t.numero} : {t.intitule}" if t.numero
                 else f"Tableau sans intitulé (page {t.page})")
        if t.suite:
            titre += " (suite)"
        lignes = t.texte_linearise()
        bloc: list[str] = []
        for lg in lignes + [None]:
            if lg is not None and compter_tokens("\n".join([titre] + bloc + [lg])) <= tmax:
                bloc.append(lg)
                continue
            if bloc:
                texte = "\n".join([titre] + bloc + ([t.source] if t.source else []))
                out.append(Passage(doc_id, t.page, t.page, chap, sect, "tableau", texte, numero=t.numero))
            bloc = [lg] if lg is not None else []
    return out
