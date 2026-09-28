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
    candidats, non_valides, abstentions = [], [], []
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
        # évolutions CITÉES dans le commentaire (variation relative par rapport à l'exercice précédent de préférence)
        cites = []
        for e in com["enonces"]:
            for s in e.get("sources", []):
                if s.get("nature") == "variation" and s.get("grandeur") == "var_rel_pct":
                    cites.append((e, s))
        if not cites:
            continue
        e, s = min(cites, key=lambda es: (es[1]["exercice_ref"] != exercice - 1, -abs(float(canon(es[1]["valeur"])))))
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
                          "score": round(score, 4), "base_score": base, "n_historique": len(hist),
                          "qualification": qualifier(vp, ns["tendance_meme_signe"]), "objectif": obj,
                          "valeur": dict(v), "valeur_ref": dict(vref)})
    candidats.sort(key=lambda c: -c["score"])
    # une même évolution (mêmes valeurs sources) n'est retenue qu'une fois
    vus, uniques = set(), []
    for c in candidats:
        k = (c["source"]["valeur_id"], c["source"]["valeur_ref_id"])
        if k not in vus:
            vus.add(k)
            uniques.append(c)
    retenus = uniques[:ns["nb_max"]]
    note = _assembler(con, exercice, retenus, candidats, non_valides, abstentions, client, ns)
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


def _gabarits(blocs: dict, retenus: list[dict]) -> None:
    """Rédaction par gabarits déterministes (mode sans modèle de langage, ou repli)."""
    for c in retenus[:3]:
        blocs["Messages clés"].append({"texte": c["enonce"]["texte"], "code": c["code"]})
    for c in retenus:
        t = f"{_nom(c)} : {c['enonce']['texte']} {c['qualification'][:1].upper()}{c['qualification'][1:]}."
        if c["objectif"]:
            o = c["objectif"]
            t += f" Objectif documenté : « {o['texte']} » ({o['titre']}, p. {o['page']})."
        else:
            t += " Aucun objectif documenté dans le corpus."
        blocs["Évolutions marquantes"].append({"texte": t, "code": c["code"]})
    for c in retenus:
        if c["var_rel"] < 0:
            blocs["Points d'attention"].append({"texte": f"Recul observé pour « {_nom(c)} ».", "code": c["code"]})
    for c in retenus:
        if c["var_rel"] < 0:
            p = (f"Examiner les causes du recul de « {_nom(c)} » et envisager des mesures d'accompagnement ciblées.")
        elif c["objectif"]:
            p = (f"Consolider les actions qui soutiennent « {_nom(c)} », en cohérence avec l'objectif documenté.")
        else:
            p = f"Poursuivre le suivi de « {_nom(c)} » et préciser, le cas échéant, un objectif de référence."
        blocs["Pistes pour la décision"].append({"texte": p, "code": c["code"]})


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


def _assembler(con, exercice, retenus, candidats, non_valides, abstentions, client, ns) -> dict:
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
        _gabarits(blocs, retenus)
    if non_valides:
        blocs["Points d'attention"].append({"texte": f"{len(non_valides)} commentaire(s) mobilisé(s) n'ont pas encore "
                                                     "été validés par la Cellule : la note est à relire.", "code": None})
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
    for c in retenus:
        autorisees += ic.construire(con, c["code"], ex, statuts).autorisees()
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
    n_mots = sum(len(b["texte"].split()) for r in RUBRIQUES for b in blocs[r])
    return {
        "type": "note_strategique", "exercice": ex, "titre": f"Note d'analyse stratégique — exercice {ex}",
        "date": datetime.now().strftime("%d/%m/%Y"), "rubriques": blocs,
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
