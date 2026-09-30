"""Choix de l'encodeur (Tableau 3.3) : Succès@5 et MRR sur le jeu de consultation,
temps d'indexation, pour chaque candidat PRÉSENT dans models/embeddings.
Un candidat absent est déclaré « non mesuré » avec la raison : aucun chiffre
n'est inventé.

Chaque candidat est comparé à l'encodeur de repli, question par question
(Wilcoxon apparié sur le rang réciproque de la voie hybride).

Mesure seule, sans refaire toute l'évaluation (quelques minutes à ~1 h par
encodeur sur CPU) :

    python -m minpmeesa.evaluation.choix_encodeur
    python -m minpmeesa.evaluation.choix_encodeur --encodeurs BAAI/bge-m3 --sortie data/results/encodeurs
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from .. import config
from ..retrieval.hybrid import Moteur, fusion_rrf
from ..store import encodeur as encmod, faiss_index
from . import metrics as M, stats


def _eval(m: Moteur, enc, index, jeu, autorises) -> tuple[dict, dict]:
    r = {"dense": {"s5": [], "rr": []}, "hybride": {"s5": [], "rr": []}}
    rrf_k = m.cfg["consultation"]["rrf_k"]
    for q in (q for q in jeu if not q["hors_corpus"]):
        den = faiss_index.rechercher(index, enc.encoder_requete(q["question"]), autorises, 50)
        lex = m.recherche_lexicale(q["question"], autorises, 50)
        for nom, ids in (("dense", [p for p, _ in den[:10]]),
                         ("hybride", [x.passage_id for x in fusion_rrf(lex, den, rrf_k)[:10]])):
            pas = [m.con.execute("SELECT doc_id, page, page_fin FROM passages WHERE passage_id=?", (i,)).fetchone()
                   for i in ids]
            pert = [M.est_pertinent({"doc_id": p[0], "page": p[1], "page_fin": p[2]}, q["pertinents"]) for p in pas]
            r[nom]["s5"].append(M.succes_a_k(pert, 5))
            r[nom]["rr"].append(M.rr(pert))
    n = len(r["dense"]["s5"])
    return ({f"{nom}_{k}": round(sum(v[k2]) / n, 4)
             for nom, v in r.items() for k, k2 in (("succes_5", "s5"), ("mrr", "rr"))}, r)


def comparer(m: Moteur, jeu: list[dict], sortie: Path | None = None,
             seulement: list[str] | None = None) -> list[dict]:
    cfg = m.cfg
    rows = m.con.execute("SELECT passage_id, texte, section FROM passages ORDER BY passage_id").fetchall()
    ids = [r[0] for r in rows]
    textes = [f"{r[2]}\n{r[1]}" for r in rows]
    autorises = m.autorises("publie", exclure_tests=True)
    candidats = list(dict.fromkeys(cfg["embeddings"]["candidats"] + [cfg["embeddings"]["repli_leger"]]))
    ordre = [encmod.NOM_REPLI] + candidats          # le repli d'abord : il sert de référence
    if seulement:
        ordre = [encmod.NOM_REPLI] + [n for n in candidats if n in seulement]
    out, par_q = [], {}
    questions = [q["id"] for q in jeu if not q["hors_corpus"]]
    for nom in ordre:
        ligne = {"encodeur": nom}
        if nom != encmod.NOM_REPLI and not encmod.dossier_modele(nom).exists():
            ligne["statut"] = ("non mesuré : modèle absent de models/embeddings "
                               "(à télécharger avec scripts/telecharger_modeles.py sur un poste connecté)")
            out.append(ligne)
            continue
        try:
            t0 = time.time()
            enc = (encmod.EncodeurLSA(cfg["embeddings"]["repli_hors_ligne_dims"], cfg["graine"]).ajuster(textes)
                   if nom == encmod.NOM_REPLI else encmod.EncodeurST(nom, cfg["embeddings"]["taille_lot"]))
            vect = enc.encoder_passages(textes)
            index = faiss_index.construire(ids, vect)
            ligne["temps_indexation_s"] = round(time.time() - t0, 2)
            ligne["dimension"] = enc.dim
            ligne["longueur_max_tokens"] = getattr(enc, "longueur_max", None)   # None : repli, sans troncature
            moy, detail = _eval(m, enc, index, jeu, autorises)
            ligne.update(moy)
            ligne["statut"] = "mesuré"
            par_q[nom] = detail
            if nom != encmod.NOM_REPLI and encmod.NOM_REPLI in par_q:
                w = stats.wilcoxon(detail["hybride"]["rr"], par_q[encmod.NOM_REPLI]["hybride"]["rr"])
                ligne["wilcoxon_mrr_hybride_vs_repli"] = w
        except Exception as e:  # modèle illisible, dépendance absente…
            ligne["statut"] = f"non mesuré : {type(e).__name__}: {e}"
        out.append(ligne)
    if sortie and par_q:
        from .h1_recuperation import _csv
        _csv(sortie / "tableau_3_3_par_question.csv",
             [{"question": qid, **{f"{nom}|{voie}|{k}": v[voie][k][i]
                                   for nom, v in par_q.items() for voie in ("dense", "hybride") for k in ("s5", "rr")}}
              for i, qid in enumerate(questions)])
    return out


def main():
    ap = argparse.ArgumentParser(description="Tableau 3.3 : comparaison des encodeurs présents dans models/embeddings")
    ap.add_argument("--encodeurs", nargs="*", default=None, help="limiter aux candidats nommés (le repli est toujours mesuré)")
    ap.add_argument("--sortie", default=None, help="dossier de sortie (défaut : data/results/<date>_encodeurs)")
    a = ap.parse_args()
    config.fixer_graine()
    from .h1_recuperation import charger_jeu
    sortie = Path(a.sortie) if a.sortie else config.chemin("resultats") / f"{date.today().isoformat()}_encodeurs"
    sortie.mkdir(parents=True, exist_ok=True)
    m = Moteur()
    t0 = time.time()
    res = comparer(m, charger_jeu(), sortie, a.encodeurs)
    (sortie / "tableau_3_3_encodeurs.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    for e in res:
        if e["statut"] == "mesuré":
            w = e.get("wilcoxon_mrr_hybride_vs_repli")
            print(f"{e['encodeur']:<60} Succès@5 hybride {e['hybride_succes_5']:.2f}  MRR {e['hybride_mrr']:.3f}  "
                  f"dense {e['dense_succes_5']:.2f}/{e['dense_mrr']:.3f}  indexation {e['temps_indexation_s']:.0f} s"
                  + (f"  (vs repli : p = {w['p_value']:.3f})" if w and w.get("p_value") is not None else ""))
        else:
            print(f"{e['encodeur']:<60} {e['statut']}")
    print(f"Durée : {time.time() - t0:.0f} s. Résultats : {sortie}")


if __name__ == "__main__":
    main()
