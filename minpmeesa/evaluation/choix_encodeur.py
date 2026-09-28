"""Choix de l'encodeur (Tableau 3.3) : Succès@5 et MRR sur le jeu de consultation,
temps d'indexation, pour chaque candidat PRÉSENT dans models/embeddings.
Un candidat absent est déclaré « non mesuré » avec la raison : aucun chiffre
n'est inventé.
"""
from __future__ import annotations

import time

from ..retrieval.hybrid import Moteur, fusion_rrf
from ..store import encodeur as encmod, faiss_index
from . import metrics as M


def _eval(m: Moteur, enc, index, jeu, autorises) -> dict:
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
    return {f"{nom}_{k}": round(sum(v[k2]) / n, 4)
            for nom, v in r.items() for k, k2 in (("succes_5", "s5"), ("mrr", "rr"))}


def comparer(m: Moteur, jeu: list[dict]) -> list[dict]:
    cfg = m.cfg
    rows = m.con.execute("SELECT passage_id, texte, section FROM passages ORDER BY passage_id").fetchall()
    ids = [r[0] for r in rows]
    textes = [f"{r[2]}\n{r[1]}" for r in rows]
    autorises = m.autorises("publie", exclure_tests=True)
    candidats = list(dict.fromkeys(cfg["embeddings"]["candidats"] + [cfg["embeddings"]["repli_leger"]]))
    out = []
    for nom in candidats + [encmod.NOM_REPLI]:
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
            ligne.update(_eval(m, enc, index, jeu, autorises))
            ligne["statut"] = "mesuré"
        except Exception as e:  # modèle illisible, dépendance absente…
            ligne["statut"] = f"non mesuré : {type(e).__name__}: {e}"
        out.append(ligne)
    return out
