"""Choix du modèle de langage (Tableau 3.2) : temps médian d'un commentaire, taux
de JSON valide, taux de valeurs écartées, sur 20 indicateurs. Un candidat non
installé dans Ollama est déclaré « non mesuré »."""
from __future__ import annotations

import statistics as st
import time

from ..generation import commentary as cm
from ..generation.llm import Ollama
from . import h2_controle


def comparer(con, cfg: dict, exercice: int, n: int = 20) -> list[dict]:
    statuts, provisoire = h2_controle.statuts_evaluation(con, exercice)
    inds = h2_controle.indicateurs(con, exercice, statuts)
    # complète avec l'exercice précédent si l'exercice n'a pas n indicateurs
    if len(inds) < n:
        inds += h2_controle.indicateurs(con, exercice - 1, statuts)
    inds = inds[:n]
    out = []
    for nom in cfg["llm"]["candidats"]:
        c = Ollama(nom, cfg["llm"]["url"], cfg["llm"]["temperature"], cfg["llm"]["delai_max_s"], cfg["graine"])
        if not c.disponible():
            out.append({"modele": nom, "statut": "non mesuré : modèle non installé dans Ollama "
                                                   "(ou Ollama non lancé) sur ce poste"})
            continue
        durees, json_ok, citees, ecartees = [], 0, 0, 0
        for a in inds:
            t0 = time.time()
            r = cm.commenter(con, a["code_indicateur"], a["exercice"], c)
            durees.append(time.time() - t0)
            json_ok += int("JSON invalide" not in (r.get("motif") or ""))
            citees += sum(len(e.get("valeurs", [])) for e in r.get("enonces_avant_controle", []))
            ecartees += len(r.get("valeurs_ecartees", []))
        out.append({"modele": nom, "statut": "mesuré", "provisoire": provisoire, "n_indicateurs": len(inds),
                    "temps_median_s": round(st.median(durees), 2),
                    "taux_json_valide": round(json_ok / len(inds), 4),
                    "taux_valeurs_ecartees": round(ecartees / citees, 4) if citees else None})
    return out
