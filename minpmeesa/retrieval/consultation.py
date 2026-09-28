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


def consulter(question: str, m: Moteur | None = None, mode: str = "hybride",
              journaliser: bool = True, rediger: bool | None = None) -> dict:
    t0 = time.time()
    m = m or moteur_defaut()
    cfg = m.cfg["consultation"]
    autorises = m.autorises(statut="publie")               # filtre AVANT classement
    signal = m.signal_confiance(question, autorises)
    seuil = cfg["seuil_abstention"]
    sortie = {"question": question, "mode": mode, "encodeur": m.nom_encodeur,
              "signal": round(signal, 3), "seuil": seuil, "abstention": False,
              "message": "", "passages": [], "reponse": None}
    if signal < seuil:
        sortie["abstention"] = True
        sortie["message"] = MESSAGE_ABSTENTION
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
            sortie["reponse"] = reponse_redigee(sortie["passages"], question)
    sortie["duree_s"] = round(time.time() - t0, 3)
    if journaliser:
        db.journaliser(m.con, "consultation", {"question": question, "mode": mode},
                       {k: v for k, v in sortie.items() if k != "passages"},
                       sources=[{k: p[k] for k in ("passage_id", "doc_id", "page")} for p in sortie["passages"]],
                       abstentions=[sortie["message"]] if sortie["abstention"] else [],
                       modele=m.nom_encodeur, duree_s=sortie["duree_s"])
    return sortie
