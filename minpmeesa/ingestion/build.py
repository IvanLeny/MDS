"""Reconstruit TOUTE la base depuis data/corpus/ (une commande, section 3.1).

    python -m minpmeesa.ingestion.build

Étapes : registre -> extraction (texte, tableaux, graphiques) -> passages ->
appariement (propositions + décisions humaines conservées) -> variations ->
index BM25 et dense -> inventaire (Annexe I) et fichiers de validation.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from collections import Counter
from pathlib import Path

import pymupdf

from .. import config
from ..compute import variations as varmod
from ..store import bm25_index, db, encodeur as encmod, faiss_index
from . import chunk, extract, pairing, registry, tables


def _log(msg: str, verbeux: bool):
    if verbeux:
        print(msg, flush=True)


def extraire_document(chemin: Path, doc_id: str, type_doc: str, cfg: dict):
    """Extraction complète d'un PDF : (texte brut, tableaux, passages, graphiques, rejets, nb_pages)."""
    ing = cfg["ingestion"]
    brut = extract.lire(chemin)
    texte_brut = brut.texte_complet()
    doc = extract.fusionner_numerotation(extract.nettoyer(brut, ing["lignes_courantes_ratio"]))
    pdf = pymupdf.open(str(chemin))
    tabs, dernier = [], None
    for i, page in enumerate(pdf, start=1):
        if doc.pages[i - 1].sommaire:
            continue
        for t in tables.extraire_page(page, i, doc.pages[i - 1].lignes, dernier):
            tabs.append(t)
            dernier = (t.numero, t.intitule, i)
    n_pages = len(pdf)
    pdf.close()
    passages, graphiques, rejets = chunk.segmenter(doc, doc_id, type_doc, tabs, cfg)
    return texte_brut, tabs, passages, graphiques, rejets, n_pages


def construire(dossier_base: Path | None = None, verbeux: bool = True,
               encodeur_nom: str | None = None, corpus: Path | None = None) -> dict:
    t0 = time.time()
    cfg = config.charger()
    config.fixer_graine()
    base = dossier_base or config.chemin("base")
    corpus = corpus or config.chemin("corpus")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    con = db.connecter(base, creer=True)
    reg = registry.charger_registre(config.chemin("registre") if corpus == config.chemin("corpus")
                                    else corpus / "registre.yaml")
    rapport = {"documents": [], "avertissements": [], "rejets": Counter()}
    inventaire = []
    graph_par_doc, tab_par_doc = {}, {}

    pdfs = sorted(corpus.glob("*.pdf"))
    for chemin in pdfs:
        e = reg.get(chemin.name)
        if e is None:
            rapport["avertissements"].append(f"{chemin.name} : absent du registre, ignoré")
            continue
        _log(f"  {chemin.name}", verbeux)
        texte, tabs, passages, graphiques, rejets, n_pages = extraire_document(chemin, e.doc_id, e.type, cfg)
        detecte = registry.detecter(texte)
        ecarts = registry.confronter(e, detecte)
        if ecarts:
            rapport["avertissements"].append(f"{e.doc_id} : registre ≠ contenu ({'; '.join(ecarts)})"
                                             + (f" — {e.remarque}" if e.remarque else ""))
        db.inserer(con, "documents", {
            "doc_id": e.doc_id, "titre": e.titre, "type": e.type, "exercice": e.exercice,
            "trimestre": e.trimestre, "statut_diffusion": e.statut_diffusion, "fichier": e.fichier,
            "nb_pages": n_pages, "sha256": registry.sha256(chemin),
            "test_synthetique": int(e.test_synthetique)})
        # Valeurs (triplets de tous les tableaux)
        lignes_val = []
        for t in tabs:
            for tr in t.triplets:
                lignes_val.append({
                    "doc_id": e.doc_id, "page": t.page, "tableau_n": t.numero,
                    "tableau_intitule": t.intitule, "ligne": tr.ligne, "colonne": tr.colonne,
                    "annee_colonne": tr.annee_colonne, "sous_colonne": tr.sous_colonne,
                    "valeur_texte": tr.valeur_texte, "valeur_num": tables.valeur_num(tr.valeur_texte),
                    "unite": tr.unite, "code_indicateur": None})
        db.inserer_plusieurs(con, "valeurs", lignes_val)
        # Passages
        for p in passages:
            db.inserer(con, "passages", {
                "doc_id": p.doc_id, "page": p.page, "page_fin": p.page_fin, "chapitre": p.chapitre,
                "section": p.section, "nature": p.nature, "code_indicateur": None,
                "numero": p.numero, "texte": p.texte, "nb_tokens": p.nb_tokens})
        for _, motif in rejets:
            rapport["rejets"][motif.split(" (")[0]] += 1
        graph_par_doc[e.doc_id] = graphiques
        tab_par_doc[e.doc_id] = tabs
        nat = Counter(p.nature for p in passages)
        inventaire.append({
            "doc_id": e.doc_id, "fichier": e.fichier, "titre": e.titre, "type": e.type,
            "exercice": e.exercice, "trimestre": e.trimestre or "",
            "statut_diffusion": e.statut_diffusion, "statut_confirme": e.statut_confirme,
            "test_synthetique": e.test_synthetique, "pages": n_pages,
            "tableaux": len({(t.numero, t.page) if t.numero is None else t.numero for t in tabs}),
            "triplets": len(lignes_val), "graphiques": len(graphiques),
            "passages": len(passages), "passages_texte": nat["texte"],
            "passages_tableau": nat["tableau"], "passages_graphique": nat["graphique"],
            "passages_rejetes": len(rejets),
            "type_detecte": detecte["type"], "exercice_detecte": detecte["exercice"],
            "concordance_registre": "oui" if not ecarts else "non (voir remarque)",
            "remarque": e.remarque})
    con.commit()

    # ------------------------------------------------ appariement
    _log("  appariement", verbeux)
    docs = {r["doc_id"]: r for r in db.documents(con)}
    couples = {}
    for d in docs.values():
        if d["type"] in ("annuaire", "rapport_analyse") and not d["test_synthetique"]:
            couples.setdefault(d["exercice"], {})[d["type"]] = d["doc_id"]
    par_ex: dict[int, list[pairing.Ligne]] = {}
    dossier_app = config.chemin("appariement")
    for ex, c in sorted(couples.items()):
        if "annuaire" not in c or "rapport_analyse" not in c:
            rapport["avertissements"].append(f"exercice {ex} : couple annuaire/rapport incomplet")
            continue
        rap, ann = c["rapport_analyse"], c["annuaire"]
        coms = {r["numero"]: r["texte"] for r in con.execute(
            "SELECT numero, texte FROM passages WHERE doc_id=? AND nature='texte' AND numero IS NOT NULL "
            "ORDER BY passage_id", (rap,))}
        graphs = [{"numero": g.numero, "titre": g.titre, "etiquettes": g.etiquettes,
                   "commentaire": coms.get(g.numero, "")}
                  for g in {g.numero: g for g in graph_par_doc[rap]}.values()]
        tabs = {}
        for t in tab_par_doc[ann]:
            if t.numero is None:
                continue
            d = tabs.setdefault(t.numero, {"intitule": t.intitule, "valeurs": set(), "extrait": []})
            for tr in t.triplets:
                v = tables.valeur_num(tr.valeur_texte)
                if v is not None:
                    d["valeurs"].add(round(v, 2))
            d["extrait"] += t.texte_linearise()
        for d in tabs.values():
            d["extrait"] = "\n".join(d["extrait"][:10])
        lignes = pairing.proposer(ex, graphs, tabs, rap, ann, cfg)
        pairing.fusionner_decisions(lignes, dossier_app / f"appariement_{ex}.csv")
        par_ex[ex] = lignes
    pairing.attribuer_codes(par_ex, cfg["appariement"]["seuil_code_stable"])
    for ex, lignes in par_ex.items():
        pairing.ecrire_csv(lignes, dossier_app / f"appariement_{ex}.csv")
        pairing.ecrire_xlsx_validation(lignes, dossier_app / f"a_valider_{ex}.xlsx")
        for l in lignes:
            com = con.execute("SELECT passage_id FROM passages WHERE doc_id=? AND nature='texte' "
                              "AND numero=? ORDER BY passage_id LIMIT 1",
                              (l.doc_rapport, l.graphique_n)).fetchone()
            db.inserer(con, "appariement", {
                "code_indicateur": l.code_indicateur, "exercice": ex, "graphique_n": l.graphique_n,
                "graphique_intitule": l.graphique_intitule, "tableau_n": l.tableau_n,
                "tableau_intitule": l.tableau_intitule, "doc_annuaire": l.doc_annuaire,
                "doc_rapport": l.doc_rapport, "passage_commentaire_id": com[0] if com else None,
                "score": l.score, "statut": l.statut, "valide_par": l.valide_par or None,
                "date_validation": l.date_validation or None})
            if l.statut == "rejete":
                continue
            # Rattachement du code aux passages (commentaire, graphique, tableau) et aux valeurs
            con.execute("UPDATE passages SET code_indicateur=? WHERE doc_id=? AND numero=? "
                        "AND nature IN ('texte','graphique')", (l.code_indicateur, l.doc_rapport, l.graphique_n))
            if l.tableau_n is not None:
                con.execute("UPDATE passages SET code_indicateur=? WHERE doc_id=? AND numero=? "
                            "AND nature='tableau' AND code_indicateur IS NULL",
                            (l.code_indicateur, l.doc_annuaire, l.tableau_n))
                con.execute("UPDATE valeurs SET code_indicateur=? WHERE doc_id=? AND tableau_n=? "
                            "AND code_indicateur IS NULL", (l.code_indicateur, l.doc_annuaire, l.tableau_n))
    con.commit()

    # ------------------------------------------------ variations
    n_var = varmod.calculer_tout(con, cfg["appariement"]["statuts_utilisables"],
                                 cfg["commentaire"]["decimales_pct"])
    _log(f"  variations : {n_var}", verbeux)

    # ------------------------------------------------ index
    _log("  index BM25 et dense", verbeux)
    rows = con.execute("SELECT passage_id, texte, chapitre, section FROM passages ORDER BY passage_id").fetchall()
    textes_index = [f"{r['section']}\n{r['texte']}" for r in rows]
    ids = [r["passage_id"] for r in rows]
    bm = bm25_index.IndexBM25.construire(list(zip(ids, textes_index)))
    bm.sauver(base)
    t_idx = time.time()
    enc = encmod.construire(cfg, textes_index, encodeur_nom)
    vect = enc.encoder_passages(textes_index)
    duree_index = time.time() - t_idx
    faiss_index.sauver(faiss_index.construire(ids, vect), base)
    if isinstance(enc, encmod.EncodeurLSA):
        enc.sauver(base / "encodeur_lsa.pkl")

    # ------------------------------------------------ inventaire et rapport
    with open(corpus / "inventaire.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(inventaire[0]), delimiter=";")
        w.writeheader()
        w.writerows(inventaire)
    manquants = []
    trims = {(d["exercice"], d["trimestre"]) for d in docs.values() if d["type"] == "note_conjoncture"}
    for ex in (2023, 2024):
        for q in ("T1", "T2", "T3", "T4"):
            if (ex, q) not in trims:
                manquants.append(f"note_conjoncture {q} {ex}")
    rapport.update({
        "base": str(base), "encodeur": enc.nom, "dimension": enc.dim,
        "duree_indexation_dense_s": round(duree_index, 2),
        "nb_documents": len(docs), "nb_passages": len(ids),
        "nb_valeurs": con.execute("SELECT COUNT(*) FROM valeurs").fetchone()[0],
        "nb_appariements": sum(len(v) for v in par_ex.values()),
        "appariements_par_statut": dict(Counter(l.statut for v in par_ex.values() for l in v)),
        "nb_variations": n_var, "notes_conjoncture_absentes_2023_2024": manquants,
        "rejets": dict(rapport["rejets"]), "duree_totale_s": round(time.time() - t0, 1),
        "config_hash": config.config_hash(),
    })
    (base / "build_rapport.json").write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")
    con.close()
    return rapport


def main():
    ap = argparse.ArgumentParser(description="Reconstruit la base depuis data/corpus/")
    ap.add_argument("--encodeur", default=None, help="nom du modèle d'embeddings (défaut : config.yaml)")
    ap.add_argument("--silencieux", action="store_true")
    a = ap.parse_args()
    r = construire(verbeux=not a.silencieux, encodeur_nom=a.encodeur)
    print(json.dumps({k: v for k, v in r.items() if k != "documents"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
