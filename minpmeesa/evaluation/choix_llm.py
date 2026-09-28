"""Choix du modèle de langage (Tableau 3.2) : temps médian d'un commentaire, taux
de JSON valide, taux de valeurs écartées, sur 20 indicateurs.

Candidats Ollama (déployables) : gpt-oss:20b (retenu), llama3.1:8b, qwen2.5:7b-instruct,
mistral:7b-instruct, llama3.2:3b. Moteur `api` (développement) : openai/gpt-oss-20b
(mêmes poids que gpt-oss:20b) et, en option, openai/gpt-oss-120b comme BORNE
HAUTE, non déployable. Un candidat indisponible est déclaré « non mesuré ».
"""
from __future__ import annotations

import statistics as st
import time

from ..generation import commentary as cm
from ..generation.llm import ErreurLLM, Ollama, client_api
from . import h2_controle


def _mesurer(con, client, inds) -> dict:
    durees, json_ok, citees, ecartees, echecs = [], 0, 0, 0, 0
    for a in inds:
        t0 = time.time()
        r = cm.commenter(con, a["code_indicateur"], a["exercice"], client)
        durees.append(time.time() - t0)
        motif = r.get("motif") or ""
        json_ok += int("JSON invalide" not in motif)
        echecs += int("indisponible" in motif)
        citees += sum(len(cm.literal_check.nombres(e["texte"])) for e in r.get("enonces_avant_controle", []))
        ecartees += len(r.get("valeurs_ecartees", []))
    return {"n_indicateurs": len(inds), "temps_median_s": round(st.median(durees), 2),
            "taux_json_valide": round(json_ok / len(inds), 4),
            "taux_valeurs_ecartees": round(ecartees / citees, 4) if citees else None,
            "appels_en_echec": echecs}


def comparer(con, cfg: dict, exercice: int, n: int = 20) -> list[dict]:
    statuts, provisoire = h2_controle.statuts_evaluation(con, exercice)
    inds = h2_controle.indicateurs(con, exercice, statuts)
    if len(inds) < n:                       # complète avec l'exercice précédent
        inds += h2_controle.indicateurs(con, exercice - 1, statuts)
    inds = inds[:n]
    l, o = cfg["llm"], cfg["llm"]["ollama"]
    out = []
    for nom in o["candidats"]:
        c = Ollama(nom, o["url"], l["temperature"], o["delai_max_s"], cfg["graine"])
        ligne = {"moteur": "ollama", "modele": nom, "deployable": True, "retenu": nom == o["modele"]}
        if not c.disponible():
            out.append({**ligne, "statut": "non mesuré : modèle non installé dans Ollama (ou Ollama non lancé)"})
            continue
        out.append({**ligne, "statut": "mesuré", "provisoire": provisoire, **_mesurer(con, c, inds)})
    a = l["api"]
    for nom, borne in ((a["modele"], False), (a.get("modele_borne_haute"), True)):
        if not nom:
            continue
        ligne = {"moteur": f"api:{a['fournisseur']}", "modele": nom, "deployable": False,
                 "borne_haute": borne, "retenu": False}
        try:
            c = client_api(cfg, nom)
        except ErreurLLM as e:
            out.append({**ligne, "statut": f"non mesuré : {e}"})
            continue
        m = _mesurer(con, c, inds)
        if m["appels_en_echec"] == len(inds):
            out.append({**ligne, "statut": "non mesuré : service distant injoignable"})
        else:
            out.append({**ligne, "statut": "mesuré", "provisoire": provisoire, **m,
                        "remarque": "temps mesuré à distance (réseau inclus), non transposable au poste cible"})
    return out
