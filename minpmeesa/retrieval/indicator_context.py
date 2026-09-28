"""Contexte ciblé d'un indicateur, en trois rubriques (section 3.3.2).

  [VALEURS AUTORISÉES — exercice traité] : valeurs du tableau apparié dans
      l'Annuaire de l'exercice traité ;
  [VARIATIONS CALCULÉES — autorisées]    : variations calculées par le programme ;
  [MODÈLES DE RÉDACTION]                 : commentaires publiés des exercices
      STRICTEMENT antérieurs (filtre temporel BF6 dans la requête SQL).
Les deux premières rubriques forment la liste des valeurs autorisées du
contrôle de citation littérale ; la troisième n'y contribue jamais.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .. import config
from ..compute.variations import annee_de
from ..guards.literal_check import ValeurAutorisee
from ..ingestion.tables import NON_RATTACHEE


@dataclass
class Contexte:
    code: str
    exercice: int
    intitule: str
    appariement: Optional[dict]
    valeurs: List[dict] = field(default_factory=list)
    variations: List[dict] = field(default_factory=list)
    modeles: List[dict] = field(default_factory=list)
    autorisees: List[ValeurAutorisee] = field(default_factory=list)
    motif_insuffisance: str = ""

    @property
    def suffisant(self) -> bool:
        return not self.motif_insuffisance

    def lignes_valeurs(self) -> List[str]:
        out = []
        for v in self.valeurs:
            lib = v["ligne"] if v["ligne"] != NON_RATTACHEE else "valeur du tableau"
            col = f" | {v['colonne']}" if v["colonne"] else ""
            out.append(f"{lib}{col} = {v['valeur_texte']}")
        return out

    def lignes_variations(self) -> List[str]:
        out = []
        for r in self.variations:
            pct = r["ligne"].endswith("(%)")
            s = f"{r['ligne']} : {r['exercice']} par rapport à {r['exercice_ref']} : écart de {r['var_abs_texte']}"
            s += " point(s) de pourcentage" if pct else ""
            if r["var_rel_texte"] is not None and not pct:
                s += f", soit {r['var_rel_texte']} %"
            s += f" (de {r['valeur_ref_texte']} en {r['exercice_ref']} à {r['valeur_texte']} en {r['exercice']})"
            out.append(s)
        return out


def _priorite(v, exercice: int) -> tuple:
    a = annee_de(v["ligne"], v["colonne"])
    if v["ligne"] == NON_RATTACHEE:
        return (4, 0)
    if a is None or a == exercice:
        return (0, 0)
    if a == exercice - 1:
        return (1, 0)
    return (2, exercice - a)


def _est_total(ligne: str) -> bool:
    return bool(re.search(r"\b(total|ensemble|cameroun|national)\b", ligne, re.I))


def contexte_indicateur(base, code: str, exercice: int, statuts=("valide", "candidat")) -> Contexte:
    marks = ",".join("?" * len(statuts))
    app = base.q(f"SELECT * FROM appariement WHERE code_indicateur=? AND exercice=? AND statut IN ({marks})",
                 (code, exercice, *statuts))
    app = dict(app[0]) if app else None
    intitule = (app or {}).get("graphique_intitule") or code
    ctx = Contexte(code, exercice, intitule, app)
    if not app or app.get("tableau_n") is None or not app.get("doc_annuaire"):
        ctx.motif_insuffisance = "aucun tableau apparié pour cet exercice"
        return ctx
    # Garde-fou temporel : le tableau vient de l'Annuaire de l'exercice traité.
    doc = base.document(app["doc_annuaire"])
    if doc is None or doc["exercice"] != exercice:
        ctx.motif_insuffisance = "l'Annuaire apparié n'est pas celui de l'exercice traité"
        return ctx
    rows = [dict(r) for r in base.valeurs_tableau(app["doc_annuaire"], app["tableau_n"])]
    if not rows:
        ctx.motif_insuffisance = "aucune valeur lue dans le tableau apparié"
        return ctx

    # Rubrique 2 : variations de l'exercice (N vs N-1 pour toutes les séries,
    # N vs toutes les années antérieures pour les totaux, N vs N-2 sinon).
    par_id = {r["valeur_id"]: r for r in rows}
    variations = []
    for v in base.q("SELECT * FROM variations WHERE code_indicateur=? AND exercice=? ORDER BY ligne, exercice_ref DESC",
                    (code, exercice)):
        v = dict(v)
        garde = v["exercice_ref"] == exercice - 1 or _est_total(v["ligne"]) or v["exercice_ref"] == exercice - 2
        if garde and v["valeur_id"] in par_id and v["valeur_ref_id"] in par_id:
            v["valeur_texte"] = par_id[v["valeur_id"]]["valeur_texte"]
            v["valeur_ref_texte"] = par_id[v["valeur_ref_id"]]["valeur_texte"]
            variations.append(v)
    variations.sort(key=lambda v: (not _est_total(v["ligne"]), v["exercice_ref"] != exercice - 1, v["ligne"]))
    ctx.variations = variations[: int(config.get("commentaire.variations_max_contexte", 40))]

    # Rubrique 1 : valeurs du tableau (priorité à l'exercice traité), plus les
    # valeurs sources des variations retenues.
    nmax = int(config.get("commentaire.valeurs_max_contexte", 60))
    requis = {v["valeur_id"] for v in ctx.variations} | {v["valeur_ref_id"] for v in ctx.variations}
    tri = sorted(rows, key=lambda r: (r["valeur_id"] not in requis, _priorite(r, exercice), r["valeur_id"]))
    ctx.valeurs = sorted(tri[:max(nmax, len(requis))], key=lambda r: r["valeur_id"])

    # Rubrique 3 : modèles de rédaction (exercices strictement antérieurs).
    for m in base.commentaires_anterieurs(code, exercice)[: int(config.get("commentaire.modeles_redaction_max", 3))]:
        ctx.modeles.append({"exercice": m["exercice"], "texte": m["texte"], "passage_id": m["passage_id"],
                            "doc_id": m["doc_id"], "page": m["page"]})

    # Valeurs autorisées = rubriques 1 et 2 uniquement.
    for r in ctx.valeurs:
        ctx.autorisees.append(ValeurAutorisee(r["valeur_texte"], {
            "genre": "valeur", "valeur_id": r["valeur_id"], "doc_id": r["doc_id"], "page": r["page"],
            "tableau_n": r["tableau_n"], "ligne": r["ligne"], "colonne": r["colonne"]}))
    for v in ctx.variations:
        src = {"genre": "variation", "valeur_id": v["valeur_id"], "valeur_ref_id": v["valeur_ref_id"],
               "doc_id": app["doc_annuaire"], "page": par_id[v["valeur_id"]]["page"],
               "tableau_n": app["tableau_n"], "ligne": v["ligne"],
               "colonne": f"{v['exercice']} / {v['exercice_ref']}"}
        ctx.autorisees.append(ValeurAutorisee(v["var_abs_texte"], src))
        if v["var_rel_texte"] is not None and not v["ligne"].endswith("(%)"):
            ctx.autorisees.append(ValeurAutorisee(v["var_rel_texte"], src))
    return ctx
