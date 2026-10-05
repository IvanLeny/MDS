"""Service 1 : consultation de la base (BF8, section 3.2.5).

Question libre -> 5 passages sourcés (document, page, extrait), ou abstention
« Aucune source suffisante trouvée dans les publications ».
Filtre obligatoire : statut_diffusion = 'publie', appliqué dans la requête.
"""
from __future__ import annotations

import re
import time

from ..guards import literal_check
from ..store import db
from ..texte import ensemble
from .hybrid import Moteur, moteur as moteur_defaut

MESSAGE_ABSTENTION = "Aucune source suffisante trouvée dans les publications."


def _extrait(texte: str, question: str, n: int = 420) -> str:
    """Extrait centré sur la phrase qui recoupe le plus la question."""
    phrases = re.split(r"(?<=[.;!?])\s+|\n", texte)
    q = ensemble(question)
    meilleur = max(range(len(phrases)), key=lambda i: len(ensemble(phrases[i]) & q), default=0)
    debut = max(0, meilleur - 1)
    ext = " ".join(phrases[debut:debut + 4]).strip()
    return (ext[:n] + "…") if len(ext) > n else ext


def reponse_redigee(passages: list[dict], question: str) -> dict:
    """Réponse courte FACULTATIVE, extractive (phrases des passages), soumise au
    contrôle de citation littérale contre ces mêmes passages."""
    q = ensemble(question)
    cand = []
    for p in passages[:3]:
        for ph in re.split(r"(?<=[.;!?])\s+", p["texte"]):
            s = len(ensemble(ph) & q)
            if s:
                cand.append((s, ph.strip(), p))
    cand.sort(key=lambda c: -c[0])
    enonces = [{"type": "constat", "texte": c[1], "valeurs": []} for c in cand[:2]]
    autorisees = [{"texte": v, "source": {"passage_id": p["passage_id"], "doc_id": p["doc_id"], "page": p["page"]}}
                  for p in passages for v in literal_check.nombres(p["texte"])]
    ctrl = literal_check.controler(enonces, autorisees, [])
    return {"texte": " ".join(e["texte"] for e in ctrl.enonces), "valeurs_ecartees": ctrl.ecartees}


# Le modèle déclare ne pas trouver la réponse alors que la recherche a restitué des extraits
# pertinents (signal au-dessus du seuil) : on présente plutôt la réponse extractive.
_NE_REPOND_PAS = re.compile(r"ne (r[ée]pondent|permettent|contiennent|fournissent|mentionnent) pas|"
                            r"pas d'information|aucune information|ne sais pas|impossible de r[ée]pondre", re.I)


def reponse_llm(client, passages: list[dict], question: str) -> dict | None:
    """Reformulation en français clair par le modèle de langage (facultative), à partir des
    seuls extraits restitués ; chaque chiffre est contrôlé contre ces extraits."""
    import json
    import re as _re
    from ..generation import prompts
    extraits = [p["texte"][:1500] for p in passages[:3]]
    try:
        brut = client.generer(prompts.SYSTEME_REFORMULATION, prompts.utilisateur_reformulation(question, extraits))
        texte = json.loads(_re.sub(r"^```(?:json)?|```$", "", brut.strip(), flags=_re.M)).get("reponse", "")
    except Exception:
        return None
    if not isinstance(texte, str) or not texte.strip() or _NE_REPOND_PAS.search(texte):
        return None                      # repli sur la réponse extractive (signalé)
    autorisees = [{"texte": v, "source": {"passage_id": p["passage_id"], "doc_id": p["doc_id"], "page": p["page"]}}
                  for p in passages[:3] for v in literal_check.nombres(p["texte"])]
    ctrl = literal_check.controler([{"type": "constat", "texte": t} for t in _re.split(r"(?<=[.!?])\s+", texte) if t],
                                   autorisees, [])
    if not ctrl.enonces:
        return None
    return {"texte": " ".join(e["texte"] for e in ctrl.enonces), "valeurs_ecartees": ctrl.ecartees,
            "redaction": getattr(client, "nom", "modèle de langage")}


def suggestions(question: str, m: Moteur, n: int = 3) -> list[str]:
    """En cas de refus : intitulés d'indicateurs de l'Annuaire proches de la question (mots en
    commun, même année de préférence), retenus seulement s'ils passent eux-mêmes le seuil
    d'abstention. Le seuil n'est pas modifié : on aide l'utilisateur à reformuler (plan C4)."""
    mots = ensemble(question)
    annees = set(re.findall(r"\b20\d\d\b", question))
    if not mots:
        return []
    cand = []
    for (titre,) in m.con.execute("SELECT DISTINCT graphique_intitule FROM appariement "
                                  "WHERE graphique_intitule IS NOT NULL ORDER BY exercice DESC"):
        commun = len(mots & ensemble(titre))
        if commun:
            cand.append((commun + 0.5 * bool(annees & set(re.findall(r"\b20\d\d\b", titre))), titre))
    cand.sort(key=lambda c: -c[0])
    autorises = m.autorises(statut="publie")
    seuil = seuil_pour(m.cfg["consultation"], m.nom_encodeur)
    out = []
    for _, titre in cand[:15]:
        t = re.sub(r"\s*\(en ?%\)\s*", " ", titre).strip()
        if t not in out and m.signal_confiance(t, autorises) >= seuil:
            out.append(t)
        if len(out) == n:
            break
    return out


def seuil_pour(cfg_consultation: dict, encodeur: str) -> float:
    """Seuil d'abstention calibré pour l'encodeur de la base (le signal en dépend)."""
    return (cfg_consultation.get("seuils_par_encodeur") or {}).get(encodeur, cfg_consultation["seuil_abstention"])


def consulter(question: str, m: Moteur | None = None, mode: str = "hybride",
              journaliser: bool = True, rediger: bool | None = None, client=None) -> dict:
    t0 = time.time()
    m = m or moteur_defaut()
    cfg = m.cfg["consultation"]
    autorises = m.autorises(statut="publie")               # filtre AVANT classement
    signal = m.signal_confiance(question, autorises)
    seuil = seuil_pour(cfg, m.nom_encodeur)
    sortie = {"question": question, "mode": mode, "encodeur": m.nom_encodeur,
              "signal": round(signal, 3), "seuil": seuil, "abstention": False,
              "message": "", "passages": [], "reponse": None}
    if signal < seuil:
        sortie["abstention"] = True
        sortie["message"] = MESSAGE_ABSTENTION
        sortie["suggestions"] = suggestions(question, m)
    else:
        for r in m.rechercher(question, autorises, mode=mode, k=cfg["top_n"]):
            p = db.passage(m.con, r.passage_id)
            sortie["passages"].append({
                "passage_id": p["passage_id"], "doc_id": p["doc_id"], "titre": p["titre"],
                "type": p["type"], "exercice": p["exercice"], "fichier": p["fichier"],
                "page": p["page"], "page_fin": p["page_fin"], "nature": p["nature"],
                "section": p["section"], "extrait": _extrait(p["texte"], question),
                "texte": p["texte"], "score": round(r.score, 5)})
        if (cfg["reponse_redigee"] if rediger is None else rediger) and sortie["passages"]:
            r = reponse_llm(client, sortie["passages"], question) if client is not None else None
            sortie["reponse"] = r or {**reponse_redigee(sortie["passages"], question),
                                      "redaction": "extractive" if client is None else
                                      "extractive (repli : réponse du modèle inexploitable)"}
    sortie["duree_s"] = round(time.time() - t0, 3)
    if journaliser:
        db.journaliser(m.con, "consultation", {"question": question, "mode": mode},
                       {k: v for k, v in sortie.items() if k != "passages"},
                       sources=[{k: p[k] for k in ("passage_id", "doc_id", "page")} for p in sortie["passages"]],
                       abstentions=[sortie["message"]] if sortie["abstention"] else [],
                       modele=m.nom_encodeur, duree_s=sortie["duree_s"])
    return sortie
