"""Service 2 : commentaire d'un indicateur (BF2 à BF7, sections 3.2.4 et 3.3).

Chaîne : contexte en trois rubriques -> modèle de langage (sortie JSON, une
nouvelle tentative si le JSON est invalide, puis abstention) -> contrôle de
citation littérale (R0-R3) -> énoncés sourcés -> journal.
Sans modèle de langage (--llm none), le commentaire est composé par des
gabarits déterministes à partir des valeurs et variations (mode extractif).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from .. import config
from ..guards.literal_check import controler
from ..retrieval.indicator_context import Contexte, _est_total, contexte_indicateur
from . import prompts
from .llm import MODE_EXTRACTIF, ClientLLM, LLMIndisponible

MENTION_ABSTENTION = "Sources insuffisantes, à commenter manuellement."


@dataclass
class Commentaire:
    code: str
    exercice: int
    intitule: str
    mode: str
    enonces: List[dict] = field(default_factory=list)          # [{type, texte, valeurs:[{valeur, source}]}]
    ecartees: List[dict] = field(default_factory=list)
    abstention: Optional[str] = None
    modeles: List[dict] = field(default_factory=list)          # sources de forme
    brut: str = ""                                             # sortie brute du modèle (avant contrôle)
    enonces_bruts: List[dict] = field(default_factory=list)
    n_valeurs_citees: int = 0
    n_valeurs_soutenues: int = 0
    n_autorisees: int = 0
    duree_s: float = 0.0
    tentatives: int = 0
    prod_id: Optional[int] = None

    def texte(self) -> str:
        if self.abstention:
            return MENTION_ABSTENTION
        return " ".join(e["texte"] for e in self.enonces)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
#  Lecture de la sortie JSON du modèle
# ---------------------------------------------------------------------------
def lire_json(texte: str) -> Optional[dict]:
    """Objet {"enonces": [...]} ou {"abstention": "..."}, sinon None."""
    if not texte:
        return None
    t = texte.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", t, re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(obj, list):
        obj = {"enonces": obj}
    if not isinstance(obj, dict):
        return None
    if "abstention" in obj and not obj.get("enonces"):
        return {"abstention": str(obj["abstention"])}
    en = obj.get("enonces")
    if not isinstance(en, list) or not en:
        return None
    propres = []
    for e in en:
        if not isinstance(e, dict) or not str(e.get("texte", "")).strip():
            return None
        typ = e.get("type", "constat")
        propres.append({"type": typ if typ in ("constat", "perspective") else "constat",
                        "texte": str(e["texte"]).strip(),
                        "valeurs": [str(v) for v in (e.get("valeurs") or [])]})
    return {"enonces": propres}


# ---------------------------------------------------------------------------
#  Mode extractif : gabarits déterministes
# ---------------------------------------------------------------------------
def _libelle(ligne: str) -> str:
    """Libellé de ligne cité entre guillemets (casse d'origine conservée)."""
    return "« " + ligne.replace(" (%)", "").strip() + " »"


def _rang_total(ligne: str) -> int:
    """0 : total général (« Total ») ; 1 : sous-total (« Adamaoua · Total ») ; 2 : autre."""
    l = ligne.replace(" (%)", "").strip(" *()").lower()
    if re.match(r"^(total|ensemble|cameroun|national)\b", l):
        return 0
    return 1 if _est_total(ligne) else 2


def enonces_extractifs(ctx: Contexte) -> List[dict]:
    """Constats composés à partir des variations calculées (aucun calcul
    supplémentaire, aucune valeur hors contexte). Pas de perspective : elle
    relève du rédacteur."""
    out: List[dict] = []
    niveaux = [v for v in ctx.variations if not v["ligne"].endswith("(%)")]
    n1 = [v for v in niveaux if v["exercice_ref"] == ctx.exercice - 1]
    totaux = sorted([v for v in n1 if _rang_total(v["ligne"]) < 2], key=lambda v: _rang_total(v["ligne"]))
    autres = [v for v in n1 if _rang_total(v["ligne"]) == 2 and v["var_rel_pct"] is not None]

    def sens(v):
        return "hausse" if v["var_abs"] > 0 else ("baisse" if v["var_abs"] < 0 else "stabilité")

    for v in totaux[:1 if totaux and _rang_total(totaux[0]["ligne"]) == 0 else 2]:
        t = (f"En {v['exercice']}, {_libelle(v['ligne'])} s'établit à {v['valeur_texte']} "
             f"contre {v['valeur_ref_texte']} en {v['exercice_ref']}")
        if sens(v) != "stabilité" and v["var_rel_texte"]:
            t += f", soit une {sens(v)} de {v['var_rel_texte'].lstrip('-')} %"
        out.append({"type": "constat", "texte": t + ".", "valeurs": []})
    longs = [v for v in niveaux if _rang_total(v["ligne"]) == 0 and v["exercice_ref"] < ctx.exercice - 1
             and v["var_rel_texte"]]
    if longs:
        v = min(longs, key=lambda x: x["exercice_ref"])
        mot = "la progression" if v["var_abs"] > 0 else "le recul"
        out.append({"type": "constat", "valeurs": [],
                    "texte": (f"Sur la période {v['exercice_ref']}-{v['exercice']}, {mot} de {_libelle(v['ligne'])} "
                              f"atteint {v['var_rel_texte'].lstrip('-')} % (de {v['valeur_ref_texte']} "
                              f"à {v['valeur_texte']}).")})
    if len(autres) >= 2:
        hausse = max(autres, key=lambda x: x["var_rel_pct"])
        baisse = min(autres, key=lambda x: x["var_rel_pct"])
        if hausse["var_rel_pct"] > 0:
            out.append({"type": "constat", "valeurs": [],
                        "texte": f"La plus forte hausse entre {hausse['exercice_ref']} et {hausse['exercice']} "
                                 f"concerne {_libelle(hausse['ligne'])} : {hausse['var_rel_texte']} % "
                                 f"(de {hausse['valeur_ref_texte']} à {hausse['valeur_texte']})."})
        if baisse["var_rel_pct"] < 0 and baisse is not hausse:
            out.append({"type": "constat", "valeurs": [],
                        "texte": f"À l'inverse, {_libelle(baisse['ligne'])} recule de "
                                 f"{baisse['var_rel_texte'].lstrip('-')} % (de {baisse['valeur_ref_texte']} "
                                 f"à {baisse['valeur_texte']})."})
    parts = [v for v in ctx.variations if v["ligne"].endswith("(%)") and v["exercice_ref"] == ctx.exercice - 1
             and _rang_total(v["ligne"]) == 2 and v["var_abs"] != 0]
    if parts:
        v = max(parts, key=lambda x: abs(x["var_abs"]))
        out.append({"type": "constat", "valeurs": [],
                    "texte": f"La part de {_libelle(v['ligne'])} passe de {v['valeur_ref_texte']} % en "
                             f"{v['exercice_ref']} à {v['valeur_texte']} % en {v['exercice']}, soit un écart de "
                             f"{v['var_abs_texte'].lstrip('-')} point(s) de pourcentage."})
    if not out:
        # Pas de série : on restitue les premières valeurs de l'exercice.
        for r in ctx.valeurs[:3]:
            if r["ligne"].startswith("("):
                continue
            col = f" ({r['colonne']})" if r["colonne"] else ""
            out.append({"type": "constat", "valeurs": [],
                        "texte": f"En {ctx.exercice}, {_libelle(r['ligne'])}{col} : {r['valeur_texte']}."})
    return out


# ---------------------------------------------------------------------------
#  Service
# ---------------------------------------------------------------------------
def commenter(base, code: str, exercice: int, llm: ClientLLM, controle: bool = True,
              appui: bool = True, journal: bool = True, statuts=("valide", "candidat")) -> Commentaire:
    t0 = time.time()
    ctx = contexte_indicateur(base, code, exercice, statuts)
    c = Commentaire(code, exercice, ctx.intitule, llm.nom, n_autorisees=len(ctx.autorisees),
                    modeles=[{k: m[k] for k in ("exercice", "doc_id", "page", "passage_id")} for m in ctx.modeles])
    if not ctx.suffisant:
        c.abstention = ctx.motif_insuffisance
    elif not llm.actif:
        c.enonces_bruts = enonces_extractifs(ctx)
        if not c.enonces_bruts:
            c.abstention = "aucune variation ni valeur exploitable"
    else:
        systeme = prompts.SYSTEME_COMMENTAIRE if appui else prompts.SYSTEME_SANS_APPUI
        contexte = prompts.bloc_contexte(ctx.intitule, exercice, ctx.lignes_valeurs(),
                                         ctx.lignes_variations(), ctx.modeles, avec_appui=appui)
        messages = [{"role": "user", "content": contexte}]
        obj = None
        for essai in range(1 + int(config.get("llm.nouvelles_tentatives_json", 1))):
            c.tentatives = essai + 1
            try:
                rep = llm.generer(systeme, messages)
            except LLMIndisponible as e:
                c.abstention = f"modèle de langage indisponible : {e}"
                break
            c.brut = rep.texte
            obj = lire_json(rep.texte)
            if obj is not None:
                break
            messages += [{"role": "assistant", "content": rep.texte},
                         {"role": "user", "content": prompts.CORRECTION_JSON}]
        if c.abstention is None:
            if obj is None:
                c.abstention = "réponse du modèle illisible (JSON invalide après une nouvelle tentative)"
            elif "abstention" in obj:
                c.abstention = f"le modèle s'abstient : {obj['abstention']}"
            else:
                c.enonces_bruts = obj["enonces"]

    if c.enonces_bruts and c.abstention is None:
        bornes = tuple(config.get("commentaire.annees_exclues", [2010, 2035]))
        res = controler(c.enonces_bruts, ctx.autorisees, bornes)
        c.n_valeurs_citees, c.n_valeurs_soutenues = res.n_valeurs_citees, res.n_valeurs_soutenues
        if controle:
            c.enonces = [e.to_dict() for e in res.enonces]
            c.ecartees = [e.__dict__ for e in res.ecartees]
        else:
            # Ancrage simple, sans contrôle : on garde le texte brut (mesure H2).
            c.enonces = [{"type": e["type"], "texte": e["texte"], "texte_original": e["texte"],
                          "valeurs": [], "ecartees": []} for e in c.enonces_bruts]
        if not c.enonces:
            c.abstention = "toutes les valeurs proposées ont été écartées par le contrôle"
    c.duree_s = round(time.time() - t0, 3)
    if journal:
        sources = [{"enonce": i, "valeur": v["valeur"], **v["source"]}
                   for i, e in enumerate(c.enonces) for v in e.get("valeurs", [])]
        c.prod_id = base.journaliser(
            "commentaire", {"code_indicateur": code, "exercice": exercice, "controle": controle, "appui": appui},
            {"enonces": c.enonces, "texte": c.texte(), "brut": c.brut},
            sources=sources + [{"modele_redaction": m} for m in c.modeles], ecartees=c.ecartees,
            abstentions=[c.abstention] if c.abstention else [], modele=c.mode,
            config_hash=config.config_hash(), duree_s=c.duree_s)
    return c
