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


def _val(v: dict) -> str:
    """Valeur telle qu'écrite dans l'Annuaire, suivie de son unité (sans doubler le signe %)."""
    t = v["valeur_texte"].strip()
    if v["unite"] == "%" or t.endswith("%"):
        return t.rstrip("% ").strip() + " %"
    return t + _suffixe(v["unite"])


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


# Grandeur mesurée par une ligne ou un indicateur (A2) : sert à ne pas commenter
# le « Stock des PME » sous un indicateur de valeur ajoutée.
_GRANDEURS = [("va", r"\bva\b|valeurs? ajout"), ("stock", r"\bstock"),
              ("ca", r"chiffres? d.affaires"), ("emplois", r"\bemplois?\b")]


def _grandeur(t: str) -> str | None:
    for nom, motif in _GRANDEURS:
        if re.search(motif, t or "", re.I):
            return nom
    return None


def _dimension(t: str) -> str | None:
    """« … par sexe », « … selon le secteur d’activité (en %) » -> « sexe », « secteur d’activité »."""
    m = re.search(r"\b(?:par|selon)\s+(?:la |le |les |l['’])?(.+?)(?:\s+(?:de|en|entre|au|du)\s+\d{4}|\s*\(|\s*$)",
                  t or "", re.I)
    if not m:
        return None
    d = re.split(r"\s+(?:de|en|entre)\s+\d{4}", m.group(1))[0].strip(" .,")
    return d or None


def _sans_renvoi(ligne: str) -> str:
    return re.sub(r"\(\*+\)|\*+", "", ligne).strip()


def _est_total(ligne: str) -> bool:
    return bool(re.search(r"(^|/\s*)total", _sans_renvoi(ligne), re.I))


def _total_general(ligne: str) -> bool:
    return bool(re.fullmatch(r"\s*total(\s+(g[ée]n[ée]ral|pme|national|ensemble))?(\s*/\s*total)?\s*",
                             _sans_renvoi(ligne), re.I))


_NOMS_GRANDEUR = {"va": "de la valeur ajoutée", "stock": "du stock", "ca": "du chiffre d'affaires",
                  "emplois": "des emplois"}


def _nature(u: str | None, sujet: str | None = None) -> str:
    if sujet in _NOMS_GRANDEUR:
        return _NOMS_GRANDEUR[sujet]
    return "du montant" if u and u != "%" else "de l'effectif"


def extractif(ctx: ic.Contexte) -> list[dict]:
    """Gabarits déterministes à partir des seules valeurs et variations du contexte.

    A2 : la ligne principale est le total, ou à défaut la ligne qui mesure la grandeur
    annoncée par l'intitulé (VA, stock…) ; les lignes d'une autre grandeur sont écartées.
    A3 : la nature de l'évolution est précisée (effectif, montant) ; une évolution de part
    s'exprime en points de pourcentage. A4 : la dimension (sexe, secteur…) est nommée.
    """
    ex = ctx.exercice
    vals = [v for v in ctx.valeurs if v["valeur_num"] is not None and v["ligne"] != "(sans libellé)"]
    courant = [v for v in vals if v["annee_colonne"] == ex] or [v for v in vals if v["annee_colonne"] is None]
    if not courant:
        return []
    tit = ctx.tableau_intitule or ctx.indicateur
    sujet = _grandeur(ctx.indicateur) or _grandeur(tit)
    dim = _dimension(tit) or _dimension(ctx.indicateur)
    autre_grandeur = lambda l: bool(sujet and _grandeur(l) and _grandeur(l) != sujet)
    niveaux = _une_colonne([v for v in courant if v["unite"] != "%" and "%" not in (v["sous_colonne"] or "")])
    parts = _une_colonne([v for v in courant if v["unite"] == "%" or "%" in (v["sous_colonne"] or "")])
    niveaux = [v for v in niveaux if not autre_grandeur(v["ligne"])]
    parts = [v for v in parts if not autre_grandeur(v["ligne"])]
    enonces = []
    tot = next((v for v in niveaux if _total_general(v["ligne"])), None)
    principal = None
    if tot is None and sujet:
        cand = [v for v in niveaux if _grandeur(v["ligne"]) == sujet]
        principal = cand[0] if len(cand) == 1 else None
    if tot:
        enonces.append({"type": "constat", "texte": f"En {ex}, pour « {tit} », le total s'établit à "
                        f"{_val(tot)}."})
        sujet_phrase = "ce total"
    elif principal:
        tot = principal
        enonces.append({"type": "constat", "texte": f"En {ex}, « {tot['ligne']} » s'établit à "
                        f"{_val(tot)}."})
        sujet_phrase = f"« {tot['ligne']} »"
    if tot:
        var = [d for d in ctx.variations if d["valeur_id"] == tot["valeur_id"] and d["var_rel_texte"]]
        prec = next((d for d in var if d["exercice_ref"] == ex - 1), None)
        if prec:
            enonces.append({"type": "constat", "texte":
                            f"Par rapport à {ex - 1}, {sujet_phrase} {_verbe(prec['var_rel_pct'], 'progresse', 'recule')} "
                            f"de {_sans_signe(prec['var_rel_texte'])} %."})
        if var:
            loin = min(var, key=lambda d: d["exercice_ref"])
            if loin["exercice_ref"] < ex - 1:
                enonces.append({"type": "constat", "texte":
                                f"Depuis {loin['exercice_ref']}, la {_verbe(loin['var_rel_pct'], 'hausse', 'baisse', 'variation')} "
                                f"cumulée atteint {_sans_signe(loin['var_rel_texte'])} %."})
    exclus = {tot["ligne"]} if tot else set()
    base = [v for v in (parts or niveaux) if not _est_total(v["ligne"]) and v["ligne"] not in exclus]
    base = sorted(base, key=lambda v: -v["valeur_num"])
    dans = f"dans la répartition par {dim}, " if dim else ""
    if len(base) >= 2:
        a, b = base[0], base[1]
        quoi = "parts" if parts else "valeurs"
        enonces.append({"type": "constat", "texte":
                        f"{dans[:1].upper() + dans[1:] if dans else ''}Les {quoi} les plus élevées en {ex} reviennent "
                        f"à « {a['ligne']} » ({_val(a)}) et à « {b['ligne']} » "
                        f"({_val(b)})." if not dans else
                        f"{dans[:1].upper() + dans[1:]}les {quoi} les plus élevées en {ex} reviennent "
                        f"à « {a['ligne']} » ({_val(a)}) et à « {b['ligne']} » "
                        f"({_val(b)})."})
    ok = lambda d: (d["exercice_ref"] == ex - 1 and not _est_total(d["ligne"]) and d["ligne"] not in exclus
                    and d["ligne"] != "(sans libellé)" and not autre_grandeur(d["ligne"]))
    cc = config.charger()["commentaire"]
    plancher = max(cc.get("effectif_min_evolution", 0),
                   cc.get("part_min_evolution", 0) * (tot["valeur_num"] if tot else 0))
    mouv = [d for d in ctx.variations if ok(d) and d["var_rel_texte"] and d["unite"] != "%"
            and abs(d["valeur_ref"] or 0) >= plancher]
    simples = [d for d in mouv if "/" not in d["ligne"]]      # lignes simples avant les croisements
    mouv = simples or mouv
    if mouv:
        d = max(mouv, key=lambda d: abs(d["var_rel_pct"]))
        enonces.append({"type": "constat", "texte":
                        f"Par rapport à {ex - 1}, {dans}l'évolution la plus marquée concerne « {d['ligne']} » "
                        f"({_verbe(d['var_rel_pct'], 'hausse', 'baisse')} de {_sans_signe(d['var_rel_texte'])} % "
                        f"{_nature(d['unite'], sujet)})."})
    else:
        mouv_parts = [d for d in ctx.variations if ok(d) and d["unite"] == "%" and d["var_abs"]]
        if mouv_parts:
            d = max(mouv_parts, key=lambda d: abs(d["var_abs"]))
            enonces.append({"type": "constat", "texte":
                            f"Par rapport à {ex - 1}, {dans}la part de « {d['ligne']} » "
                            f"{_verbe(d['var_abs'], 'gagne', 'perd')} {_sans_signe(d['var_abs_texte'])} point(s) "
                            f"de pourcentage."})
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
              moteur=None, statuts: list[str] | None = None, repli: bool | None = None) -> dict:
    """Commentaire d'un indicateur. `controle=False` et `avec_appui=False` servent
    uniquement aux configurations d'évaluation (H1 ancrage, H2).

    `repli` (par défaut : config `commentaire.repli_gabarits`) : si la réponse du modèle est
    inexploitable (JSON invalide, abstention du modèle, trop peu d'énoncés soutenus après
    contrôle), le commentaire est rédigé par les gabarits, et ce repli est signalé. Les
    évaluations du modèle (H1, H2, Tableau 3.2) passent `repli=False` pour mesurer le modèle seul."""
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
        ccom = cfg["commentaire"]
        repli = ccom.get("repli_gabarits", True) if repli is None else repli

        def _repli(motif: str, **extra) -> dict:
            if repli:
                r = commenter(con, code, exercice, None, controle, avec_appui, False, moteur, statuts)
                if not r.get("abstention"):
                    r.update({"modele": modele, "moteur": base["moteur"], "mode_extractif": False,
                              "repli_gabarits": motif, "reponses_brutes": bruts, "repli_details": extra})
                    return _fin(con, r, t0, journaliser, modele)
            return _fin(con, abst.resultat(code, exercice, motif, reponses_brutes=bruts, **extra, **base),
                        t0, journaliser, modele)

        try:
            d, bruts = generer_llm(client, sys_, usr, cfg["llm"]["nouvelles_tentatives_json"])
        except ErreurLLM as e:
            return _repli(f"modèle de langage indisponible : {e}")
        if d is None:
            return _repli("réponse du modèle non conforme (JSON invalide après une nouvelle tentative)")
        if "abstention" in d:
            return _repli(f"abstention du modèle : {d['abstention']}")
        enonces = d["enonces"]

    avant = [dict(e) for e in enonces]
    if controle:
        c = literal_check.controler(enonces, ctx.autorisees(), ctx.textes_modeles())
        gardes, ecartees, supprimes = c.enonces, c.ecartees, c.supprimes
    else:
        idx = literal_check.index_autorise(ctx.autorisees())
        gardes = [{**e, "sources": [{"valeur": o.texte, **(literal_check.trouver(o.texte, idx, e["texte"], o.debut)
                                                           or {"nature": "non soutenue"})}
                                    for o in literal_check.occurrences(e["texte"])]} for e in enonces]
        ecartees, supprimes = [], []
    if client is not None and controle and repli:
        n_min = cfg["commentaire"].get("repli_min_constats", 1)
        if sum(e.get("type") == "constat" for e in gardes) < n_min:
            return _repli("aucun énoncé soutenu après contrôle" if not gardes else
                          f"moins de {n_min} constats soutenus après contrôle",
                          valeurs_ecartees=ecartees, enonces_avant_controle=avant)
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
