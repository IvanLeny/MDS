"""Choix du modèle de langage (Tableau 3.2) : temps médian d'un commentaire, taux
de JSON valide, taux de valeurs écartées, sur 20 indicateurs.

Candidats Ollama (déployables) : gpt-oss:20b (retenu), llama3.1:8b, qwen2.5:7b-instruct,
mistral:7b-instruct, llama3.2:3b. Moteur `api` (développement) : openai/gpt-oss-20b
(mêmes poids que gpt-oss:20b) et, en option, openai/gpt-oss-120b comme BORNE
HAUTE, non déployable. Un candidat indisponible est déclaré « non mesuré ».
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import time
from datetime import date

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


def comparer(con, cfg: dict, exercice: int, n: int = 20, api: bool = True, bavard: bool = False) -> list[dict]:
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
        if bavard:
            print(f"  ollama / {nom} : {len(inds)} commentaires…", flush=True)
        out.append({**ligne, "statut": "mesuré", "provisoire": provisoire, **_mesurer(con, c, inds)})
        if bavard:
            print(f"    temps médian {out[-1]['temps_median_s']} s", flush=True)
    if not api:
        return out
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


def main():
    """Mesure le Tableau 3.2 seul, sur le poste courant (modèles Ollama installés)."""
    from .. import config
    from ..store import db
    from .run_all import _machine

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exercice", type=int, default=None)
    ap.add_argument("--n", type=int, default=None, help="nombre d'indicateurs (20 par défaut)")
    ap.add_argument("--avec-api", action="store_true", help="mesurer aussi le moteur api (clé requise)")
    a = ap.parse_args()
    cfg = config.charger()
    config.fixer_graine()
    ev = cfg["evaluation"]
    ex, n = a.exercice or ev["exercice"], a.n or ev["nb_indicateurs_llm"]
    sortie = config.chemin("resultats") / f"{date.today().isoformat()}_choix_llm_poste"
    sortie.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    lignes = comparer(db.connecter(), cfg, ex, n, api=a.avec_api, bavard=True)
    res = {"exercice": ex, "n_indicateurs": n, "machine": _machine(), "duree_s": round(time.time() - t0, 1),
           "config_hash": config.config_hash(cfg), "config_locale": cfg.get("config_locale"),
           "tableau_3_2": lignes}
    (sortie / "tableau_3_2_modeles_langage.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    for l in lignes:
        print(f"{l['moteur']} / {l['modele']} : " + (
            f"temps médian {l['temps_median_s']} s, JSON valide {l['taux_json_valide']:.0%}, "
            f"valeurs écartées {l['taux_valeurs_ecartees']}, échecs {l['appels_en_echec']}"
            if l["statut"] == "mesuré" else l["statut"]))
    print(f"Résultats : {sortie}")


if __name__ == "__main__":
    main()
