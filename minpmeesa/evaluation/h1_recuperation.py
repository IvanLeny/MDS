"""H1 (partie récupération) : Succès@1, Succès@5, MRR, nDCG@5 pour les trois
configurations (lexicale seule, dense seule, hybride), ablation de k (RRF) et
du lexique, Wilcoxon apparié, calibration de l'abstention (validation croisée).
"""
from __future__ import annotations

import csv
import json
import random
import time
from pathlib import Path

from .. import config
from ..retrieval.hybrid import Moteur
from ..store import db
from . import metrics as M
from . import stats


def charger_jeu(chemin: Path | None = None) -> list[dict]:
    chemin = chemin or config.chemin("gold") / "consultation.json"
    return json.loads(chemin.read_text(encoding="utf-8"))["questions"]


def _classement(m: Moteur, q: str, autorises: list[int], mode: str, rrf_k: int, expansion: bool, k: int = 10):
    res = m.rechercher(q, autorises, mode=mode, k=k, rrf_k=rrf_k, expansion=expansion)
    out = []
    for r in res:
        p = m.con.execute("SELECT doc_id, page, page_fin FROM passages WHERE passage_id=?",
                          (r.passage_id,)).fetchone()
        out.append({"passage_id": r.passage_id, "doc_id": p[0], "page": p[1], "page_fin": p[2]})
    return out


def configurations(cfg: dict) -> list[dict]:
    c = cfg["consultation"]
    confs = [{"nom": "lexicale", "mode": "lexicale", "rrf_k": c["rrf_k"], "expansion": c["expansion_lexique"]},
             {"nom": "dense", "mode": "dense", "rrf_k": c["rrf_k"], "expansion": c["expansion_lexique"]}]
    for k in c["rrf_k_ablation"]:
        confs.append({"nom": f"hybride_k{k}", "mode": "hybride", "rrf_k": k, "expansion": c["expansion_lexique"]})
    confs.append({"nom": "hybride_sans_lexique", "mode": "hybride", "rrf_k": c["rrf_k"], "expansion": False})
    confs.append({"nom": "lexicale_sans_lexique", "mode": "lexicale", "rrf_k": c["rrf_k"], "expansion": False})
    return confs


def evaluer_recuperation(m: Moteur, jeu: list[dict], sortie: Path | None = None) -> dict:
    cfg = m.cfg
    autorises = m.autorises("publie", exclure_tests=True)
    questions = [q for q in jeu if not q["hors_corpus"]]
    lignes, par_conf = [], {}
    for conf in configurations(cfg):
        vals = {"s1": [], "s5": [], "rr": [], "ndcg5": [], "duree": []}
        for q in questions:
            t0 = time.time()
            cl = _classement(m, q["question"], autorises, conf["mode"], conf["rrf_k"], conf["expansion"])
            vals["duree"].append(time.time() - t0)
            pert = [M.est_pertinent(p, q["pertinents"]) for p in cl]
            n_pert = sum(len(r["pages"]) for r in q["pertinents"])
            s1, s5, r_, nd = M.succes_a_k(pert, 1), M.succes_a_k(pert, 5), M.rr(pert), M.ndcg_a_k(pert, 5, n_pert)
            for k, v in zip(("s1", "s5", "rr", "ndcg5"), (s1, s5, r_, nd)):
                vals[k].append(v)
            rang = next((i + 1 for i, p in enumerate(pert) if p), None)
            lignes.append({"configuration": conf["nom"], "id": q["id"], "succes_1": s1, "succes_5": s5,
                           "rr": round(r_, 4), "ndcg_5": round(nd, 4), "rang_premier_pertinent": rang,
                           "top1": f"{cl[0]['doc_id']} p.{cl[0]['page']}" if cl else ""})
        par_conf[conf["nom"]] = vals
    n = len(questions)
    resume = []
    for nom, v in par_conf.items():
        resume.append({"configuration": nom, "n": n,
                       "succes_1": round(sum(v["s1"]) / n, 4), "succes_5": round(sum(v["s5"]) / n, 4),
                       "mrr": round(sum(v["rr"]) / n, 4), "ndcg_5": round(sum(v["ndcg5"]) / n, 4),
                       "duree_mediane_s": stats.mediane_p90(v["duree"])["mediane"]})
    k_ref = cfg["consultation"]["rrf_k"]
    hyb = f"hybride_k{k_ref}"
    tests = {}
    for seule in ("lexicale", "dense"):
        for met in ("rr", "s5"):
            tests[f"{hyb}_vs_{seule}_{met}"] = stats.wilcoxon(par_conf[hyb][met], par_conf[seule][met])
    res = {"n_questions": n, "encodeur": m.nom_encodeur, "configuration_reference": hyb,
           "resume": resume, "wilcoxon": tests}
    if sortie:
        sortie.mkdir(parents=True, exist_ok=True)
        _csv(sortie / "h1_recuperation_par_question.csv", lignes)
        _csv(sortie / "h1_recuperation_configurations.csv", resume)
    return res


def signaux(m: Moteur, jeu: list[dict], signal: str | None = None) -> list[tuple[str, float, bool]]:
    autorises = m.autorises("publie", exclure_tests=True)
    return [(q["id"], m.signal_confiance(q["question"], autorises, signal), q["hors_corpus"]) for q in jeu]


def _meilleur_seuil(sig: list[tuple[float, bool]]) -> float:
    """Seuil maximisant l'exactitude équilibrée (abstention sur hors corpus,
    réponse sur les questions du corpus)."""
    valeurs = sorted({s for s, _ in sig})
    cands = [(a + b) / 2 for a, b in zip(valeurs, valeurs[1:])] or valeurs
    best, best_s = None, -1.0
    for t in cands:
        hc = [s for s, h in sig if h]
        ic = [s for s, h in sig if not h]
        tpr = sum(s < t for s in hc) / len(hc) if hc else 0
        tnr = sum(s >= t for s in ic) / len(ic) if ic else 0
        score = (tpr + tnr) / 2
        if score > best_s + 1e-12:
            best, best_s = t, score
    return float(best)


def calibrer_abstention(m: Moteur, jeu: list[dict], plis: int, graine: int, sortie: Path | None = None,
                        signal: str | None = None) -> dict:
    """Seuil calibré + estimation HORS ÉCHANTILLON par validation croisée stratifiée."""
    signal = signal or m.cfg["consultation"]["signal_abstention"]
    sig = signaux(m, jeu, signal)
    rng = random.Random(graine)
    hc = [s for s in sig if s[2]]
    ic = [s for s in sig if not s[2]]
    rng.shuffle(hc)
    rng.shuffle(ic)
    folds = [hc[i::plis] + ic[i::plis] for i in range(plis)]
    decisions = []
    for i in range(plis):
        train = [(s, h) for j, f in enumerate(folds) if j != i for _, s, h in f]
        t = _meilleur_seuil(train)
        for qid, s, h in folds[i]:
            decisions.append({"id": qid, "signal": round(s, 3), "hors_corpus": h,
                              "seuil_pli": round(t, 3), "abstention": s < t})
    n_hc = sum(1 for d in decisions if d["hors_corpus"])
    n_ic = len(decisions) - n_hc
    abst_ok = sum(1 for d in decisions if d["hors_corpus"] and d["abstention"])
    faux_pos = sum(1 for d in decisions if not d["hors_corpus"] and d["abstention"])
    rep_hc = sum(1 for d in decisions if d["hors_corpus"] and not d["abstention"])
    seuil = _meilleur_seuil([(s, h) for _, s, h in sig])
    res = {"signal": signal,
           "description_signal": {"bm25_max": "meilleur score BM25 de la question (sans expansion)",
                                  "dense_max": "meilleur cosinus de la voie dense"}[signal],
           "seuil_calibre": round(seuil, 3), "plis": plis,
           "taux_abstention_correcte_hors_corpus": round(abst_ok / n_hc, 4) if n_hc else None,
           "abstentions_a_tort_questions_du_corpus": faux_pos,
           "taux_abstention_a_tort": round(faux_pos / n_ic, 4) if n_ic else None,
           "reponses_hors_corpus_non_abstenues": rep_hc, "n_hors_corpus": n_hc, "n_corpus": n_ic}
    if sortie:
        _csv(sortie / f"h1_abstention_validation_croisee_{signal}.csv", decisions)
    return res


def _csv(chemin: Path, lignes: list[dict]):
    if not lignes:
        return
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]), delimiter=";")
        w.writeheader()
        w.writerows(lignes)


def appliquer_seuil(seuil: float, chemin_config: Path | None = None) -> None:
    """Reporte le seuil calibré dans config.yaml (ligne seuil_abstention)."""
    import re
    p = chemin_config or (config.RACINE / "config.yaml")
    s = p.read_text(encoding="utf-8")
    s = re.sub(r"(seuil_abstention:\s*)[0-9.]+(\s*#.*)?",
               lambda m: f"{m.group(1)}{seuil}  # calibré (evaluation.h1_recuperation, validation croisée)", s)
    p.write_text(s, encoding="utf-8")
    config.charger.cache_clear()
