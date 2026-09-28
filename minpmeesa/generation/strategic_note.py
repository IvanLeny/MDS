"""Service 4 : note d'analyse stratégique (BN1 à BN5, sections 3.5.2 à 3.5.4).

Point de départ : les commentaires validés de l'exercice (jamais les tableaux
bruts). Pour chaque indicateur commenté, l'évolution principale (ligne
« Total » si elle existe, sinon la plus forte variation) est notée :

  BN1  score = |var_rel| / écart-type des variations passées de la série
       (moins de 3 points d'historique : |var_rel| seul), + bonus si un
       objectif de politique publique est documenté ; on retient 5 à 7 évolutions ;
  BN2  mise en perspective : même signe sur 3 exercices consécutifs = tendance,
       sinon variation ponctuelle ;
  BN3  rattachement à un objectif SEULEMENT s'il est documenté dans le corpus
       (passage, document, page) ; sinon rien n'est inventé ;
  BN4  chaque énoncé renvoie au commentaire, au tableau, à la page, et chaque
       variation à ses deux valeurs sources ;
  BN5  1 à 2 pages : Messages clés (3), Évolutions marquantes, Points
       d'attention, Pistes pour la décision (sans chiffre), Sources.
Même contrôle de citation littérale que le service 2.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from .. import config
from ..compute.variations import points_du_tableau, variations_historiques
from ..guards.literal_check import ValeurAutorisee, controler
from ..ingestion.pairing import racines
from . import prompts
from .commentary import commenter
from .llm import ClientLLM, LLMIndisponible

_MOT_OBJECTIF = re.compile(r"\bobjectifs?\b|\bcibles?\b|à l[’']horizon|\bvise(nt)? à\b|\bambition|\bSND\s?30|\bCSP\b",
                           re.I)
_GENERIQUES = {"evol", "repa", "nomb", "prop", "pme", "entr", "stoc", "cree", "sele", "sect", "acti", "tota",
               "rapp", "ensemble", "de"}


@dataclass
class Evolution:
    code: str
    intitule: str
    ligne: str
    exercice: int
    exercice_ref: int
    valeur_texte: str
    valeur_ref_texte: str
    var_abs_texte: str
    var_rel_texte: Optional[str]
    var_rel_pct: Optional[float]
    var_abs: float
    valeur_id: int
    valeur_ref_id: int
    tableau_n: Optional[int]
    page: Optional[int]
    doc_annuaire: str
    commentaire_ref: str                     # « validé » ou « généré (prod n) »
    historique: List[dict] = field(default_factory=list)
    volatilite: Optional[float] = None
    score: float = 0.0
    qualification: str = ""
    objectif: Optional[dict] = None


@dataclass
class NoteStrategique:
    exercice: int
    mode: str
    messages: List[dict] = field(default_factory=list)
    evolutions: List[dict] = field(default_factory=list)
    points_attention: List[str] = field(default_factory=list)
    pistes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    tracabilite: List[dict] = field(default_factory=list)
    ecartees: List[dict] = field(default_factory=list)
    avertissements: List[str] = field(default_factory=list)
    projet: bool = False
    nb_mots: int = 0
    verif_bn4: bool = False
    verif_bn5: bool = False
    duree_s: float = 0.0
    prod_id: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
#  BN1 - BN3
# ---------------------------------------------------------------------------
def _serie_historique(base, app: dict, ligne: str, exercice: int) -> List[dict]:
    rows = base.valeurs_tableau(app["doc_annuaire"], app["tableau_n"])
    return [v for v in variations_historiques(points_du_tableau(rows), app["code_indicateur"], exercice)
            if v["ligne"] == ligne]


_EN_LETTRES = {2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six"}


def _qualifier(hist: List[dict], exercice: int, n: int) -> str:
    """BN2 : tendance si même signe sur n exercices consécutifs jusqu'à l'exercice.
    Le nombre d'exercices est écrit en lettres : un chiffre produit par le
    programme hors des valeurs autorisées serait (à juste titre) écarté."""
    par_annee = {h["exercice"]: h["var_abs"] for h in hist}
    derniers = [par_annee.get(a) for a in range(exercice - n + 1, exercice + 1)]
    nb = _EN_LETTRES.get(n, str(n))
    if all(d is not None and d > 0 for d in derniers):
        return f"tendance à la hausse sur {nb} exercices consécutifs ({exercice - n + 1}-{exercice})"
    if all(d is not None and d < 0 for d in derniers):
        return f"tendance à la baisse sur {nb} exercices consécutifs ({exercice - n + 1}-{exercice})"
    if len([d for d in derniers if d is not None]) < n:
        return "historique insuffisant pour qualifier une tendance"
    return "variation ponctuelle (pas de même sens sur les exercices précédents)"


def chercher_objectif(base, texte_indicateur: str, exercice: int) -> Optional[dict]:
    """BN3 : phrase d'un document publié (exercice ≤ exercice traité) qui énonce un
    objectif et partage au moins deux racines significatives avec l'indicateur."""
    cible = racines(texte_indicateur) - _GENERIQUES
    if len(cible) < 2:
        return None
    seuil = float(config.get("strategique.seuil_rattachement_objectif", 0.34))
    meilleur = None
    for r in base.q("SELECT p.passage_id, p.doc_id, p.page, p.texte, d.titre FROM passages p "
                    "JOIN documents d ON d.doc_id = p.doc_id WHERE d.statut_diffusion='publie' "
                    "AND d.exercice <= ? AND p.nature = 'texte'", (exercice,)):
        if not _MOT_OBJECTIF.search(r["texte"]):
            continue
        for ph in re.split(r"(?<=[.!?])\s+", r["texte"]):
            if not _MOT_OBJECTIF.search(ph) or len(ph) > 450:
                continue
            communs = cible & racines(ph)
            s = len(communs) / len(cible)
            if len(communs) >= 2 and s >= seuil and (meilleur is None or s > meilleur["similarite"]):
                meilleur = {"texte": ph.strip(), "doc_id": r["doc_id"], "titre": r["titre"], "page": r["page"],
                            "passage_id": r["passage_id"], "similarite": round(s, 3)}
    return meilleur


def _evolution_principale(base, code: str, exercice: int) -> Optional[dict]:
    vs = [dict(v) for v in base.q("SELECT * FROM variations WHERE code_indicateur=? AND exercice=? "
                                  "AND exercice_ref=? AND var_rel_pct IS NOT NULL", (code, exercice, exercice - 1))]
    vs = [v for v in vs if not v["ligne"].endswith("(%)")]
    if not vs:
        return None
    tot = [v for v in vs if re.sub(r"\(\*\)|\*", "", v["ligne"]).strip().lower() in ("total", "ensemble", "total général")]
    return tot[0] if tot else max(vs, key=lambda v: abs(v["var_rel_pct"]))


def selectionner(base, exercice: int, codes: List[str], refs: dict) -> List[Evolution]:
    cfg = config.get("strategique")
    evols = []
    for code in codes:
        v = _evolution_principale(base, code, exercice)
        if v is None:
            continue
        app = dict(base.q("SELECT * FROM appariement WHERE code_indicateur=? AND exercice=?", (code, exercice))[0])
        val = base.q("SELECT * FROM valeurs WHERE valeur_id IN (?, ?)", (v["valeur_id"], v["valeur_ref_id"]))
        par_id = {r["valeur_id"]: r for r in val}
        hist = _serie_historique(base, app, v["ligne"], exercice)
        passees = [h["var_rel_pct"] for h in hist if h["exercice"] < exercice and h["var_rel_pct"] is not None]
        e = Evolution(code, app["graphique_intitule"] or code, v["ligne"], exercice, v["exercice_ref"],
                      par_id[v["valeur_id"]]["valeur_texte"], par_id[v["valeur_ref_id"]]["valeur_texte"],
                      v["var_abs_texte"], v["var_rel_texte"], v["var_rel_pct"], v["var_abs"], v["valeur_id"],
                      v["valeur_ref_id"], app["tableau_n"], par_id[v["valeur_id"]]["page"], app["doc_annuaire"],
                      refs.get(code, ""), historique=hist)
        if len(passees) >= int(cfg["historique_min_volatilite"]) and statistics.pstdev(passees) > 0:
            e.volatilite = statistics.pstdev(passees)
            e.score = abs(v["var_rel_pct"]) / e.volatilite
        else:
            e.score = abs(v["var_rel_pct"])
        e.qualification = _qualifier(hist, exercice, int(cfg["tendance_meme_signe"]))
        e.objectif = chercher_objectif(base, f"{e.intitule} {e.ligne}", exercice)
        if e.objectif:
            e.score += float(cfg["bonus_objectif"])
        evols.append(e)
    evols.sort(key=lambda e: -e.score)
    # Deux indicateurs appariés au même tableau donneraient la même évolution : une seule est gardée.
    vues, uniques = set(), []
    for e in evols:
        k = (e.doc_annuaire, e.tableau_n, e.ligne)
        if k not in vues:
            vues.add(k)
            uniques.append(e)
    evols = uniques
    n = min(int(cfg["n_max"]), len(evols))
    return evols[:max(n, min(int(cfg["n_min"]), len(evols)))]


# ---------------------------------------------------------------------------
#  Rédaction
# ---------------------------------------------------------------------------
def _lib(e: Evolution) -> str:
    return f"« {e.ligne} » ({e.intitule})"


def _phrase_evolution(e: Evolution) -> str:
    sens = "progresse" if e.var_abs > 0 else "recule"
    t = (f"{_lib(e)} {sens} de {e.var_rel_texte.lstrip('-')} % entre {e.exercice_ref} et {e.exercice} "
         f"({e.valeur_ref_texte} puis {e.valeur_texte}) : {e.qualification}.")
    return t


def _autorisees(evols: List[Evolution]) -> List[ValeurAutorisee]:
    out = []
    for e in evols:
        src = {"genre": "variation", "valeur_id": e.valeur_id, "valeur_ref_id": e.valeur_ref_id,
               "doc_id": e.doc_annuaire, "page": e.page, "tableau_n": e.tableau_n, "code": e.code}
        for t in (e.valeur_texte, e.valeur_ref_texte, e.var_abs_texte, e.var_rel_texte):
            if t:
                out.append(ValeurAutorisee(t, src))
    return out


def _llm_json(llm: ClientLLM, systeme: str, contenu: str, cle: str):
    try:
        rep = llm.generer(systeme, [{"role": "user", "content": contenu}])
        return json.loads(rep.texte).get(cle)
    except (LLMIndisponible, ValueError, AttributeError):
        return None


def rediger_note_strategique(base, exercice: int, llm: ClientLLM, codes: Optional[List[str]] = None,
                             inclure_non_valides: bool = False, journal: bool = True) -> NoteStrategique:
    t0 = time.time()
    note = NoteStrategique(exercice, llm.nom)
    valides = {r["code_indicateur"]: r for r in base.commentaires_valides(exercice)}
    tous = [r["code_indicateur"] for r in base.q(
        "SELECT code_indicateur FROM appariement WHERE exercice=? AND statut != 'rejete' ORDER BY graphique_n",
        (exercice,))]
    codes = codes or tous
    refs, retenus = {}, []
    for c in codes:
        if c in valides:
            refs[c], _ = "commentaire validé", retenus.append(c)
        elif inclure_non_valides:
            com = commenter(base, c, exercice, llm, journal=journal)
            if com.abstention:
                note.points_attention.append(f"{com.intitule} : sources insuffisantes, à commenter manuellement.")
                continue
            refs[c] = f"commentaire généré, non validé (production n° {com.prod_id})"
            retenus.append(c)
            note.projet = True
    if not retenus:
        note.avertissements.append("Aucun commentaire validé pour cet exercice : note non rédigée.")
        return note
    evols = selectionner(base, exercice, retenus, refs)
    aut = _autorisees(evols)
    bornes = tuple(config.get("commentaire.annees_exclues", [2010, 2035]))

    # Messages clés (3) : modèle de langage si disponible, sinon gabarits ; contrôlés.
    top = evols[:3]
    bruts = None
    if llm.actif:
        bruts = _llm_json(llm, prompts.SYSTEME_MESSAGES, "\n".join(_phrase_evolution(e) for e in evols), "messages")
    if not bruts:
        bruts = [{"texte": f"{_lib(e)} : {'+' if e.var_abs > 0 else '-'}{e.var_rel_texte.lstrip('-')} % "
                           f"en {e.exercice} ({e.valeur_texte} contre {e.valeur_ref_texte} en {e.exercice_ref})."}
                 for e in top]
    res = controler([{"type": "constat", **m} for m in bruts[:3]], aut, bornes)
    note.messages = [e.to_dict() for e in res.enonces]
    note.ecartees += [x.__dict__ for x in res.ecartees]

    # Évolutions marquantes (gabarits déterministes, contrôlés aussi).
    res = controler([{"type": "constat", "texte": _phrase_evolution(e)} for e in evols], aut, bornes)
    for e, en in zip(evols, res.enonces):
        d = en.to_dict()
        d.update({"code": e.code, "score_bn1": round(e.score, 3),
                  "volatilite": None if e.volatilite is None else round(e.volatilite, 3),
                  "qualification_bn2": e.qualification, "objectif_bn3": e.objectif,
                  "commentaire": e.commentaire_ref, "tableau_n": e.tableau_n, "page": e.page,
                  "doc_annuaire": e.doc_annuaire, "valeur_id": e.valeur_id, "valeur_ref_id": e.valeur_ref_id})
        note.evolutions.append(d)
    note.ecartees += [x.__dict__ for x in res.ecartees]

    # Points d'attention : reculs et tendances baissières.
    for e in evols:
        if e.var_abs < 0:
            note.points_attention.append(f"{_lib(e)} est en recul : {e.qualification}.")
    # Pistes pour la décision : sans chiffre (liste autorisée vide -> tout chiffre retiré).
    pistes = None
    if llm.actif:
        pistes = _llm_json(llm, prompts.SYSTEME_PISTES, "\n".join(_phrase_evolution(e) for e in evols), "pistes")
    if not pistes:
        pistes = []
        for e in evols[:4]:
            if e.objectif:
                pistes.append(f"Suivre l'écart à l'objectif documenté pour {_lib(e)}.")
            elif e.var_abs < 0:
                pistes.append(f"Examiner les causes du recul de {_lib(e)} avec les services concernés.")
            else:
                pistes.append(f"Consolider les dispositifs qui accompagnent la progression de {_lib(e)}.")
    res = controler([{"type": "perspective", "texte": p} for p in pistes], [], bornes)
    note.pistes = [x.texte for x in res.enonces]

    # Sources et traçabilité (BN4).
    srcs = set()
    for i, e in enumerate(evols, start=1):
        doc = base.document(e.doc_annuaire)
        srcs.add(f"{doc['titre']}, tableau {e.tableau_n}, p. {e.page}")
        if e.objectif:
            srcs.add(f"{e.objectif['titre']}, p. {e.objectif['page']}")
        note.tracabilite.append({
            "enonce": f"E{i}", "texte": note.evolutions[i - 1]["texte"] if i <= len(note.evolutions) else "",
            "commentaire": e.commentaire_ref, "code_indicateur": e.code, "ligne": e.ligne,
            "valeur": e.valeur_texte, "valeur_id": e.valeur_id, "valeur_ref": e.valeur_ref_texte,
            "valeur_ref_id": e.valeur_ref_id, "variation": f"{e.var_rel_texte} %", "document": e.doc_annuaire,
            "tableau_n": e.tableau_n, "page": e.page,
            "objectif": f"{e.objectif['doc_id']} p. {e.objectif['page']}" if e.objectif else ""})
    note.sources = sorted(srcs)

    # Vérifications automatiques BN4 et BN5.
    textes = [m["texte"] for m in note.messages] + [e["texte"] for e in note.evolutions] + \
             note.points_attention + note.pistes
    note.nb_mots = sum(len(t.split()) for t in textes) + sum(len(s.split()) for s in note.sources)
    limite = int(config.get("strategique.pages_max", 2)) * int(config.get("strategique.mots_par_page", 500))
    note.verif_bn5 = note.nb_mots <= limite
    tout = controler([{"type": "constat", "texte": t} for t in textes], aut, bornes)
    note.verif_bn4 = not tout.ecartees and all(t["valeur_id"] and t["valeur_ref_id"] and t["page"]
                                               for t in note.tracabilite)
    if note.projet:
        note.avertissements.insert(0, "PROJET : note fondée sur des commentaires générés, non encore validés.")
    if not llm.actif:
        note.avertissements.append("Mode extractif (sans modèle de langage) : messages et pistes composés "
                                   "par gabarits.")
    note.duree_s = round(time.time() - t0, 3)
    if journal:
        note.prod_id = base.journaliser(
            "note_strategique", {"exercice": exercice, "codes": codes}, note.to_dict(),
            sources=note.tracabilite, ecartees=note.ecartees, abstentions=note.points_attention,
            modele=note.mode, config_hash=config.config_hash(), duree_s=note.duree_s)
    return note
