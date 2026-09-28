"""H2 : contrôle de citation littérale (section 2.4.2).

Deux configurations sur les indicateurs appariés de l'exercice évalué :
  - ancrage simple (sans contrôle) ;
  - ancrage + contrôle de citation littérale.
Mesures : valeurs non soutenues (nombre, taux), exactitude Exa, couverture
Couv (valeurs) et Couv_ind (indicateurs), taux de faux rejets TFR (valeur
écartée présente sous une autre écriture dans les sources), typologie des
valeurs écartées, échantillon de 30 valeurs pour relecture manuelle.

Complément (clairement distingué) : le même contrôle appliqué aux commentaires
PUBLIÉS de l'exercice, pour caractériser ce que le contrôle retiendrait ou
écarterait dans une rédaction humaine.
"""
from __future__ import annotations

import csv
import itertools
import random
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pymupdf

from .. import config
from ..generation.commentary import commenter
from ..guards.literal_check import controler, index_autorise, valeurs_non_soutenues
from ..guards.normalize import cles, extraire_nombres
from ..retrieval.indicator_context import contexte_indicateur
from . import metrics as M


# ---------------------------------------------------------------------------
#  Classement d'une valeur écartée
# ---------------------------------------------------------------------------
def _nombres(textes: List[str]) -> List[Decimal]:
    out = []
    for t in textes:
        for n in extraire_nombres(t, bornes_annees=(0, -1), garder_references=True):
            out.append(abs(n.lectures[0]))
    return out


def _texte_pages(base, doc_id: str, pages: List[int]) -> str:
    doc = base.document(doc_id)
    if doc is None:
        return ""
    d = pymupdf.open(config.chemin("corpus") / doc["fichier"])
    t = "\n".join(d[p - 1].get_text() for p in pages if 1 <= p <= len(d))
    d.close()
    return t


def classer(valeur: str, ctx, base, cache: dict) -> str:
    """Typologie d'une valeur écartée (ordre des tests = ordre de priorité) :
    faux_rejet   : la valeur figure sous une autre écriture dans les sources de
                   l'exercice (tableau apparié complet ou texte de sa page) ;
    arrondi      : arrondi d'une valeur autorisée ;
    calcul       : somme, différence, rapport ou taux entre deux valeurs autorisées ;
    autre_exercice : elle figure dans l'Annuaire antérieur apparié ou dans un
                   modèle de rédaction antérieur ;
    absente      : introuvable (invention ou source non appariée)."""
    n = extraire_nombres(valeur, bornes_annees=(0, -1), garder_references=True)
    if not n:
        return "absente"
    k, x = cles(n[0]), abs(n[0].lectures[0])
    cle = (ctx.code, ctx.exercice)
    if cle not in cache:
        app = ctx.appariement or {}
        tab = [r["valeur_texte"] for r in base.valeurs_tableau(app.get("doc_annuaire"), app.get("tableau_n"))] \
            if app.get("tableau_n") else []
        pages = sorted({v["page"] for v in ctx.valeurs})
        page_txt = _texte_pages(base, app.get("doc_annuaire"), pages) if pages else ""
        prec = base.q("SELECT * FROM appariement WHERE code_indicateur=? AND exercice<? AND tableau_n IS NOT NULL",
                      (ctx.code, ctx.exercice))
        anterieur = [r["valeur_texte"] for p in prec for r in base.valeurs_tableau(p["doc_annuaire"], p["tableau_n"])]
        anterieur += [m["texte"] for m in ctx.modeles]
        aut = _nombres([a.texte for a in ctx.autorisees])
        cache[cle] = {"sources": set().union(*[cles(y) for t in tab + [page_txt]
                                               for y in extraire_nombres(t, bornes_annees=(0, -1), garder_references=True)] or [set()]),
                      "anterieur": set().union(*[cles(y) for t in anterieur
                                                 for y in extraire_nombres(t, bornes_annees=(0, -1), garder_references=True)] or [set()]),
                      "aut": aut}
    c = cache[cle]
    if k & c["sources"]:
        return "faux_rejet"
    decs = -x.as_tuple().exponent if x.as_tuple().exponent < 0 else 0
    pas = Decimal(1).scaleb(-decs)
    if any(abs(a.quantize(pas) - x) < pas / 2 for a in c["aut"] if a != x):
        return "arrondi"
    aut = [a for a in c["aut"] if a != 0][:150]
    tol = pas / 2 + Decimal("1e-9")
    for a, b in itertools.permutations(aut, 2):
        for y in (a + b, abs(a - b), 100 * a / b, 100 * (a - b) / b):
            if abs(abs(y) - x) <= tol or abs(abs(y).quantize(pas) - x) < tol:
                return "calcul"
    if k & c["anterieur"]:
        return "autre_exercice"
    return "absente"


# ---------------------------------------------------------------------------
#  Mesures
# ---------------------------------------------------------------------------
def evaluer_h2(base, llm, exercice: int, statuts, dossier: Path, graine: int) -> dict:
    codes = [r["code_indicateur"] for r in base.q(
        f"SELECT code_indicateur FROM appariement WHERE exercice=? AND statut IN ({','.join('?' * len(statuts))}) "
        f"ORDER BY graphique_n", (exercice, *statuts))]
    lignes, ecartees, cache = [], [], {}
    for code in codes:
        ctx = contexte_indicateur(base, code, exercice, statuts)
        sans = commenter(base, code, exercice, llm, controle=False, journal=False, statuts=statuts)
        avec = commenter(base, code, exercice, llm, controle=True, journal=True, statuts=statuts)
        texte_sans = " ".join(e["texte"] for e in sans.enonces)
        texte_avec = " ".join(e["texte"] for e in avec.enonces)
        ns_sans = valeurs_non_soutenues(texte_sans, ctx.autorisees)
        ns_avec = valeurs_non_soutenues(texte_avec, ctx.autorisees)
        n_sans = len(extraire_nombres(texte_sans))
        n_avec = len(extraire_nombres(texte_avec))
        cites = {k for e in avec.enonces for v in e.get("valeurs", []) for k in
                 cles(extraire_nombres(v["valeur"], bornes_annees=(0, -1), garder_references=True)[0])}
        aut_cles = set(index_autorise(ctx.autorisees))
        lignes.append({"code_indicateur": code, "exercice": exercice, "mode": avec.mode,
                       "abstention": avec.abstention or "", "n_autorisees": len(ctx.autorisees),
                       "valeurs_citees_sans_controle": n_sans, "non_soutenues_sans_controle": len(ns_sans),
                       "valeurs_citees_avec_controle": n_avec, "non_soutenues_avec_controle": len(ns_avec),
                       "valeurs_ecartees": len(avec.ecartees),
                       "couverture_valeurs": M.couverture_valeurs(len(cites & aut_cles), len(aut_cles)),
                       "commentaire_non_vide": bool(avec.enonces) and not avec.abstention})
        for e in avec.ecartees:
            ecartees.append({"code_indicateur": code, "exercice": exercice, "valeur": e["valeur"],
                             "type": classer(e["valeur"], ctx, base, cache), "action": e["action"],
                             "enonce_original": e["enonce_original"]})
    return _resumer(lignes, ecartees, dossier, graine, "h2")


def evaluer_publies(base, exercice: int, statuts, dossier: Path, graine: int) -> dict:
    """Contrôle appliqué aux commentaires publiés du Rapport d'analyse de
    l'exercice (texte humain, contre les valeurs autorisées de son contexte)."""
    lignes, ecartees, cache = [], [], {}
    for a in base.q(f"SELECT * FROM appariement WHERE exercice=? AND statut IN ({','.join('?' * len(statuts))}) "
                    f"AND passage_commentaire_id IS NOT NULL ORDER BY graphique_n", (exercice, *statuts)):
        p = base.passages([a["passage_commentaire_id"]])
        if not p:
            continue
        texte = p[0]["texte"].split("\n", 1)[-1]
        ctx = contexte_indicateur(base, a["code_indicateur"], exercice, statuts)
        if not ctx.suffisant or not texte.strip():
            continue
        res = controler([{"type": "constat", "texte": texte}], ctx.autorisees)
        lignes.append({"code_indicateur": a["code_indicateur"], "exercice": exercice, "mode": "commentaire publié",
                       "abstention": "", "n_autorisees": len(ctx.autorisees),
                       "valeurs_citees_sans_controle": res.n_valeurs_citees,
                       "non_soutenues_sans_controle": res.n_valeurs_citees - res.n_valeurs_soutenues,
                       "valeurs_citees_avec_controle": res.n_valeurs_soutenues, "non_soutenues_avec_controle": 0,
                       "valeurs_ecartees": len(res.ecartees), "couverture_valeurs": None,
                       "commentaire_non_vide": bool(res.enonces)})
        for e in res.ecartees:
            ecartees.append({"code_indicateur": a["code_indicateur"], "exercice": exercice, "valeur": e.valeur,
                             "type": classer(e.valeur, ctx, base, cache), "action": e.action,
                             "enonce_original": e.enonce_original[:300]})
    return _resumer(lignes, ecartees, dossier, graine, "h2_publies")


def _resumer(lignes: List[dict], ecartees: List[dict], dossier: Path, graine: int, prefixe: str) -> dict:
    dossier.mkdir(parents=True, exist_ok=True)
    if lignes:
        with open(dossier / f"{prefixe}_par_indicateur.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0]), delimiter=";")
            w.writeheader()
            w.writerows(lignes)
    with open(dossier / f"{prefixe}_valeurs_ecartees.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code_indicateur", "exercice", "valeur", "type", "action",
                                          "enonce_original"], delimiter=";")
        w.writeheader()
        w.writerows(ecartees)
    rnd = random.Random(graine)
    n_ech = int(config.get("evaluation.echantillon_relecture_h2", 30))
    ech = rnd.sample(ecartees, min(n_ech, len(ecartees)))
    with open(dossier / f"{prefixe}_echantillon_relecture.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code_indicateur", "exercice", "valeur", "type", "enonce_original",
                                          "verdict_relecteur (faux_rejet / rejet_justifie)", "remarque"],
                           delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(ech)
    n_ind = len(lignes)
    cit_s = sum(l["valeurs_citees_sans_controle"] for l in lignes)
    ns_s = sum(l["non_soutenues_sans_controle"] for l in lignes)
    cit_a = sum(l["valeurs_citees_avec_controle"] for l in lignes)
    ns_a = sum(l["non_soutenues_avec_controle"] for l in lignes)
    typo: Dict[str, int] = {}
    for e in ecartees:
        typo[e["type"]] = typo.get(e["type"], 0) + 1
    couvs = [l["couverture_valeurs"] for l in lignes if l["couverture_valeurs"] is not None]
    exemples = {}
    for e in ecartees:
        exemples.setdefault(e["type"], [])
        if len(exemples[e["type"]]) < 3:
            exemples[e["type"]].append({"valeur": e["valeur"], "code": e["code_indicateur"],
                                        "extrait": e["enonce_original"][:220]})
    return {
        "n_indicateurs": n_ind,
        "sans_controle": {"valeurs_citees": cit_s, "non_soutenues": ns_s,
                          "taux_non_soutenues": (ns_s / cit_s) if cit_s else None,
                          "exactitude": M.exactitude(cit_s - ns_s, cit_s)},
        "avec_controle": {"valeurs_citees": cit_a, "non_soutenues": ns_a,
                          "taux_non_soutenues": (ns_a / cit_a) if cit_a else None,
                          "exactitude": M.exactitude(cit_a - ns_a, cit_a)},
        "valeurs_ecartees": len(ecartees),
        "tfr_automatique": (typo.get("faux_rejet", 0) / len(ecartees)) if ecartees else None,
        "typologie": typo, "exemples": exemples,
        "couverture_valeurs_moyenne": (sum(couvs) / len(couvs)) if couvs else None,
        "couverture_indicateurs": M.couverture_indicateurs(sum(1 for l in lignes if l["commentaire_non_vide"]), n_ind),
    }
