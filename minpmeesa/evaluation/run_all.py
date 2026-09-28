"""Point d'entrée unique de l'évaluation (chapitre 2.4) :

    python -m minpmeesa.evaluation.run_all [--llm none|ollama] [--sans-seuil]
    python -m minpmeesa.evaluation.run_all --h3 data/results/AAAA-MM-JJ/h3_saisie_temps.xlsx \
                                           --grille data/results/AAAA-MM-JJ/h3_grille_evaluation.xlsx

Écrit tout dans data/results/AAAA-MM-JJ/ : CSV, JSON, figures PNG, resume.md,
manifest.json. Aucune valeur n'est saisie à la main : ce qui ne peut pas être
mesuré est écrit « non mesuré », avec la raison.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from datetime import date
from importlib import metadata
from pathlib import Path

from .. import config
from ..generation import analysis_note, commentary, strategic_note
from ..generation.llm import obtenir
from ..export import docx_export
from ..retrieval import consultation
from ..retrieval.hybrid import Moteur
from . import choix_encodeur, choix_llm, figures, h1_recuperation as h1, h2_controle as h2, h3, stats


def _j(chemin: Path, obj):
    chemin.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _versions() -> dict:
    out = {"python": platform.python_version()}
    for p in ["pymupdf", "rank-bm25", "faiss-cpu", "numpy", "scipy", "scikit-learn", "python-docx",
              "openpyxl", "matplotlib", "streamlit", "sentence-transformers"]:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = "non installé"
    return out


def _machine() -> dict:
    ram = None
    try:
        ram = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (ValueError, OSError, AttributeError):
        pass
    return {"systeme": platform.platform(), "processeur": platform.processor() or platform.machine(),
            "coeurs": os.cpu_count(), "ram_go": ram, "carte_graphique": "non utilisée (CPU seul)"}


def kappa_jeu(jeu: list[dict]) -> dict:
    """Kappa de Cohen sur la pertinence (doc, page) quand la seconde annotation existe."""
    a, b = [], []
    for q in jeu:
        if q.get("annotateur_2") is None or q["hors_corpus"]:
            continue
        p1 = {(r["doc_id"], p) for r in q["pertinents"] for p in r["pages"]}
        p2 = {(r["doc_id"], p) for r in q["annotateur_2"] for p in r["pages"]}
        for x in p1 | p2:
            a.append(x in p1)
            b.append(x in p2)
    if not a:
        return {"statut": "non mesuré", "raison": "seconde annotation (annotateur_2) non encore réalisée"}
    return {"statut": "mesuré", "n_jugements": len(a), "kappa": round(stats.kappa_cohen(a, b), 4)}


def verdict(criteres: list[tuple[str, bool | None]]) -> str:
    if any(ok is False for _, ok in criteres):
        return "non validée"
    if any(ok is None for _, ok in criteres):
        return "non concluante"
    return "validée"


def executer(llm: str | None = None, appliquer_seuil: bool = True) -> Path:
    t0 = time.time()
    cfg = config.charger()
    config.fixer_graine()
    ev = cfg["evaluation"]
    crit = ev["criteres"]
    sortie = config.chemin("resultats") / date.today().isoformat()
    sortie.mkdir(parents=True, exist_ok=True)
    m = Moteur()
    con = m.con
    client, expl_llm = obtenir(cfg, llm)
    jeu = h1.charger_jeu()
    R: dict = {"llm": expl_llm, "encodeur": m.nom_encodeur}
    print("H1 récupération…", flush=True)

    # ---------------- H1 : récupération, abstention, kappa
    R["h1_recuperation"] = h1.evaluer_recuperation(m, jeu, sortie)
    R["h1_abstention"] = {f"{s}/{c}": h1.calibrer_abstention(m, jeu, ev["plis_calibration"], cfg["graine"], sortie, s, c)
                          for s in ("bm25_max", "dense_max") for c in ("refus_a_tort_max", "equilibre")}
    sig = f"{cfg['consultation']['signal_abstention']}/{cfg['consultation']['critere_calibration']}"
    R["h1_abstention_retenue"] = sig
    if appliquer_seuil:
        h1.appliquer_seuil(R["h1_abstention"][sig]["seuil_calibre"])
        m.cfg = config.charger()
    R["kappa_jeu_consultation"] = kappa_jeu(jeu)
    print("Choix de l'encodeur et du modèle de langage…", flush=True)
    R["choix_encodeur"] = choix_encodeur.comparer(m, jeu)
    R["choix_llm"] = choix_llm.comparer(con, cfg, ev["exercice"], ev["nb_indicateurs_llm"])
    _j(sortie / "tableau_3_3_encodeurs.json", R["choix_encodeur"])
    _j(sortie / "tableau_3_2_modeles_langage.json", R["choix_llm"])

    # ---------------- H1 ancrage, H2, analyse des commentaires publiés (2024, puis 2023)
    print("H1 ancrage, H2…", flush=True)
    for ex in (ev["exercice"], ev["exercice_secondaire"]):
        d = sortie / f"exercice_{ex}"
        d.mkdir(exist_ok=True)
        R[f"h1_ancrage_{ex}"] = h2.evaluer_h1_ancrage(con, client, m.encodeur, ex, d)
        R[f"h2_{ex}"] = h2.evaluer_h2(con, client, ex, d, cfg["graine"], ev["echantillon_relecture"])
        R[f"commentaires_publies_{ex}"] = h2.analyser_commentaires_publies(con, ex, d)

    # ---------------- H3 : temps de réponse du système
    print("H3 temps de réponse…", flush=True)
    durees = {"consultation": [], "commentaire": [], "note d'analyse": [], "note stratégique": []}
    for q in jeu:
        durees["consultation"].append(consultation.consulter(q["question"], m)["duree_s"])
    statuts, _ = h2.statuts_evaluation(con, ev["exercice"])
    inds = h2.indicateurs(con, ev["exercice"], statuts)
    for a in inds:
        durees["commentaire"].append(commentary.commenter(con, a["code_indicateur"], ev["exercice"], client, moteur=m)["duree_s"])
    notes_h3 = []
    for k in range(3):
        durees["note d'analyse"].append(analysis_note.rediger(con, ev["exercice"], chapitre=r"CHAPITRE I\b",
                                                              client=client, moteur=m)["duree_s"])
    for ex in (ev["exercice"], ev["exercice_secondaire"]):
        ns = strategic_note.rediger(con, ex, client, m)
        durees["note stratégique"].append(ns["duree_s"])
        f = sortie / f"note_strategique_{ex}.docx"
        docx_export.exporter_note_strategique(ns, f)
        notes_h3.append({"titre": ns["titre"], "fichier": f.name, "verification": strategic_note.verifier_bn4_bn5(ns),
                         "provisoire": ns["provisoire"], "nb_evolutions": ns["nb_evolutions"]})
    R["h3_temps_systeme"] = {k: stats.mediane_p90(v) for k, v in durees.items()}
    R["h3_temps_systeme"]["poste"] = "poste de développement (Linux, CPU) — à refaire sur le poste cible Windows"
    R["h3_verification_automatique_notes"] = notes_h3
    taches = h3.plan(inds)
    h3.protocole_docx(sortie / "h3_protocole_chronometrage.docx", taches)
    h3.saisie_xlsx(sortie / "h3_saisie_temps.xlsx", taches)
    h3.grille_xlsx(sortie / "h3_grille_evaluation.xlsx", notes_h3)
    R["h3_chronometrage"] = {"statut": "non mesuré", "raison": "séance avec au moins 3 cadres à conduire ; "
                             "saisir h3_saisie_temps.xlsx puis relancer avec --h3"}
    R["h3_grille"] = {"statut": "non mesuré", "raison": "notes des deux lecteurs à saisir dans h3_grille_evaluation.xlsx"}

    # ---------------- figures
    res = {r["configuration"]: r for r in R["h1_recuperation"]["resume"]}
    confs = ["lexicale", "dense", f"hybride_k{cfg['consultation']['rrf_k']}"]
    figures.barres_groupees(sortie / "figure_h1_succes5_mrr.png", ["lexicale seule", "dense seule", "hybride"],
                            {"Succès@5": [res[c]["succes_5"] for c in confs], "MRR": [res[c]["mrr"] for c in confs]},
                            "H1 — Succès@5 et MRR par configuration", "score",
                            note=f"n = {R['h1_recuperation']['n_questions']} questions ; encodeur : {m.nom_encodeur}")
    abl = [r for r in R["h1_recuperation"]["resume"]]
    figures.barres_groupees(sortie / "figure_h1_ablations.png", [r["configuration"] for r in abl],
                            {"Succès@5": [r["succes_5"] for r in abl], "MRR": [r["mrr"] for r in abl]},
                            "H1 — ablation (k de la fusion RRF, lexique métier)", "score")
    figures.distribution_temps(sortie / "figure_h3_temps_reponse.png", durees,
                               "Temps de réponse du système par service (poste de développement)")
    h2m = R[f"h2_{ev['exercice']}"]
    if h2m.get("statut") == "mesuré":
        a_, b_ = h2m["ancrage_simple"], h2m["ancrage_citation_litterale"]
        figures.barres_groupees(sortie / "figure_h2_exactitude_couverture.png", ["Exactitude", "Couv_ind"],
                                {"ancrage simple": [a_["exactitude"], a_["couv_ind"]],
                                 "ancrage + citation littérale": [b_["exactitude"], b_["couv_ind"]]},
                                "H2 — exactitude et couverture, avec ou sans contrôle", "taux")
    cp = [R[f"commentaires_publies_{ex}"] for ex in (ev["exercice"], ev["exercice_secondaire"])]
    figures.barres_groupees(sortie / "figure_commentaires_publies.png", [str(c["exercice"]) for c in cp],
                            {"part des valeurs retrouvées littéralement": [c["part_retrouvee"] for c in cp]},
                            "Analyse complémentaire — valeurs des commentaires publiés retrouvées dans les sources",
                            "part")

    R["duree_totale_s"] = round(time.time() - t0, 1)
    _j(sortie / "resultats.json", R)
    manifest = {"date": date.today().isoformat(), "config": cfg, "config_hash": config.config_hash(),
                "graine": cfg["graine"], "encodeur": m.nom_encodeur, "modele_langage": expl_llm,
                "versions": _versions(), "machine": _machine(), "duree_s": R["duree_totale_s"],
                "documents": [{"doc_id": r["doc_id"], "fichier": r["fichier"], "sha256": r["sha256"],
                               "statut_diffusion": r["statut_diffusion"]}
                              for r in con.execute("SELECT * FROM documents ORDER BY doc_id")]}
    _j(sortie / "manifest.json", manifest)
    (sortie / "resume.md").write_text(resume(R, cfg), encoding="utf-8")
    print(f"Résultats : {sortie}")
    return sortie


def _f(x, d=2):
    return "n.m." if x is None else f"{x:.{d}f}".replace(".", ",")


def _p(t):
    return "n.m." if t.get("p_value") is None else f"{t['p_value']:.3f}".replace(".", ",")


def resume(R: dict, cfg: dict) -> str:
    ev, crit = cfg["evaluation"], cfg["evaluation"]["criteres"]
    ex = ev["exercice"]
    res = {r["configuration"]: r for r in R["h1_recuperation"]["resume"]}
    hyb = R["h1_recuperation"]["configuration_reference"]
    s5, meil = res[hyb]["succes_5"], max(res["lexicale"]["succes_5"], res["dense"]["succes_5"])
    mrr_meil = max(res["lexicale"]["mrr"], res["dense"]["mrr"])
    w = R["h1_recuperation"]["wilcoxon"]
    anc = R[f"h1_ancrage_{ex}"]
    h2m = R[f"h2_{ex}"]
    prov = R[f"commentaires_publies_{ex}"].get("provisoire")
    c_h1 = [("Succès@5 ≥ 0,80", s5 >= crit["h1_succes5"]),
            ("hybride ≥ meilleure voie seule", s5 >= meil and res[hyb]["mrr"] >= mrr_meil),
            ("ROUGE-L avec appui > sans appui, p < 0,05",
             None if anc.get("statut") != "mesuré" else
             (anc["rouge_l"]["p_value"] or 1) < 0.05 and anc["rouge_l"]["delta_moyen"] > 0)]
    if h2m.get("statut") == "mesuré":
        c_h2 = [("0 valeur non soutenue après contrôle, ≥ 1 sans", h2m["ancrage_citation_litterale"]["valeurs_non_soutenues"] == 0
                 and h2m["ancrage_simple"]["valeurs_non_soutenues"] >= 1),
                ("TFR < 5 %", None if h2m["tfr_automatique"] is None else h2m["tfr_automatique"] < crit["h2_tfr_max"]),
                ("Couv_ind ≥ 80 %", (h2m["ancrage_citation_litterale"]["couv_ind"] or 0) >= crit["h2_couv_ind_min"])]
    else:
        c_h2 = [("0 valeur non soutenue après contrôle, ≥ 1 sans", None), ("TFR < 5 %", None), ("Couv_ind ≥ 80 %", None)]
    c_h3 = [("réduction du temps médian ≥ 50 %", None), ("≥ 80 % des notes satisfont ≥ 4 critères sur 5", None)]
    t = R["h3_temps_systeme"]
    L = [f"# Résumé de l'évaluation — {R.get('duree_totale_s')} s d'exécution", "",
         "> **Résultats PROVISOIRES** : les tables d'appariement ne sont pas encore validées par double lecture ; "
         "l'évaluation utilise les appariements « candidats »." if prov else "",
         f"> Encodeur utilisé : `{R['encodeur']}`. Modèle de langage : {R['llm']}.", "",
         "## Tableau 4.1 — Confrontation des hypothèses aux critères", "",
         "| Hypothèse | Critère | Valeur mesurée | p-value | Critère atteint ? |", "|---|---|---|---|---|",
         f"| H1 | Succès@5 (hybride) ≥ 0,80 | {_f(s5)} | — | {'oui' if c_h1[0][1] else 'non'} |",
         f"| H1 | hybride ≥ meilleure voie seule (Succès@5 / MRR) | {_f(s5)} vs {_f(meil)} / {_f(res[hyb]['mrr'])} vs {_f(mrr_meil)} "
         f"| lexicale : {_p(w[hyb + '_vs_lexicale_rr'])} ; dense : {_p(w[hyb + '_vs_dense_rr'])} (MRR, Wilcoxon) "
         f"| {'oui' if c_h1[1][1] else 'non'} |",
         f"| H1 | ROUGE-L avec appui > sans appui | "
         + (f"{_f(anc['rouge_l']['moyenne_a'])} vs {_f(anc['rouge_l']['moyenne_b'])} | {_p(anc['rouge_l'])} |" if anc.get("statut") == "mesuré"
            else "non mesuré | — |") + f" {'—' if c_h1[2][1] is None else ('oui' if c_h1[2][1] else 'non')} |",
         ]
    for nom, ok in c_h2:
        L.append(f"| H2 | {nom} | {'voir résultats' if ok is not None else 'non mesuré'} | — | {'—' if ok is None else ('oui' if ok else 'non')} |")
    for nom, ok in c_h3:
        L.append(f"| H3 | {nom} | non mesuré (séance humaine à conduire) | — | — |")
    L += ["", "| Hypothèse | Verdict |", "|---|---|",
          f"| H1 | **{verdict(c_h1)}** |", f"| H2 | **{verdict(c_h2)}** |", f"| H3 | **{verdict(c_h3)}** |", "",
          "Règle : « validée » si tous les critères sont mesurés et atteints ; « non validée » si un critère mesuré "
          "n'est pas atteint ; « non concluante » si des critères restent non mesurés.", "",
          "## Ce qu'il faut retenir, en français simple", ""]
    L.append(f"- **Recherche dans les publications** : sur {R['h1_recuperation']['n_questions']} questions, la bonne page "
             f"figure parmi les 5 premiers résultats dans {_f(100 * s5, 0)} % des cas avec la recherche hybride, contre "
             f"{_f(100 * res['lexicale']['succes_5'], 0)} % (mots-clés seuls) et {_f(100 * res['dense']['succes_5'], 0)} % "
             f"(recherche sémantique seule). Le seuil de 80 % n'est {'pas ' if not c_h1[0][1] else ''}atteint.")
    ab = R["h1_abstention"][R["h1_abstention_retenue"]]
    L.append(f"- **Abstention** (validation croisée) : {_f(100 * ab['taux_abstention_correcte_hors_corpus'], 0)} % des "
             f"questions hors sujet sont refusées ; {ab['abstentions_a_tort_questions_du_corpus']} question(s) du corpus "
             f"sur {ab['n_corpus']} sont refusées à tort. Seuil calibré : {_f(ab['seuil_calibre'], 3)} "
             f"(signal et critère : {R['h1_abstention_retenue']} ; les autres combinaisons figurent dans resultats.json).")
    L.append(f"- **Rédaction avec modèle de langage (H1 ancrage, H2)** : {anc.get('raison') or 'voir resultats.json'}")
    cp = R[f"commentaires_publies_{ex}"]
    L.append(f"- **Analyse complémentaire** (ce n'est pas H2) : dans les commentaires publiés de {ex}, "
             f"{cp['valeurs_retrouvees']} valeurs sur {cp['valeurs_citees']} ({_f(100 * cp['part_retrouvee'], 1)} %) se "
             f"retrouvent telles quelles dans le tableau apparié ou les variations calculées ; les autres se répartissent en "
             + ", ".join(f"{k} : {v}" for k, v in cp["typologie_non_retrouvees"].items()) + ".")
    L.append("- **Temps de réponse du système** (poste de développement) : "
             + " ; ".join(f"{k} : médiane {_f(v['mediane'], 2)} s, P90 {_f(v['p90'], 2)} s"
                          for k, v in t.items() if isinstance(v, dict) and v.get("n")) + ".")
    L += ["", "## Choix des modèles (Tableaux 3.2 et 3.3)", ""]
    for e in R["choix_encodeur"]:
        L.append(f"- {e['encodeur']} : " + (f"Succès@5 (hybride) {_f(e['hybride_succes_5'])}, MRR {_f(e['hybride_mrr'])}, "
                                            f"indexation {_f(e['temps_indexation_s'], 1)} s" if e["statut"] == "mesuré" else e["statut"]))
    for e in R["choix_llm"]:
        L.append(f"- {e['modele']} : " + (f"temps médian {e['temps_median_s']} s, JSON valide {e['taux_json_valide']}, "
                                          f"valeurs écartées {e['taux_valeurs_ecartees']}" if e["statut"] == "mesuré" else e["statut"]))
    L += ["", "## Ce qui reste à faire par l'étudiant", "",
          "- valider les tables d'appariement (double lecture) puis relancer la reconstruction et l'évaluation ;",
          "- faire annoter le jeu de questions par un second lecteur (kappa) et y ajouter les questions des cadres ;",
          "- conduire la séance de chronométrage (≥ 3 cadres) et remplir h3_saisie_temps.xlsx ;",
          "- faire noter les notes stratégiques par 2 lecteurs (h3_grille_evaluation.xlsx) ;",
          "- relire l'échantillon h2_echantillon_relecture.csv (quand un modèle de langage est disponible) ;",
          "- confirmer le statut de diffusion réel de chaque document auprès de la Cellule ;",
          "- lancer l'évaluation sur le poste cible avec les modèles téléchargés (bge-m3, Ollama)."]
    return "\n".join(l for l in L if l is not None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default=None, choices=["ollama", "api", "llamacpp", "none"])
    ap.add_argument("--sans-seuil", action="store_true", help="ne pas reporter le seuil calibré dans config.yaml")
    ap.add_argument("--h3", default=None, help="h3_saisie_temps.xlsx rempli")
    ap.add_argument("--grille", default=None, help="h3_grille_evaluation.xlsx rempli")
    a = ap.parse_args()
    if a.h3 or a.grille:
        cfg = config.charger()["evaluation"]["criteres"]
        out = {}
        if a.h3:
            out["temps"] = h3.calculer_temps(Path(a.h3))
            if out["temps"].get("reduction") is not None:
                out["temps"]["critere_atteint"] = out["temps"]["reduction"] >= cfg["h3_reduction_temps"]
        if a.grille:
            out["grille"] = h3.calculer_grille(Path(a.grille), cfg["h3_moyenne_bn"], cfg["h3_criteres_min"])
            if out["grille"].get("part_conformes") is not None:
                out["grille"]["critere_atteint"] = out["grille"]["part_conformes"] >= cfg["h3_part_notes_conformes"]
        dest = Path(a.h3 or a.grille).parent / "h3_resultats.json"
        _j(dest, out)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    executer(a.llm, not a.sans_seuil)


if __name__ == "__main__":
    main()
