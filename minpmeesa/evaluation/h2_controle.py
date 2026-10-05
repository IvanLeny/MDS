"""H2 : contrôle de citation littérale ; H1 (ancrage) ; analyse des commentaires publiés.

H2 compare, sur la MÊME sortie du modèle de langage :
  - « ancrage simple »                (aucun contrôle) ;
  - « ancrage + citation littérale »  (règles R0 à R3).
Mesures : valeurs non soutenues, exactitude (Exa), couverture (Couv, Couv_ind),
taux de faux rejets (TFR, automatique + échantillon pour relecture manuelle),
typologie des valeurs écartées.

Sans modèle de langage disponible, H1-ancrage et H2 sont déclarées « non
mesuré » : le mode extractif ne produit par construction que des valeurs du
contexte, il ne peut pas servir de mesure.
"""
from __future__ import annotations

import csv
import random
import re
from pathlib import Path

import pymupdf

from .. import config
from ..generation import commentary as cm
from ..guards import literal_check as lc
from ..guards.normalize import formes
from ..retrieval import indicator_context as ic
from . import metrics as M
from . import stats


def indicateurs(con, exercice: int, statuts: list[str]) -> list[dict]:
    q = (f"SELECT a.*, p.texte AS commentaire_publie FROM appariement a LEFT JOIN passages p "
         f"ON p.passage_id = a.passage_commentaire_id WHERE a.exercice=? AND a.tableau_n IS NOT NULL "
         f"AND a.statut IN ({','.join('?' * len(statuts))}) ORDER BY a.graphique_n")
    return [dict(r) for r in con.execute(q, (exercice, *statuts))]


def statuts_evaluation(con, exercice: int) -> tuple[list[str], bool]:
    """Lignes validées ; à défaut (repli prévu par config), candidats => PROVISOIRE."""
    cfg = config.charger()["appariement"]
    st = cfg["statuts_evaluation"]
    if indicateurs(con, exercice, st):
        return st, False
    if cfg["repli_evaluation_candidats"]:
        return ["valide", "candidat"], True
    return st, False


# ------------------------------------------------------------ TFR automatique
def _pages_sources(con, ctx: ic.Contexte) -> str:
    pages = {(v["doc_id"], v["page"]) for v in ctx.valeurs}
    textes = []
    for doc_id, page in pages:
        f = con.execute("SELECT fichier FROM documents WHERE doc_id=?", (doc_id,)).fetchone()[0]
        d = pymupdf.open(str(config.chemin("corpus") / f))
        textes.append(d[page - 1].get_text())
    return "\n".join(textes)


def faux_rejet(valeur: str, texte_sources: str) -> bool:
    """La valeur écartée figurait-elle dans les sources sous une autre écriture ?"""
    cible = formes(valeur)
    for o in lc.NOMBRE.finditer(texte_sources):
        if formes(o.group("n")) & cible:
            return True
    # écriture éclatée par l'extraction (« 1181 » vs « 1 181 », retours à la ligne)
    compact = re.sub(r"[\s  ]", "", texte_sources)
    v = re.sub(r"[\s  ]", "", valeur)
    return len(v) >= 4 and v in compact


def _anterieures(con, ctx: ic.Contexte) -> list[str]:
    """Chiffres des modèles de rédaction et des éditions antérieures (typologie)."""
    out = [n for m in ctx.modeles for n in lc.nombres(m["texte"])]
    for r in con.execute("SELECT v.valeur_texte FROM valeurs v JOIN appariement a ON a.doc_annuaire=v.doc_id "
                         "AND a.tableau_n=v.tableau_n WHERE a.code_indicateur=? AND a.exercice<?",
                         (ctx.code, ctx.exercice)):
        out.append(r[0])
    return out


def evaluer_h2(con, client, exercice: int, sortie: Path | None, graine: int = 42,
               n_echantillon: int = 30) -> dict:
    if client is None:
        return {"statut": "non mesuré", "raison": "aucun modèle de langage disponible (Ollama/llama-cpp) : "
                "H2 compare des sorties de modèle ; le mode extractif n'en produit pas."}
    statuts, provisoire = statuts_evaluation(con, exercice)
    lignes, ecarts = [], []
    cfg = config.charger()
    for a in indicateurs(con, exercice, statuts):
        brut = cm.commenter(con, a["code_indicateur"], exercice, client, controle=False, journaliser=True, repli=False)
        if brut.get("abstention"):
            lignes.append({"code": a["code_indicateur"], "abstention_sans": 1, "abstention_avec": 1,
                           "citees": 0, "non_soutenues_sans": 0, "retenues_avec": 0, "non_soutenues_avec": 0})
            continue
        ctx = ic.construire(con, a["code_indicateur"], exercice, statuts, cfg["commentaire"]["nb_modeles_redaction"])
        enonces = brut["enonces_avant_controle"]
        aut = ctx.autorisees()
        idx = lc.index_autorise(aut)
        citees = [o for e in enonces for o in lc.nombres(e["texte"])]
        ns_sans = [o for o in citees if lc.trouver(o, idx) is None]
        c = lc.controler(enonces, aut, ctx.textes_modeles())
        ns_avec = [o for e in c.enonces for o in lc.nombres(e["texte"]) if lc.trouver(o, idx) is None]
        src = _pages_sources(con, ctx)
        ant = _anterieures(con, ctx)
        for e in c.ecartees:
            ecarts.append({"code": a["code_indicateur"], "valeur": e["valeur"], "type_enonce": e["type"],
                           "action": e["action"], "texte_original": e["texte_original"],
                           "faux_rejet_auto": int(faux_rejet(e["valeur"], src)),
                           "typologie": lc.classer_ecart(e["valeur"], [x["texte"] for x in aut], ant)})
        lignes.append({"code": a["code_indicateur"], "abstention_sans": 0,
                       "abstention_avec": int(not c.enonces), "citees": len(citees),
                       "non_soutenues_sans": len(ns_sans), "retenues_avec": c.n_retenues,
                       "non_soutenues_avec": len(ns_avec)})
    n_cit = sum(l["citees"] for l in lignes)
    res = {
        "statut": "mesuré", "provisoire": provisoire, "modele": client.nom, "n_indicateurs": len(lignes),
        "ancrage_simple": {"valeurs_citees": n_cit,
                           "valeurs_non_soutenues": sum(l["non_soutenues_sans"] for l in lignes),
                           "exactitude": M.taux(n_cit - sum(l["non_soutenues_sans"] for l in lignes), n_cit),
                           "couv_ind": M.taux(sum(1 - l["abstention_sans"] for l in lignes), len(lignes))},
        "ancrage_citation_litterale": {
            "valeurs_retenues": sum(l["retenues_avec"] for l in lignes),
            "valeurs_non_soutenues": sum(l["non_soutenues_avec"] for l in lignes),
            "exactitude": M.taux(sum(l["retenues_avec"] for l in lignes) - sum(l["non_soutenues_avec"] for l in lignes),
                                 sum(l["retenues_avec"] for l in lignes)),
            "couv": M.taux(sum(l["retenues_avec"] for l in lignes), n_cit),
            "couv_ind": M.taux(sum(1 - l["abstention_avec"] for l in lignes), len(lignes))},
        "valeurs_ecartees": len(ecarts),
        "tfr_automatique": M.taux(sum(e["faux_rejet_auto"] for e in ecarts), len(ecarts)),
        "typologie": {t: sum(1 for e in ecarts if e["typologie"] == t)
                      for t in ("arrondi", "calcul", "chiffre d'un autre exercice", "invention")},
    }
    if sortie:
        _csv(sortie / "h2_par_indicateur.csv", lignes)
        _csv(sortie / "h2_valeurs_ecartees.csv", ecarts)
        ech = random.Random(graine).sample(ecarts, min(n_echantillon, len(ecarts)))
        _csv(sortie / "h2_echantillon_relecture.csv",
             [{**e, "verdict_manuel (vrai_rejet|faux_rejet)": ""} for e in ech])
    return res


def evaluer_h1_ancrage(con, client, encodeur, exercice: int, sortie: Path | None) -> dict:
    """ROUGE-L et similarité sémantique, avec et sans appui documentaire, contre
    le commentaire publié ; Wilcoxon apparié (unilatéral : avec > sans)."""
    if client is None:
        return {"statut": "non mesuré", "raison": "aucun modèle de langage disponible : la comparaison "
                "avec/sans appui porte sur des sorties de modèle."}
    statuts, provisoire = statuts_evaluation(con, exercice)
    lignes = []
    for a in indicateurs(con, exercice, statuts):
        ref = a.get("commentaire_publie")
        if not ref:
            continue
        avec = cm.commenter(con, a["code_indicateur"], exercice, client, avec_appui=True, repli=False)
        sans = cm.commenter(con, a["code_indicateur"], exercice, client, avec_appui=False, repli=False)
        ta, ts = cm.texte(avec), cm.texte(sans)
        vr = encodeur.encoder_requete(ref)
        lignes.append({"code": a["code_indicateur"],
                       "rouge_l_avec": round(M.rouge_l(ta, ref), 4), "rouge_l_sans": round(M.rouge_l(ts, ref), 4),
                       "sim_avec": round(M.cosinus(encodeur.encoder_requete(ta), vr), 4) if ta else 0.0,
                       "sim_sans": round(M.cosinus(encodeur.encoder_requete(ts), vr), 4) if ts else 0.0})
    if sortie:
        _csv(sortie / "h1_ancrage_par_indicateur.csv", lignes)
    return {"statut": "mesuré", "provisoire": provisoire, "modele": client.nom, "encodeur": encodeur.nom,
            "n": len(lignes),
            "rouge_l": stats.wilcoxon([l["rouge_l_avec"] for l in lignes], [l["rouge_l_sans"] for l in lignes], "greater"),
            "similarite": stats.wilcoxon([l["sim_avec"] for l in lignes], [l["sim_sans"] for l in lignes], "greater")}


def analyser_commentaires_publies(con, exercice: int, sortie: Path | None) -> dict:
    """Analyse complémentaire (ce n'est PAS H2) : le contrôle littéral appliqué aux
    commentaires PUBLIÉS par le ministère, contre les valeurs du tableau apparié
    et les variations calculées. Mesure réelle, sans modèle de langage."""
    statuts, provisoire = statuts_evaluation(con, exercice)
    cfg = config.charger()
    lignes, ecarts = [], []
    for a in indicateurs(con, exercice, statuts):
        if not a.get("commentaire_publie"):
            continue
        ctx = ic.construire(con, a["code_indicateur"], exercice, statuts, cfg["commentaire"]["nb_modeles_redaction"])
        phrases = [p for p in re.split(r"(?<=[.;])\s+", a["commentaire_publie"]) if lc.nombres(p)]
        aut = ctx.autorisees()
        idx = lc.index_autorise(aut)
        src = _pages_sources(con, ctx)
        ant = _anterieures(con, ctx)
        n, ok = 0, 0
        for ph in phrases:
            for o in lc.nombres(ph):
                n += 1
                if lc.trouver(o, idx) is not None:
                    ok += 1
                else:
                    ecarts.append({"code": a["code_indicateur"], "valeur": o, "phrase": ph[:300],
                                   "present_ailleurs_sur_la_page_du_tableau": int(faux_rejet(o, src)),
                                   "typologie": lc.classer_ecart(o, [x["texte"] for x in aut], ant)})
        lignes.append({"code": a["code_indicateur"], "tableau_n": a["tableau_n"], "valeurs_citees": n,
                       "valeurs_retrouvees": ok, "part_retrouvee": round(ok / n, 4) if n else None})
    if sortie:
        _csv(sortie / "analyse_commentaires_publies.csv", lignes)
        _csv(sortie / "analyse_commentaires_publies_ecarts.csv", ecarts)
    n = sum(l["valeurs_citees"] for l in lignes)
    ok = sum(l["valeurs_retrouvees"] for l in lignes)
    return {"statut": "mesuré", "provisoire": provisoire, "exercice": exercice, "n_indicateurs": len(lignes),
            "valeurs_citees": n, "valeurs_retrouvees": ok, "part_retrouvee": round(ok / n, 4) if n else None,
            "typologie_non_retrouvees": {t: sum(1 for e in ecarts if e["typologie"] == t)
                                         for t in ("arrondi", "calcul", "chiffre d'un autre exercice", "invention")}}


def _csv(chemin: Path, lignes: list[dict]):
    if not lignes:
        return
    chemin.parent.mkdir(parents=True, exist_ok=True)
    champs = list(dict.fromkeys(k for l in lignes for k in l))
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";")
        w.writeheader()
        w.writerows(lignes)


def comparer_gabarits(con, client, encodeur, exercice: int, sortie: Path | None) -> dict:
    """Référence « gabarits » (H1) : les mêmes commentaires rédigés en mode --llm none
    (gabarits déterministes) et par le LLM ancré, comparés au commentaire PUBLIÉ du
    rapport d'analyse (ROUGE-L, similarité sémantique avec le même encodeur, couverture).
    Le côté gabarits se mesure sans modèle de langage ; le côté LLM exige un modèle."""
    statuts, provisoire = statuts_evaluation(con, exercice)
    lignes = []
    for a in indicateurs(con, exercice, statuts):
        ref = a.get("commentaire_publie")
        if not ref:
            continue
        vr = encodeur.encoder_requete(ref)
        ligne = {"code": a["code_indicateur"]}
        confs = [("gabarits", None)] + ([("llm_ancre", client)] if client is not None else [])
        for nom, cl in confs:
            r = cm.commenter(con, a["code_indicateur"], exercice, cl, repli=False)
            t = cm.texte(r)
            ligne[f"rouge_l_{nom}"] = round(M.rouge_l(t, ref), 4) if t else 0.0
            ligne[f"sim_{nom}"] = round(M.cosinus(encodeur.encoder_requete(t), vr), 4) if t else 0.0
            ligne[f"commente_{nom}"] = int(not r.get("abstention"))
            ligne[f"valeurs_retenues_{nom}"] = sum(len(lc.nombres(e["texte"])) for e in r.get("enonces", []))
            ligne[f"mots_{nom}"] = len(t.split())
        lignes.append(ligne)
    if sortie:
        _csv(sortie / "h1_reference_gabarits_par_indicateur.csv", lignes)
    n = len(lignes)

    def moy(k):
        v = [l[k] for l in lignes if k in l]
        return round(sum(v) / len(v), 4) if v else None

    res = {"statut_gabarits": "mesuré" if n else "non mesuré", "provisoire": provisoire, "n": n,
           "encodeur": encodeur.nom, "reference": "commentaires publiés du rapport d'analyse",
           "gabarits": {"rouge_l": moy("rouge_l_gabarits"), "similarite": moy("sim_gabarits"),
                        "couv_ind": moy("commente_gabarits"), "valeurs_retenues_moy": moy("valeurs_retenues_gabarits"),
                        "mots_moy": moy("mots_gabarits")}}
    if client is None:
        res["llm_ancre"] = {"statut": "non mesuré", "raison": "aucun modèle de langage disponible"}
    else:
        res["llm_ancre"] = {"statut": "mesuré", "modele": client.nom, "rouge_l": moy("rouge_l_llm_ancre"),
                            "similarite": moy("sim_llm_ancre"), "couv_ind": moy("commente_llm_ancre"),
                            "valeurs_retenues_moy": moy("valeurs_retenues_llm_ancre"),
                            "mots_moy": moy("mots_llm_ancre")}
        res["wilcoxon_rouge_l_llm_vs_gabarits"] = stats.wilcoxon(
            [l["rouge_l_llm_ancre"] for l in lignes], [l["rouge_l_gabarits"] for l in lignes])
        res["wilcoxon_similarite_llm_vs_gabarits"] = stats.wilcoxon(
            [l["sim_llm_ancre"] for l in lignes], [l["sim_gabarits"] for l in lignes])
    return res
