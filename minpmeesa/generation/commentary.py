"""Service 2 : commentaire d'un indicateur (BF2 à BF7, sections 3.2.4 et 3.3).

code_indicateur + exercice -> contexte en trois rubriques -> rédaction (modèle de
langage en JSON, ou gabarits extractifs sans modèle) -> contrôle de citation
littérale -> traçabilité -> journal. Abstention visible si les sources manquent.
"""
from __future__ import annotations

import json
import re
import time

from .. import config
from ..guards import abstention as abst
from ..guards import literal_check, provenance
from ..retrieval import indicator_context as ic
from ..store import db
from . import prompts
from .llm import ClientLLM, ErreurLLM, decrire

MODE_EXTRACTIF = "extractif (sans modèle de langage)"


# ------------------------------------------------------------ JSON du modèle
def lire_json(brut: str) -> dict | None:
    """Réponse du modèle -> {"enonces": [...]} ou {"abstention": ...} ; None si invalide."""
    if not brut:
        return None
    s = brut.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        d = json.loads(s)
    except ValueError:
        m = re.search(r"(\{.*\}|\[.*\])", s, re.S)
        if not m:
            return None
        try:
            d = json.loads(m.group(1))
        except ValueError:
            return None
    if isinstance(d, list):
        d = {"enonces": d}
    if not isinstance(d, dict):
        return None
    if "abstention" in d and not d.get("enonces"):
        return {"abstention": str(d["abstention"])}
    en = d.get("enonces")
    if not isinstance(en, list) or not en:
        return None
    propres = []
    for e in en:
        if not isinstance(e, dict) or not isinstance(e.get("texte"), str) or not e["texte"].strip():
            return None
        t = str(e.get("type", "constat")).lower()
        propres.append({"type": "perspective" if t.startswith("persp") else "constat",
                        "texte": e["texte"].strip(),
                        "valeurs": [str(v) for v in e.get("valeurs", []) if v is not None]})
    return {"enonces": propres}


def generer_llm(client: ClientLLM, systeme: str, utilisateur: str, tentatives: int = 1) -> tuple[dict | None, list[str]]:
    """Appel au modèle ; un JSON invalide donne lieu à `tentatives` nouvelle(s) tentative(s)."""
    bruts = []
    msg = utilisateur
    for _ in range(1 + tentatives):
        brut = client.generer(systeme, msg, json_attendu=True)
        bruts.append(brut)
        d = lire_json(brut)
        if d is not None:
            return d, bruts
        msg = f"{utilisateur}\n\n{prompts.CORRECTION_JSON}"
    return None, bruts


# ------------------------------------------------------------ mode extractif
def _suffixe(u: str | None) -> str:
    if u == "%":
        return " %"
    return f" {u}" if u else ""


def _sans_signe(t: str) -> str:
    return t.lstrip("-−+")


def _verbe(x: float, hausse: str, baisse: str, stable: str = "reste stable") -> str:
    return hausse if x > 0 else baisse if x < 0 else stable


def _une_colonne(vals: list[dict]) -> list[dict]:
    """Tableau à deux dimensions : on ne lit qu'UNE colonne (la colonne « Total »
    s'il y en a une ; sinon la seule colonne présente ; sinon rien)."""
    cols = list(dict.fromkeys(v["colonne"] for v in vals))
    if len(cols) <= 1:
        return vals
    tot = [c for c in cols if re.search(r"\btotal\b|ensemble", c, re.I)]
    return [v for v in vals if v["colonne"] == tot[-1]] if tot else []


def extractif(ctx: ic.Contexte) -> list[dict]:
    """Gabarits déterministes à partir des seules valeurs et variations du contexte."""
    ex = ctx.exercice
    vals = [v for v in ctx.valeurs if v["valeur_num"] is not None and v["ligne"] != "(sans libellé)"]
    courant = [v for v in vals if v["annee_colonne"] == ex] or [v for v in vals if v["annee_colonne"] is None]
    if not courant:
        return []
    est_total = lambda l: bool(re.search(r"(^|/\s*)total", l, re.I))
    niveaux = _une_colonne([v for v in courant if v["unite"] != "%" and "%" not in (v["sous_colonne"] or "")])
    parts = _une_colonne([v for v in courant if v["unite"] == "%" or "%" in (v["sous_colonne"] or "")])
    enonces = []
    tit = ctx.tableau_intitule or ctx.indicateur
    # total général uniquement (pas un sous-total « Yaoundé / Total »)
    tot = next((v for v in niveaux if re.fullmatch(
        r"\s*total(\s+(g[ée]n[ée]ral|pme|national|ensemble))?(\s*/\s*total)?\s*", v["ligne"], re.I)), None)
    if tot:
        enonces.append({"type": "constat", "texte": f"En {ex}, pour « {tit} », le total s'établit à "
                        f"{tot['valeur_texte']}{_suffixe(tot['unite'])}."})
        var = [d for d in ctx.variations if d["valeur_id"] == tot["valeur_id"] and d["var_rel_texte"]]
        prec = next((d for d in var if d["exercice_ref"] == ex - 1), None)
        if prec:
            enonces.append({"type": "constat", "texte":
                            f"Par rapport à {ex - 1}, ce total {_verbe(prec['var_rel_pct'], 'progresse', 'recule')} "
                            f"de {_sans_signe(prec['var_rel_texte'])} %."})
        if var:
            loin = min(var, key=lambda d: d["exercice_ref"])
            if loin["exercice_ref"] < ex - 1:
                enonces.append({"type": "constat", "texte":
                                f"Depuis {loin['exercice_ref']}, la {_verbe(loin['var_rel_pct'], 'hausse', 'baisse', 'variation')} "
                                f"cumulée atteint {_sans_signe(loin['var_rel_texte'])} %."})
    base = [v for v in (parts or niveaux) if not est_total(v["ligne"])]
    base = sorted(base, key=lambda v: -v["valeur_num"])
    if len(base) >= 2:
        a, b = base[0], base[1]
        quoi = "parts" if parts else "valeurs"
        enonces.append({"type": "constat", "texte":
                        f"Les {quoi} les plus élevées en {ex} reviennent à « {a['ligne']} » "
                        f"({a['valeur_texte']}{_suffixe(a['unite'])}) et à « {b['ligne']} » "
                        f"({b['valeur_texte']}{_suffixe(b['unite'])})."})
    mouv = [d for d in ctx.variations if d["exercice_ref"] == ex - 1 and d["var_rel_texte"]
            and not est_total(d["ligne"]) and d["unite"] != "%" and d["ligne"] != "(sans libellé)"]
    if mouv:
        d = max(mouv, key=lambda d: abs(d["var_rel_pct"]))
        enonces.append({"type": "constat", "texte":
                        f"Par rapport à {ex - 1}, l'évolution la plus marquée concerne « {d['ligne']} » "
                        f"({_verbe(d['var_rel_pct'], 'hausse', 'baisse')} de {_sans_signe(d['var_rel_texte'])} %)."})
    if enonces:
        enonces.append({"type": "perspective", "texte":
                        "Le suivi de cet indicateur lors du prochain exercice permettra de confirmer "
                        "ou non cette orientation."})
    for e in enonces:
        e["valeurs"] = literal_check.nombres(e["texte"])
    return enonces


# ------------------------------------------------------------ service
def commenter(con, code: str, exercice: int, client: ClientLLM | None = None,
              controle: bool = True, avec_appui: bool = True, journaliser: bool = True,
              moteur=None, statuts: list[str] | None = None) -> dict:
    """Commentaire d'un indicateur. `controle=False` et `avec_appui=False` servent
    uniquement aux configurations d'évaluation (H1 ancrage, H2)."""
    t0 = time.time()
    cfg = config.charger()
    statuts = statuts or cfg["appariement"]["statuts_utilisables"]
    ctx = ic.construire(con, code, exercice, statuts, cfg["commentaire"]["nb_modeles_redaction"], moteur)
    modele = client.nom if client else MODE_EXTRACTIF
    base = {"code_indicateur": code, "exercice": exercice, "indicateur": ctx.indicateur,
            "tableau_n": ctx.tableau_n, "tableau_intitule": ctx.tableau_intitule,
            "doc_annuaire": ctx.doc_annuaire, "provisoire": ctx.provisoire,
            "statut_appariement": ctx.statut_appariement, "modele": modele,
            "moteur": decrire(client)["moteur"],
            "mode_extractif": client is None, "controle_litteral": controle, "avec_appui": avec_appui}
    motif = abst.avant_generation(ctx)
    if motif:
        return _fin(con, abst.resultat(code, exercice, motif, **base), t0, journaliser, modele)

    bruts = []
    if client is None:
        enonces = extractif(ctx)
        if not enonces:
            return _fin(con, abst.resultat(code, exercice, "tableau non exploitable par les gabarits extractifs "
                                           "(libellés ou colonnes non reconnus)", **base), t0, journaliser, modele)
    else:
        if avec_appui:
            sys_, usr = prompts.SYSTEME_COMMENTAIRE, prompts.utilisateur_commentaire(
                ctx.rendu(cfg["commentaire"]["max_valeurs_contexte"]))
        else:
            vals = ctx.rendu(cfg["commentaire"]["max_valeurs_contexte"]).split(ic.RUBRIQUE_VARIATIONS)[0]
            sys_, usr = prompts.SYSTEME_SANS_APPUI, prompts.utilisateur_sans_appui(vals)
        try:
            d, bruts = generer_llm(client, sys_, usr, cfg["llm"]["nouvelles_tentatives_json"])
        except ErreurLLM as e:
            return _fin(con, abst.resultat(code, exercice, f"modèle de langage indisponible : {e}", **base),
                        t0, journaliser, modele)
        if d is None:
            return _fin(con, abst.resultat(code, exercice, "réponse du modèle non conforme (JSON invalide "
                                           "après une nouvelle tentative)", reponses_brutes=bruts, **base),
                        t0, journaliser, modele)
        if "abstention" in d:
            return _fin(con, abst.resultat(code, exercice, f"abstention du modèle : {d['abstention']}", **base),
                        t0, journaliser, modele)
        enonces = d["enonces"]

    avant = [dict(e) for e in enonces]
    if controle:
        c = literal_check.controler(enonces, ctx.autorisees(), ctx.textes_modeles())
        gardes, ecartees, supprimes = c.enonces, c.ecartees, c.supprimes
    else:
        idx = literal_check.index_autorise(ctx.autorisees())
        gardes = [{**e, "sources": [{"valeur": o, **(literal_check.trouver(o, idx) or {"nature": "non soutenue"})}
                                    for o in literal_check.nombres(e["texte"])]} for e in enonces]
        ecartees, supprimes = [], []
    if not gardes:
        return _fin(con, abst.resultat(code, exercice, "aucun énoncé soutenu après contrôle",
                                       valeurs_ecartees=ecartees, enonces_avant_controle=avant, **base),
                    t0, journaliser, modele)
    res = {**base, "abstention": False, "enonces": provenance.tracer(con, gardes, ctx.modeles),
           "valeurs_ecartees": ecartees, "enonces_supprimes": supprimes, "enonces_avant_controle": avant,
           "modeles_de_redaction": [{k: m[k] for k in ("doc_id", "page", "exercice", "passage_id")} for m in ctx.modeles],
           "reponses_brutes": bruts}
    return _fin(con, res, t0, journaliser, modele)


def _fin(con, res: dict, t0: float, journaliser: bool, modele: str) -> dict:
    res["duree_s"] = round(time.time() - t0, 3)
    if journaliser:
        sources = [r for e in res.get("enonces", []) for r in e.get("references", [])]
        res["prod_id"] = db.journaliser(
            con, "commentaire", {"code_indicateur": res["code_indicateur"], "exercice": res["exercice"],
                                 "controle": res.get("controle_litteral"), "avec_appui": res.get("avec_appui")},
            {k: v for k, v in res.items() if k not in ("reponses_brutes",)},
            sources=[{"valeur": s["valeur"], "libelle": s["libelle"]} for s in sources],
            ecartees=res.get("valeurs_ecartees"),
            abstentions=[res["motif"]] if res.get("abstention") else [],
            modele=modele, duree_s=res["duree_s"])
    return res


def texte(res: dict) -> str:
    """Texte continu d'un commentaire (constats puis perspectives)."""
    return " ".join(e["texte"] for e in res.get("enonces", []))
