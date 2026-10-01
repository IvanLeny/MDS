"""Service 4 : note d'analyse stratégique (BN1 à BN5, sections 3.5.2 à 3.5.4).

Point de départ : les COMMENTAIRES (validés ; à défaut, produits et signalés),
jamais les tableaux bruts.
  BN1  sélection : score = |variation relative| / écart-type des variations
       passées de la même série (|var_rel| seul si moins de 3 points
       d'historique), + bonus si un objectif est documenté ; 5 à 7 évolutions ;
  BN2  mise en perspective : tendance si même signe sur 3 exercices, sinon
       variation ponctuelle ;
  BN3  rattachement à un objectif UNIQUEMENT s'il est documenté dans le corpus
       (bulletins, notes de perspective, notes de conjoncture), avec la page ;
  BN4  traçabilité : énoncé -> commentaire -> valeur -> tableau -> page ;
       variation -> ses deux valeurs sources ;
  BN5  format : Messages clés (3), Évolutions marquantes, Points d'attention,
       Pistes pour la décision (sans chiffre nouveau), Sources ; 1 à 2 pages.
Même contrôle de citation littérale que le service 2.
"""
from __future__ import annotations

import json
import re
import statistics as st
import time
from datetime import datetime

from .. import config
from ..guards import literal_check as lc
from ..guards.normalize import canon
from ..retrieval import indicator_context as ic
from ..store import db
from ..texte import jaccard
from . import analysis_note, commentary as cm, prompts

RUBRIQUES = ["Messages clés", "Évolutions marquantes", "Points d'attention", "Pistes pour la décision", "Sources"]
_OBJECTIF = re.compile(r"objectif|cible|à l[’']horizon|horizon 20\d\d|SND ?-?30|vise[rà]?\b|ambition|"
                       r"prévoi[tr]|entend|devrai[te]nt|atteindre", re.I)


# Phrases décrivant le but du document lui-même, pas un objectif de politique publique.
_BUT_DOCUMENT = re.compile(r"(ce|cette|le présent|la présente)\s+(document|note|bulletin|rapport|chapitre|enquête)|"
                           r"objectif (étant|est) d['’](analyser|présenter|examiner)|a pour objectif de présenter", re.I)


def _valeur(con, vid):
    return con.execute("SELECT * FROM valeurs WHERE valeur_id=?", (vid,)).fetchone()


def serie(con, v) -> list[tuple[int, float]]:
    """Série millésimée de la même ligne / sous-colonne dans le même tableau."""
    rows = con.execute("SELECT annee_colonne, valeur_num FROM valeurs WHERE doc_id=? AND tableau_n=? AND ligne=? "
                       "AND IFNULL(sous_colonne,'')=IFNULL(?,'') AND annee_colonne IS NOT NULL "
                       "AND valeur_num IS NOT NULL ORDER BY annee_colonne",
                       (v["doc_id"], v["tableau_n"], v["ligne"], v["sous_colonne"])).fetchall()
    return list(dict((a, x) for a, x in rows).items())


def variations_passees(s: list[tuple[int, float]], exercice: int) -> list[float]:
    """Variations relatives successives (%) de la série, jusqu'à l'exercice."""
    s = [(a, x) for a, x in s if a <= exercice]
    return [100 * (x - x0) / x0 for (a0, x0), (a, x) in zip(s, s[1:]) if x0]


def qualifier(vp: list[float], n: int) -> str:
    """BN2 : tendance si les n dernières variations ont le même signe."""
    if len(vp) >= n and (all(x > 0 for x in vp[-n:]) or all(x < 0 for x in vp[-n:])):
        sens = "hausse" if vp[-1] > 0 else "baisse"
        return f"tendance à la {sens} confirmée sur les trois derniers intervalles disponibles"
    if len(vp) < n:
        return "historique trop court pour qualifier une tendance"
    return "variation ponctuelle (pas de tendance de même sens sur trois intervalles)"


def objectif_documente(moteur, intitule: str, exercice: int, seuil: float) -> dict | None:
    """BN3 : passage du corpus énonçant un objectif lié à l'indicateur, ou None."""
    if moteur is None:
        return None
    aut = moteur.autorises("publie", exercice_max=exercice, types=("contexte", "note_conjoncture"),
                           exclure_tests=True)
    for r in moteur.rechercher(intitule, aut, mode="hybride", k=8):
        p = db.passage(moteur.con, r.passage_id)
        for ph in re.split(r"(?<=[.;!?])\s+", p["texte"]):
            if (_OBJECTIF.search(ph) and not _BUT_DOCUMENT.search(ph)
                    and jaccard(ph, intitule) >= seuil and 40 <= len(ph) <= 400):
                return {"texte": ph.strip(), "doc_id": p["doc_id"], "titre": p["titre"], "page": p["page"],
                        "passage_id": p["passage_id"]}
    return None


def rediger(con, exercice: int, client=None, moteur=None, journaliser: bool = True) -> dict:
    t0 = time.time()
    cfg = config.charger()
    ns = cfg["note_strategique"]
    statuts = cfg["appariement"]["statuts_utilisables"]
    codes = [r[0] for r in con.execute(
        f"SELECT code_indicateur FROM appariement WHERE exercice=? AND tableau_n IS NOT NULL "
        f"AND statut IN ({','.join('?' * len(statuts))}) ORDER BY graphique_n", (exercice, *statuts))]
    candidats, non_valides, abstentions, commentaires = [], [], [], []
    for code in codes:
        com = analysis_note.commentaire_valide(con, code, exercice)
        if com is None:
            com = cm.commenter(con, code, exercice, client, journaliser=journaliser, moteur=moteur)
            com["valide"] = False
        if com.get("abstention"):
            abstentions.append({"code": code, "motif": com.get("motif")})
            continue
        if not com["valide"]:
            non_valides.append(code)
        commentaires.append((code, com))
        # évolutions CITÉES dans le commentaire (variation relative par rapport à l'exercice précédent de préférence)
        cites = []
        for e in com["enonces"]:
            for s in e.get("sources", []):
                if s.get("nature") == "variation" and s.get("grandeur") == "var_rel_pct":
                    cites.append((e, s))
        if not cites:
            continue
        # Évolution représentative de l'indicateur : celle de son TOTAL (ou de sa grandeur principale)
        # par rapport à l'exercice précédent, à défaut la plus forte évolution citée.
        niveau_ = [(e, s) for e, s in cites if _EVOL_PH.search(e["texte"])]
        e, s = min(niveau_ or cites,
                   key=lambda es: (es[1]["exercice_ref"] != exercice - 1, -abs(float(canon(es[1]["valeur"])))))
        mouvement = next((x["texte"] for x in com["enonces"] if _MOUV.search(x["texte"])), None)
        v, vref = _valeur(con, s["valeur_id"]), _valeur(con, s["valeur_ref_id"])
        signe = 1 if v["valeur_num"] >= vref["valeur_num"] else -1
        var_rel = signe * float(canon(s["valeur"]))
        vp = variations_passees(serie(con, v), exercice)
        hist = vp[:-1] if vp and abs(vp[-1] - var_rel) < 0.06 else vp
        if len(hist) >= ns["historique_min"] and st.pstdev(hist) > 0:
            score, base = abs(var_rel) / st.pstdev(hist), "|var| / écart-type des variations passées"
        else:
            score, base = abs(var_rel), "|var_rel| (historique < 3 points)"
        obj = objectif_documente(moteur, com.get("indicateur") or com.get("tableau_intitule", ""), exercice,
                                 ns["seuil_objectif"])
        if obj:
            score += ns["bonus_objectif"]
        candidats.append({"code": code, "commentaire": com, "enonce": e, "source": s, "var_rel": var_rel,
                          "mouvement": mouvement,
                          "score": round(score, 4), "base_score": base, "n_historique": len(hist),
                          "qualification": qualifier(vp, ns["tendance_meme_signe"]), "objectif": obj,
                          "valeur": dict(v), "valeur_ref": dict(vref)})
    candidats.sort(key=lambda c: -c["score"])
    # une même évolution (mêmes valeurs sources) n'est retenue qu'une fois
    # une même évolution n'est retenue qu'une fois : mêmes valeurs sources, ou même grandeur
    # avec la même variation (le total du stock de PME figure dans plusieurs tableaux)
    vus, uniques = set(), []
    for c in candidats:
        k1 = (c["source"]["valeur_id"], c["source"]["valeur_ref_id"])
        k2 = (nom_court(c["commentaire"]), c["source"]["valeur"], c["source"]["exercice_ref"])
        if k1 not in vus and k2 not in vus:
            vus.update({k1, k2})
            uniques.append(c)
    # une seule évolution par grandeur : celle de l'indicateur de référence (même que l'encadré)
    ref = {nom: code for nom, (code, _) in references_grandeurs(commentaires).items()}
    par_grandeur: dict[str, dict] = {}
    for c in uniques:
        nom = nom_court(c["commentaire"])
        if nom not in par_grandeur or (c["code"] == ref.get(nom) and par_grandeur[nom]["code"] != ref.get(nom)):
            par_grandeur[nom] = c
    uniques = [c for c in uniques if par_grandeur.get(nom_court(c["commentaire"])) is c]
    retenus = uniques[:ns["nb_max"]]
    note = _assembler(con, exercice, retenus, candidats, non_valides, abstentions, client, ns, commentaires)
    note["duree_s"] = round(time.time() - t0, 3)
    if journaliser:
        note["prod_id"] = db.journaliser(
            con, "note_strategique", {"exercice": exercice},
            {k: v for k, v in note.items() if k not in ("tracabilite",)},
            sources=note["tracabilite"], ecartees=note["valeurs_ecartees"], abstentions=abstentions,
            modele=note["modele"], duree_s=note["duree_s"])
    return note


def _nom(c) -> str:
    return c["commentaire"].get("indicateur") or c["commentaire"].get("tableau_intitule") or c["code"]


def nom_court(com: dict) -> str:
    """Nom lisible de la grandeur suivie par un indicateur (« le stock de PME »…)."""
    t = f"{com.get('indicateur') or ''} {com.get('tableau_intitule') or ''}"
    if re.search(r"\bVA\b|valeurs? ajout", t, re.I):
        return "la valeur ajoutée des PME"
    if re.search(r"\bUPA\b", t):
        return "les UPA enregistrées"
    if re.search(r"\bOES\b", t):
        return "les OES enregistrées"
    if re.search(r"cr[ée]{2}e?s|cr[ée]ation", t, re.I) and re.search(r"CFCE", t):
        return "les créations de PME dans les CFCE"
    if re.search(r"stock", t, re.I) and re.search(r"\bPME\b", t):
        return "le stock de PME"
    if re.search(r"stock", t, re.I):
        return "le stock d'entreprises"
    return f"« {com.get('indicateur') or com.get('tableau_intitule')} »"


def de(nom: str) -> str:
    """« de » + nom, avec contraction : du stock, des UPA, de la valeur ajoutée."""
    for a, b in (("le ", "du "), ("les ", "des ")):
        if nom.startswith(a):
            return b + nom[len(a):]
    return "de " + nom


_MOUV = re.compile(r"(?:dans la répartition par (?P<dim>[^,]+), )?l'évolution la plus marquée concerne « (?P<lab>.+?) » "
                   r"\((?P<sens>hausse|baisse) de (?P<val>[\d  ,.]+) % (?P<nat>[^)]+)\)")
_TOTAL_PH = re.compile(r"(?:le total|« .+? ») s'établit à (?P<val>[\d  ,.]+)(?P<u>[^.]*)\.")
_EVOL_PH = re.compile(r"Par rapport à (?P<ref>\d{4}), (?:ce total|« .+? ») (?P<verbe>progresse|recule) de (?P<val>[\d  ,.]+) %")


def niveau(com: dict) -> dict | None:
    """Niveau et évolution de l'indicateur, lus dans SON commentaire (valeurs déjà contrôlées)."""
    tot = evo = None
    for e in com.get("enonces", []):
        tot = tot or _TOTAL_PH.search(e["texte"])
        evo = evo or _EVOL_PH.search(e["texte"])
    if not tot:
        return None
    u = tot.group("u").strip()
    return {"nom": nom_court(com), "valeur": tot.group("val").strip(), "unite": u,
            "evolution": evo.group("val").strip() if evo else None,
            "sens": ("hausse" if evo.group("verbe") == "progresse" else "baisse") if evo else None,
            "ref": evo.group("ref") if evo else None}


def references_grandeurs(commentaires: list[tuple[str, dict]]) -> dict[str, tuple[str, dict]]:
    """Pour chaque grandeur, l'indicateur de référence : le premier (ordre de l'Annuaire) qui donne
    son niveau, de préférence avec une évolution. Partagé par l'encadré et la sélection."""
    par_nom: dict[str, tuple[str, dict]] = {}
    for code, com in commentaires:
        nv = niveau(com)
        if nv and (nv["nom"] not in par_nom or (nv["evolution"] and not par_nom[nv["nom"]][1]["evolution"])):
            par_nom[nv["nom"]] = (code, nv)
    return par_nom


def chiffres_cles(commentaires: list[tuple[str, dict]], n: int = 6) -> list[dict]:
    """Encadré « chiffres clés » (B3) : niveau et évolution des grandeurs principales,
    une ligne par grandeur (de préférence celle qui porte une évolution), dans l'ordre des indicateurs."""
    par_nom: dict[str, tuple[str, dict]] = {}
    for code, com in commentaires:
        nv = niveau(com)
        if nv and (nv["nom"] not in par_nom or (nv["evolution"] and not par_nom[nv["nom"]][1]["evolution"])):
            par_nom[nv["nom"]] = (code, nv)
    out = []
    for code, nv in par_nom.values():
        t = f"{nv['nom'][:1].upper()}{nv['nom'][1:]} : {nv['valeur']}{(' ' + nv['unite']) if nv['unite'] else ''}"
        if nv["evolution"]:
            t += f" ({'+' if nv['sens'] == 'hausse' else '−'}{nv['evolution']} % par rapport à {nv['ref']})"
        out.append({"texte": t + ".", "code": code})
    return out[:n]


def _messages_cles(retenus: list[dict], commentaires: list[tuple[str, dict]], ex: int) -> list[dict]:
    """B1 : trois messages de structures différentes — fait principal, dynamique la plus forte,
    point de vigilance —, chacun avec au moins un chiffre déjà contrôlé dans un commentaire."""
    msgs = []
    # (1) fait principal : la grandeur de tête (stock de PME de préférence)
    tetes = [(code, com, niveau(com)) for code, com in commentaires]
    tetes = [x for x in tetes if x[2] and x[2]["evolution"]]
    tetes.sort(key=lambda x: (x[2]["nom"] != "le stock de PME", x[2]["nom"] != "la valeur ajoutée des PME"))
    if tetes:
        code, com, nv = tetes[0]
        u = f" {nv['unite']}" if nv["unite"] else ""
        msgs.append({"texte": f"En {ex}, {nv['nom']} atteint {nv['valeur']}{u}, en {nv['sens']} de "
                              f"{nv['evolution']} % par rapport à {nv['ref']}.", "code": code})
    # (2) dynamique la plus forte et (3) point de vigilance, à partir des évolutions retenues (BN1)
    mouvs = []
    for c in retenus:
        m = _MOUV.search(c.get("mouvement") or "") or _MOUV.search(c["enonce"]["texte"])
        if m:
            mouvs.append((c, m))
    ampleur = lambda x: float(canon(x[1].group("val")))
    rang = lambda x: ("/" in x[1].group("lab"), -ampleur(x))           # lignes simples d'abord
    hausses = sorted([x for x in mouvs if x[1].group("sens") == "hausse"], key=rang)
    baisses = sorted([x for x in mouvs if x[1].group("sens") == "baisse"], key=rang)
    pris = {m["code"] for m in msgs}
    if hausses:
        c, m = hausses[0]
        dim = f" (répartition par {m.group('dim')})" if m.group("dim") else ""
        msgs.append({"texte": f"La dynamique la plus forte concerne « {m.group('lab')} »{dim} pour {nom_court(c['commentaire'])} : "
                              f"+{m.group('val')} % {m.group('nat')} en un an.", "code": c["code"]})
    if baisses:
        c, m = baisses[0]
        dim = f" (répartition par {m.group('dim')})" if m.group("dim") else ""
        msgs.append({"texte": f"Point de vigilance : {nom_court(c['commentaire'])} reculent pour « {m.group('lab')} »{dim}, "
                              f"avec une baisse de {m.group('val')} % {m.group('nat')} par rapport à {ex - 1}."
                     if nom_court(c['commentaire']).startswith("les ") else
                     f"Point de vigilance : {nom_court(c['commentaire'])} recule pour « {m.group('lab')} »{dim}, "
                     f"avec une baisse de {m.group('val')} % {m.group('nat')} par rapport à {ex - 1}.",
                     "code": c["code"]})
    elif len(hausses) > 1:
        c, m = hausses[-1]
        msgs.append({"texte": f"Aucune des évolutions retenues n'est en recul ; la progression la plus modérée "
                              f"concerne « {m.group('lab')} » pour {nom_court(c['commentaire'])} (+{m.group('val')} %).",
                     "code": c["code"]})
    # compléter si besoin avec les constats retenus restants (jamais deux fois le même)
    for c in retenus:
        if len(msgs) >= 3:
            break
        if c["enonce"]["texte"] not in {m["texte"] for m in msgs} and c["code"] not in pris:
            msgs.append({"texte": f"{nom_court(c['commentaire'])[:1].upper()}{nom_court(c['commentaire'])[1:]} : "
                                  f"{c['enonce']['texte'][:1].lower()}{c['enonce']['texte'][1:]}", "code": c["code"]})
    return msgs[:3]


_TERRITOIRE = re.compile(r"r[ée]gion|ville|CFCE|commune|d[ée]partement", re.I)


def _piste(c: dict) -> tuple[str, str]:
    """B2 : piste typée, sans chiffre (règle BN), rattachée à l'évolution et à l'objectif documenté."""
    nom = nom_court(c["commentaire"])
    m = _MOUV.search(c.get("mouvement") or "") or _MOUV.search(c["enonce"]["texte"])
    lab = f"« {m.group('lab')} »" if m else None
    tend = c["qualification"].startswith("tendance")
    if c["var_rel"] < 0:
        cible = f", en particulier pour {lab}," if lab and m.group("sens") == "baisse" else ""
        return "corriger", (f"Corriger : analyser les causes du recul observé pour {nom}{cible} et définir des mesures "
                            f"d'accompagnement ciblées.")
    if c["objectif"]:
        return "consolider", (f"Consolider : maintenir les actions favorables à la progression observée pour {nom}, "
                              f"en cohérence avec l'objectif cité dans le corpus.")
    if lab and (_TERRITOIRE.search(_nom(c)) or _TERRITOIRE.search(c["commentaire"].get("tableau_intitule") or "")):
        return "cibler", (f"Cibler : examiner la situation de {lab} pour {nom}, afin d'identifier les facteurs "
                          f"locaux de la dynamique observée.")
    if tend:
        return "approfondir", (f"Approfondir : documenter les facteurs de la hausse durable observée pour {nom}, "
                               f"afin d'en tirer des enseignements pour l'action publique.")
    return "suivre", (f"Suivre : fixer un objectif de référence pour {nom} afin d'apprécier les prochaines évolutions.")


def _gabarits(blocs: dict, retenus: list[dict], commentaires: list[tuple[str, dict]] | None = None,
              ex: int | None = None) -> None:
    """Rédaction par gabarits déterministes (mode sans modèle de langage, ou repli)."""
    ex = ex or (retenus[0]["commentaire"]["exercice"] if retenus else 0)
    blocs["Messages clés"] = _messages_cles(retenus, commentaires or [(c["code"], c["commentaire"]) for c in retenus], ex)
    for c in retenus:
        nc = nom_court(c["commentaire"])
        t = f"{nc[:1].upper()}{nc[1:]} — {c['enonce']['texte']}"
        if c.get("mouvement") and c["mouvement"] != c["enonce"]["texte"]:
            t += f" {c['mouvement']}"
        t += f" {c['qualification'][:1].upper()}{c['qualification'][1:]}."
        if c["objectif"]:
            o = c["objectif"]
            t += f" Objectif documenté : « {o['texte']} » ({o['titre']}, p. {o['page']})."
        else:
            t += " Aucun objectif documenté dans le corpus."
        blocs["Évolutions marquantes"].append({"texte": t, "code": c["code"]})
    for c in retenus:
        m = _MOUV.search(c.get("mouvement") or "")
        nc = nom_court(c["commentaire"])
        if c["var_rel"] < 0:
            blocs["Points d'attention"].append({"texte": f"Recul {de(nc)} : {c['enonce']['texte'][:1].lower()}"
                                                        f"{c['enonce']['texte'][1:]}", "code": c["code"]})
        elif m and m.group("sens") == "baisse":
            blocs["Points d'attention"].append({"texte": f"Malgré la progression d'ensemble {de(nc)}, recul pour "
                                                        f"« {m.group('lab')} » ({m.group('val')} % {m.group('nat')}).",
                                                "code": c["code"]})
    groupes: dict[tuple, list[dict]] = {}
    for c in retenus:
        groupes.setdefault((_piste(c)[0], nom_court(c["commentaire"])), []).append(c)
    for (typ, nom), cs in groupes.items():
        if len(cs) > 1 and typ == "corriger":
            labs = [m.group("lab") for m in (_MOUV.search(c.get("mouvement") or "") for c in cs) if m]
            cible = (", en particulier pour " + " et ".join(f"« {l} »" for l in labs) + ",") if labs else ""
            p = (f"Corriger : analyser les causes du recul observé pour {nom}{cible} et définir des mesures "
                 f"d'accompagnement ciblées.")
        else:
            p = _piste(cs[0])[1]
        blocs["Pistes pour la décision"].append({"texte": p, "code": cs[0]["code"]})


def _rediger_llm(client, retenus: list[dict], ex: int) -> dict | None:
    """Le modèle rédige messages clés, mise en perspective, points d'attention et pistes,
    à partir des SEULS éléments fournis par le programme. None si la réponse est inexploitable
    (repli sur les gabarits, signalé)."""
    elements = [{"code": c["code"], "indicateur": _nom(c), "constat_valide": c["enonce"]["texte"],
                 "sens": "hausse" if c["var_rel"] > 0 else "baisse" if c["var_rel"] < 0 else "stable",
                 "qualification_programme": c["qualification"],
                 "objectif_documente": c["objectif"]["texte"] if c["objectif"] else None} for c in retenus]
    try:
        brut = client.generer(prompts.SYSTEME_NOTE_STRATEGIQUE, prompts.utilisateur_note_strategique(ex, elements))
        d = json.loads(re.sub(r"^```(?:json)?|```$", "", brut.strip(), flags=re.M))
    except Exception:
        return None
    if not isinstance(d, dict) or not isinstance(d.get("messages_cles"), list) or len(d["messages_cles"]) < 3:
        return None
    for cle in ("points_attention", "pistes"):
        if not isinstance(d.get(cle, []), list):
            return None
    d["messages_cles"] = [str(x) for x in d["messages_cles"] if str(x).strip()]
    d["points_attention"] = [str(x) for x in d.get("points_attention", []) if str(x).strip()]
    d["pistes"] = [str(x) for x in d.get("pistes", []) if str(x).strip()]
    d["evolutions"] = [e for e in d.get("evolutions", []) if isinstance(e, dict)]
    return d


def _assembler(con, exercice, retenus, candidats, non_valides, abstentions, client, ns,
               commentaires: list | None = None) -> dict:
    ex = exercice
    blocs: dict[str, list[dict]] = {r: [] for r in RUBRIQUES}
    redaction = _rediger_llm(client, retenus, ex) if client is not None else None
    if redaction:
        # Le modèle rédige ; le programme a sélectionné (BN1), qualifié (BN2) et apporté les objectifs (BN3).
        blocs["Messages clés"] = [{"texte": t, "code": None} for t in redaction["messages_cles"][:3]]
        persp = {e.get("code"): e.get("mise_en_perspective", "") for e in redaction.get("evolutions", [])}
        for c in retenus:
            t = f"{_nom(c)} : {c['enonce']['texte']} {persp.get(c['code'], '')}".strip()
            t += (f" Objectif documenté : « {c['objectif']['texte']} » ({c['objectif']['titre']}, "
                  f"p. {c['objectif']['page']})." if c["objectif"] else " Aucun objectif documenté dans le corpus.")
            blocs["Évolutions marquantes"].append({"texte": t, "code": c["code"]})
        blocs["Points d'attention"] = [{"texte": t, "code": None} for t in redaction.get("points_attention", [])]
        blocs["Pistes pour la décision"] = [{"texte": t, "code": None} for t in redaction.get("pistes", [])]
    else:
        _gabarits(blocs, retenus, commentaires, ex)
    if non_valides:
        blocs["Points d'attention"].append({"texte": f"{len(non_valides)} commentaire(s) mobilisé(s) n'ont pas encore "
                                                     "été validés par la Cellule : la note est à relire.", "code": None})
    if len(retenus) < ns["nb_min"]:
        noms = ", ".join(nom_court(c["commentaire"]) for c in retenus)
        blocs["Points d'attention"].append({"texte": f"Seules {len(retenus)} grandeurs disposent d'une évolution "
                                                     f"calculable pour cet exercice ({noms}) : la note en retient moins "
                                                     f"que le minimum prévu plutôt que d'y faire figurer des évolutions "
                                                     f"non comparables.", "code": None})
    if abstentions:
        blocs["Points d'attention"].append({"texte": "Certains indicateurs n'ont pas pu être commentés faute de "
                                                     "sources suffisantes ; ils sont à commenter manuellement.",
                                            "code": None})
    # Sources (BN4)
    trace = []
    for c in retenus:
        com = c["commentaire"]
        for s_ in [c["valeur"], c["valeur_ref"]]:
            trace.append({"enonce": c["enonce"]["texte"], "code_indicateur": c["code"],
                          "commentaire_prod_id": com.get("prod_id"), "commentaire_valide": com.get("valide"),
                          "variation": c["source"]["valeur"], "valeur": s_["valeur_texte"],
                          "valeur_id": s_["valeur_id"], "ligne": s_["ligne"], "colonne": s_["colonne"],
                          "document": s_["doc_id"], "tableau": s_["tableau_n"], "page": s_["page"]})
        for r in (r for e in com.get("enonces", []) if e["texte"] == c["enonce"]["texte"]
                  for r in e.get("references", []) if r.get("nature") == "valeur"):
            for vs in r.get("valeurs_sources") or []:
                if vs:
                    trace.append({"enonce": c["enonce"]["texte"], "code_indicateur": c["code"],
                                  "commentaire_prod_id": com.get("prod_id"), "commentaire_valide": com.get("valide"),
                                  "variation": "", "valeur": vs["valeur_texte"], "valeur_id": vs["valeur_id"],
                                  "ligne": vs["ligne"], "colonne": vs["colonne"], "document": vs["doc_id"],
                                  "tableau": vs["tableau_n"], "page": vs["page"]})
    docs = sorted({(t["document"], t["tableau"], t["page"]) for t in trace}, key=lambda x: (x[0], x[1] or 0))
    blocs["Sources"] = [{"texte": f"{d}, tableau {t}, p. {p}", "code": None} for d, t, p in docs]
    objs = sorted({(c["objectif"]["titre"], c["objectif"]["page"]) for c in retenus if c["objectif"]})
    blocs["Sources"] += [{"texte": f"{t}, p. {p} (objectif documenté)", "code": None} for t, p in objs]
    blocs["Sources"] += [{"texte": f"Commentaire n° {c['commentaire'].get('prod_id')} ({c['code']})"
                                  + ("" if c["commentaire"].get("valide") else " — non validé"), "code": None}
                         for c in retenus]

    # Même contrôle littéral que le service 2 (valeurs des indicateurs retenus + objectifs cités)
    autorisees = []
    statuts = config.charger()["appariement"]["statuts_utilisables"]
    codes_cites = list(dict.fromkeys([c["code"] for c in retenus] + [code for code, _ in (commentaires or [])]))
    for code in codes_cites:
        autorisees += ic.construire(con, code, ex, statuts).autorisees()
    for c in retenus:
        if c["objectif"]:
            autorisees += [{"texte": n, "source": {"nature": "objectif documenté", "doc_id": c["objectif"]["doc_id"],
                                                  "page": c["objectif"]["page"]}}
                           for n in lc.nombres(c["objectif"]["texte"])]
    ecartees = []
    for r in RUBRIQUES[:-1]:
        en = [{"type": r, "texte": b["texte"], "code": b["code"]} for b in blocs[r]]
        if r == "Pistes pour la décision":
            ctrl = lc.controler(en, [], [])                     # aucun chiffre admis dans les pistes
        else:
            ctrl = lc.controler(en, autorisees, [])
        blocs[r] = ctrl.enonces
        ecartees += ctrl.ecartees
    ck = lc.controler([{"type": "chiffres clés", **b} for b in chiffres_cles(commentaires or [])], autorisees, [])
    ecartees += ck.ecartees
    n_mots = sum(len(b["texte"].split()) for r in RUBRIQUES for b in blocs[r])
    return {
        "type": "note_strategique", "exercice": ex, "titre": f"Note d'analyse stratégique — exercice {ex}",
        "date": datetime.now().strftime("%d/%m/%Y"), "rubriques": blocs, "chiffres_cles": ck.enonces,
        "selection": [{"code": c["code"], "indicateur": _nom(c), "score": c["score"], "base_score": c["base_score"],
                       "variation_relative": c["var_rel"], "n_historique": c["n_historique"],
                       "qualification": c["qualification"], "objectif": c["objectif"]} for c in retenus],
        "candidats_ecartes_de_la_selection": [{"code": c["code"], "score": c["score"]} for c in candidats[len(retenus):]],
        "nb_evolutions": len(retenus), "sous_le_minimum": len(retenus) < ns["nb_min"],
        "tracabilite": trace, "valeurs_ecartees": ecartees, "abstentions": abstentions,
        "commentaires_non_valides": non_valides, "nb_mots": n_mots, "max_mots": ns["max_mots"],
        "mode_extractif": client is None, "modele": client.nom if client else cm.MODE_EXTRACTIF,
        "moteur": client.moteur if client else "none",
        "redaction": "modèle de langage" if redaction else ("gabarits" if client is None else
                                                           "gabarits (repli : réponse du modèle inexploitable)"),
        "provisoire": any(c["commentaire"].get("provisoire") for c in retenus),
    }


def verifier_bn4_bn5(note: dict) -> dict:
    """Vérification automatique de ce qui est vérifiable : BN4 (toute valeur est
    tracée) et BN5 (rubriques présentes, longueur <= 2 pages)."""
    non_tracees = [s for r in RUBRIQUES[:-1] for e in note["rubriques"][r]
                   for s in lc.nombres(e["texte"]) if s not in {x["valeur"] for x in e.get("sources", [])}]
    return {"BN4_toute_valeur_tracee": not non_tracees and bool(note["tracabilite"]),
            "BN4_valeurs_non_tracees": non_tracees,
            "BN5_rubriques": all(note["rubriques"].get(r) for r in RUBRIQUES[:2] + RUBRIQUES[3:]),
            "BN5_messages_cles_3": len(note["rubriques"]["Messages clés"]) == 3,
            "BN5_longueur_ok": note["nb_mots"] <= note["max_mots"], "nb_mots": note["nb_mots"]}
