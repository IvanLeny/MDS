"""Reconstruit TOUTE la base depuis data/corpus/ en une commande :

    python -m minpmeesa.ingestion.build            # base + index BM25 + index dense
    python -m minpmeesa.ingestion.build --sans-dense

Étapes : registre -> tableaux (triplets) -> passages (texte, tableau, graphique)
-> appariement (candidats ou validés) -> variations -> inventaire et fichiers
d'appariement à valider -> index de recherche.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .. import config
from ..compute.variations import recalculer_tout
from ..store.db import Base
from . import pairing
from .chunk import (Passage, compter_tokens, graphiques_rapport, lignes_document,
                    passages_texte, rubrique_pour, section_de_page)
from .extract import extraire
from .registry import charger_corrections, decrire
from .tables import extraire_tableaux


def _extrait(t: str, n: int = 300) -> str:
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


def construire(corpus: Optional[Path] = None, chemin_base: Optional[Path] = None,
               dense: bool = True, verbeux: bool = True, fichiers: Optional[List[Path]] = None,
               dossier_index: Optional[Path] = None, dossier_appariement: Optional[Path] = None) -> dict:
    t0 = time.time()
    cfg = config.charger()
    corpus = corpus or config.chemin("corpus")
    chemin_base = chemin_base or config.chemin("base")
    if str(chemin_base) != ":memory:" and Path(chemin_base).exists():
        Path(chemin_base).unlink()
    base = Base(chemin_base)
    corrections = charger_corrections(corpus)
    ing = cfg["ingestion"]

    fiches, tableaux_doc, graphiques_doc, stats = {}, {}, {}, defaultdict(Counter)
    passages_graphique: Dict[tuple, int] = {}
    pdfs = fichiers if fichiers is not None else sorted(corpus.glob("*.pdf"))
    for pdf in pdfs:
        doc = extraire(pdf)
        fiche = decrire(pdf, doc, corrections)
        if fiche["doc_id"] in fiches:
            raise ValueError(f"Deux fichiers donnent le même doc_id {fiche['doc_id']} : "
                             f"{fiches[fiche['doc_id']]['fichier']} et {pdf.name}")
        fiches[fiche["doc_id"]] = fiche
        base.ajouter_document(fiche)
        did = fiche["doc_id"]

        # 1) Tableaux -> triplets + passages « tableau ».
        tabs = extraire_tableaux(str(pdf))
        tableaux_doc[did] = tabs
        zones: Dict[int, list] = defaultdict(list)
        for t in tabs:
            zones[t.page].append(t.bbox)
        lignes = lignes_document(doc, zones, ing["titre_courant_ratio"])
        defaut = "Préambule"
        sections = section_de_page(lignes, defaut)
        for t in tabs:
            ids = []
            for tr in t.triplets:
                ids.append(base.ajouter_valeur({
                    "doc_id": did, "page": t.page, "tableau_n": t.numero,
                    "tableau_intitule": t.intitule, "ligne": tr.ligne, "colonne": tr.colonne,
                    "valeur_texte": tr.valeur_texte, "valeur_num": tr.valeur_num, "unite": tr.unite}))
            stats[did]["valeurs"] += len(ids)
            chap, sec = rubrique_pour(t.page, sections, defaut)
            texte = t.texte()
            # Un très grand tableau est coupé en plusieurs passages (≤ max tokens).
            morceaux, cour = [], []
            for l in texte.splitlines():
                cour.append(l)
                if compter_tokens("\n".join(cour)) >= ing["passage_max_tokens"]:
                    morceaux.append("\n".join(cour))
                    cour = [texte.splitlines()[0] + " (suite)"]
            if len(cour) > 1:
                morceaux.append("\n".join(cour))
            for m in morceaux:
                base.ajouter_passage({"doc_id": did, "page": t.page, "chapitre": chap,
                                      "section": sec, "nature": "tableau", "texte": m,
                                      "nb_tokens": compter_tokens(m)})
                stats[did]["passages_tableau"] += 1
        stats[did]["tableaux"] = len({t.numero for t in tabs if t.numero} |
                                     {(t.page, t.bbox) for t in tabs if not t.numero})

        # 2) Rapport d'analyse : un passage « graphique » par commentaire.
        if fiche["type"] == "rapport_analyse":
            gs = graphiques_rapport(lignes)
            graphiques_doc[did] = gs
            stats[did]["graphiques"] = len(gs)
            for g in gs:
                texte = f"Graphique {g.numero} : {g.intitule}\n{g.commentaire}".strip()
                pid = base.ajouter_passage({"doc_id": did, "page": g.page, "chapitre": g.chapitre,
                                            "section": g.section, "nature": "graphique",
                                            "texte": texte, "nb_tokens": compter_tokens(texte)})
                passages_graphique[(did, g.numero)] = pid
                stats[did]["passages_graphique"] += 1
        else:
            stats[did]["graphiques"] = len({l.texte.split(":")[0] for l in lignes
                                            if l.texte.startswith("Graphique ")})

        # 3) Prose.
        for p in passages_texte(lignes, ing, defaut):
            base.ajouter_passage({"doc_id": did, "page": p.page, "chapitre": p.chapitre,
                                  "section": p.section, "nature": "texte", "texte": p.texte,
                                  "nb_tokens": p.nb_tokens})
            stats[did]["passages_texte"] += 1
        if verbeux:
            print(f"  {pdf.name:45s} -> {did:28s} {fiche['type']:16s} {fiche['exercice']} "
                  f"{fiche['trimestre'] or '':3s} | {stats[did]['valeurs']:5d} valeurs, "
                  f"{sum(v for k, v in stats[did].items() if k.startswith('passages'))} passages")
    base.commit()

    # 4) Appariement.
    appariement = apparier(base, fiches, tableaux_doc, graphiques_doc, passages_graphique, verbeux,
                           dossier_appariement or config.chemin("appariement"))

    # 5) Variations calculées par le programme.
    n_var = recalculer_tout(base)

    # 6) Inventaire (Annexe I).
    ecrire_inventaire(corpus / "inventaire.csv", fiches, stats)
    manquants = corpus_manquant(fiches)
    rapport = {"documents": len(fiches), "passages": base.q("SELECT COUNT(*) n FROM passages")[0]["n"],
               "valeurs": base.q("SELECT COUNT(*) n FROM valeurs")[0]["n"],
               "variations": n_var, "appariement": appariement, "manquants": manquants,
               "duree_s": round(time.time() - t0, 1)}
    if verbeux:
        for m in manquants:
            print(f"  ATTENTION corpus incomplet : {m}")

    # 7) Index de recherche.
    if str(chemin_base) != ":memory:":
        from ..store.bm25_index import construire_bm25
        construire_bm25(base, (dossier_index / "bm25.pkl") if dossier_index else None)
        if dense:
            from ..store.faiss_index import construire_faiss
            try:
                info = construire_faiss(base, dossier=dossier_index)
                rapport["index_dense"] = info
            except Exception as e:  # modèle absent : la consultation reste lexicale
                rapport["index_dense"] = f"non construit : {e}"
                if verbeux:
                    print(f"  Index dense non construit : {e}")
        rapport["duree_s"] = round(time.time() - t0, 1)
        Path(chemin_base).with_name("build_rapport.json").write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    if verbeux:
        print(f"Base reconstruite en {rapport['duree_s']} s : {rapport['documents']} documents, "
              f"{rapport['passages']} passages, {rapport['valeurs']} valeurs, {n_var} variations.")
    base.fermer() if str(chemin_base) != ":memory:" else None
    return rapport if str(chemin_base) != ":memory:" else {**rapport, "base": base}


def apparier(base, fiches, tableaux_doc, graphiques_doc, passages_graphique, verbeux, dossier: Path) -> dict:
    """Propose un tableau pour chaque graphique ; applique les validations
    humaines existantes ; écrit data/pairing/a_valider_AAAA.xlsx."""
    validations = pairing.charger_validations(dossier)
    par_ex = {}
    for did, gs in graphiques_doc.items():
        par_ex[fiches[did]["exercice"]] = (did, gs)
    codes = pairing.attribuer_codes({ex: gs for ex, (_, gs) in par_ex.items()})
    bilan = Counter()
    for ex, (rap, gs) in sorted(par_ex.items()):
        ann = next((d for d, f in fiches.items() if f["type"] == "annuaire" and f["exercice"] == ex), None)
        lignes_xlsx = []
        for g in gs:
            code = codes[(ex, g.numero)]
            cands = pairing.proposer(g, tableaux_doc.get(ann, [])) if ann else []
            meilleur = cands[0] if cands else None
            v = validations.get((code, ex))
            statut = v["statut"] if v else "candidat"
            tab_n = int(v["tableau_n"]) if v and v.get("tableau_n") else (meilleur[3].numero if meilleur else None)
            tab_int = next((t.intitule for t in tableaux_doc.get(ann, []) if t.numero == tab_n), "")
            pid = passages_graphique.get((rap, g.numero))
            base.ajouter_appariement({
                "code_indicateur": code, "exercice": ex, "graphique_n": g.numero,
                "graphique_intitule": g.intitule, "tableau_n": tab_n, "tableau_intitule": tab_int,
                "doc_annuaire": ann, "passage_commentaire_id": pid,
                "score": meilleur[0] if meilleur else 0.0, "statut": statut,
                "valide_par": v.get("valide_par") if v else None,
                "date_validation": v.get("date_validation") if v else None})
            bilan[statut] += 1
            if pid:
                base.conn.execute("UPDATE passages SET code_indicateur=? WHERE passage_id=?", (code, pid))
            if statut != "rejete" and tab_n is not None and ann:
                base.conn.execute("UPDATE valeurs SET code_indicateur=? WHERE doc_id=? AND tableau_n=?",
                                  (code, ann, tab_n))
                base.conn.execute("UPDATE passages SET code_indicateur=? WHERE doc_id=? AND nature='tableau' "
                                  "AND texte LIKE ?", (code, ann, f"Tableau {tab_n} :%"))
            if meilleur:
                t = meilleur[3]
                lignes_xlsx.append({
                    "code_indicateur": code, "exercice": ex, "graphique_n": g.numero,
                    "graphique_intitule": g.intitule, "extrait_commentaire": _extrait(g.commentaire),
                    "tableau_n_propose": t.numero, "tableau_intitule": t.intitule, "page_tableau": t.page,
                    "extrait_tableau": _extrait("\n".join(x.ligne + " | " + x.colonne + " = " + x.valeur_texte
                                                          for x in t.triplets[:8]), 400),
                    "score": meilleur[0], "sim_intitules": meilleur[1], "part_valeurs_retrouvees": meilleur[2],
                    "autres_candidats": " ; ".join(f"T{c[3].numero} ({c[0]}) {c[3].intitule[:50]}"
                                                   for c in cands[1:])})
            else:
                lignes_xlsx.append({"code_indicateur": code, "exercice": ex, "graphique_n": g.numero,
                                    "graphique_intitule": g.intitule,
                                    "extrait_commentaire": _extrait(g.commentaire),
                                    "remarque": "aucun Annuaire de cet exercice dans le corpus"})
        pairing.ecrire_a_valider(lignes_xlsx, dossier / f"a_valider_{ex}.xlsx")
    base.commit()
    if verbeux:
        print(f"  Appariement : {dict(bilan)} (validations humaines lues : {len(validations)})")
    return dict(bilan)


def ecrire_inventaire(chemin: Path, fiches: dict, stats: dict) -> None:
    champs = ["doc_id", "fichier", "type", "exercice", "trimestre", "statut_diffusion", "nb_pages",
              "nb_tableaux", "nb_graphiques", "passages_texte", "passages_tableau",
              "passages_graphique", "nb_valeurs", "sha256", "titre"]
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";")
        w.writeheader()
        for did, fi in sorted(fiches.items(), key=lambda kv: (kv[1]["type"], kv[1]["exercice"],
                                                               kv[1]["trimestre"] or "")):
            s = stats[did]
            w.writerow({**{k: fi.get(k) for k in champs if k in fi},
                        "nb_tableaux": s["tableaux"], "nb_graphiques": s["graphiques"],
                        "passages_texte": s["passages_texte"], "passages_tableau": s["passages_tableau"],
                        "passages_graphique": s["passages_graphique"], "nb_valeurs": s["valeurs"]})


def corpus_manquant(fiches: dict) -> List[str]:
    """Trimestres manquants dans la série des notes de conjoncture, et couples
    Annuaire / Rapport incomplets."""
    out = []
    notes = {(f["exercice"], f["trimestre"]) for f in fiches.values() if f["type"] == "note_conjoncture"}
    if notes:
        debut, fin = min(notes), max(notes)
        a, t = debut[0], int(debut[1][1])
        while (a, f"T{t}") <= fin:
            if (a, f"T{t}") not in notes:
                out.append(f"note de conjoncture T{t} {a} absente")
            t += 1
            if t == 5:
                a, t = a + 1, 1
    ann = {f["exercice"] for f in fiches.values() if f["type"] == "annuaire"}
    rap = {f["exercice"] for f in fiches.values() if f["type"] == "rapport_analyse"}
    for ex in sorted(ann ^ rap):
        out.append(f"couple Annuaire/Rapport incomplet pour {ex}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Reconstruit la base depuis les PDF du corpus")
    ap.add_argument("--sans-dense", action="store_true", help="ne pas construire l'index dense")
    a = ap.parse_args()
    construire(dense=not a.sans_dense)
