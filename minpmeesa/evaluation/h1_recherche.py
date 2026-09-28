"""H1, partie récupération (section 2.4.1) : lexicale seule, dense seule,
hybride ; Succès@1, Succès@5, MRR, nDCG@5 ; Wilcoxon apparié ; ablation du k
de RRF ; abstention sur les questions hors corpus (calibrage du seuil)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from .. import config
from ..retrieval.hybrid import Recherche
from . import metrics as M
from .stats import wilcoxon_apparie


def charger_jeu(chemin: Optional[Path] = None) -> List[dict]:
    p = chemin or config.chemin("gold") / "consultation.json"
    return json.loads(Path(p).read_text(encoding="utf-8"))["questions"]


def _resultats(rech: Recherche, q: str, mode: str, rrf_k: Optional[int] = None, n: int = 5):
    res = rech.chercher(q, mode=mode, n=n, rrf_k=rrf_k)
    rows = rech.base.passages([r.passage_id for r in res])
    return [(r["doc_id"], r["page"]) for r in rows], [r["passage_id"] for r in rows]


def evaluer_configs(rech: Recherche, jeu: List[dict], dossier: Path, modes=None,
                    ablation_k=None, etiquette: str = "") -> dict:
    modes = modes or (["lexicale", "dense", "hybride"] if rech.dense else ["lexicale"])
    ablation_k = ablation_k if ablation_k is not None else (config.get("recherche.rrf_k_ablation") if rech.dense else [])
    dans = [q for q in jeu if not q["hors_corpus"]]
    configs = [(m, None) for m in modes] + [("hybride", k) for k in ablation_k]
    par_q: Dict[str, Dict[str, dict]] = {}
    for mode, k in configs:
        nom = mode if k is None else f"hybride_k{k}"
        par_q[nom] = {}
        for q in dans:
            pert = {(p["doc_id"], p["page"]) for p in q["pertinents"]}
            res, ids = _resultats(rech, q["question"], mode, k)
            rang = M.rang_pertinent(res, pert)
            par_q[nom][q["id"]] = {"rang": rang, "s1": M.succes_at(rang, 1), "s5": M.succes_at(rang, 5),
                                   "rr": M.rr(rang), "ndcg5": M.ndcg_at(res, pert, 5),
                                   "top5": [f"{d}:p{p}" for d, p in res], "ids": ids}
    resume = {}
    for nom, d in par_q.items():
        n = len(d)
        resume[nom] = {"n": n, "succes_1": sum(x["s1"] for x in d.values()) / n,
                       "succes_5": sum(x["s5"] for x in d.values()) / n,
                       "mrr": sum(x["rr"] for x in d.values()) / n,
                       "ndcg_5": sum(x["ndcg5"] for x in d.values()) / n}
    tests = {}
    if "hybride" in par_q:
        for autre in ("lexicale", "dense"):
            if autre in par_q:
                ids = sorted(par_q["hybride"])
                for met in ("rr", "s5"):
                    a = [par_q["hybride"][i][met] for i in ids]
                    b = [par_q[autre][i][met] for i in ids]
                    tests[f"hybride_vs_{autre}_{met}"] = wilcoxon_apparie(a, b)
    # Écritures.
    dossier.mkdir(parents=True, exist_ok=True)
    with open(dossier / f"h1_recherche_par_question{etiquette}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["configuration", "id", "rang", "succes_1", "succes_5", "rr", "ndcg_5", "top5"])
        for nom, d in par_q.items():
            for qid, x in d.items():
                w.writerow([nom, qid, x["rang"] or "", x["s1"], x["s5"], round(x["rr"], 4),
                            round(x["ndcg5"], 4), " | ".join(x["top5"])])
    with open(dossier / f"h1_recherche_resume{etiquette}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["configuration", "n", "succes_1", "succes_5", "mrr", "ndcg_5"])
        for nom, r in resume.items():
            w.writerow([nom, r["n"], round(r["succes_1"], 4), round(r["succes_5"], 4), round(r["mrr"], 4),
                        round(r["ndcg_5"], 4)])
    return {"resume": resume, "tests": tests, "par_question": par_q}


def calibrer_abstention(rech: Recherche, jeu: List[dict]) -> dict:
    """Seuil sur le meilleur score BM25 de la requête non étendue, choisi pour
    maximiser l'exactitude équilibrée : moyenne de (abstention sur les
    questions hors corpus) et (réponse sur les questions du corpus).
    Attention : calibré et mesuré sur le même jeu (à confirmer sur les
    questions des cadres)."""
    signaux = [(rech.score_bm25_brut(q["question"]), q["hors_corpus"], q["id"]) for q in jeu]
    candidats = sorted({round(s, 3) for s, _, _ in signaux} | {0.0})
    meilleur = None
    for t in candidats:
        hc = [s < t for s, h, _ in signaux if h]
        ic = [s >= t for s, h, _ in signaux if not h]
        ba = (sum(hc) / len(hc) + sum(ic) / len(ic)) / 2 if hc and ic else 0
        if meilleur is None or ba > meilleur[0]:
            meilleur = (ba, t)
    seuil = meilleur[1]
    hc = [(i, s) for s, h, i in signaux if h]
    ic = [(i, s) for s, h, i in signaux if not h]
    return {
        "signal": "bm25_max (requête non étendue)", "seuil": seuil, "exactitude_equilibree": round(meilleur[0], 4),
        "abstention_correcte_hors_corpus": sum(1 for _, s in hc if s < seuil) / len(hc),
        "faux_positifs_hors_corpus": [i for i, s in hc if s >= seuil],
        "fausses_abstentions_dans_corpus": [i for i, s in ic if s < seuil],
        "taux_fausses_abstentions": sum(1 for _, s in ic if s < seuil) / len(ic),
        "signaux": {i: round(s, 3) for s, _, i in signaux},
        "remarque": "seuil calibré et mesuré sur le même jeu de questions (optimiste) ; "
                    "à confirmer sur les questions des cadres (source « cellule »).",
    }


def kappa_annotations(jeu: List[dict]) -> Optional[float]:
    a = [q["annotateur_1"].get("pertinence") for q in jeu]
    b = [q["annotateur_2"].get("pertinence") for q in jeu]
    paires = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(paires) < 5:
        return None
    return M.kappa_cohen([x for x, _ in paires], [y for _, y in paires])
