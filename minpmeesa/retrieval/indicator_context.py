"""Contexte ciblé d'un indicateur (section 3.3, trois rubriques balisées).

[VALEURS AUTORISÉES — exercice traité]      valeurs du tableau apparié de l'Annuaire de l'exercice
[VARIATIONS CALCULÉES — autorisées]         variations calculées par le programme (3.3.3)
[MODÈLES DE RÉDACTION — exercices antérieurs, NE PAS reprendre leurs chiffres]
                                            commentaires publiés des exercices ANTÉRIEURS

Filtre temporel (BF6) dans la requête SQL : les modèles de rédaction ne
proviennent que de documents d'exercice < exercice traité ; les valeurs, que du
tableau de l'Annuaire de l'exercice traité (aucune source postérieure).
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from ..guards.literal_check import nombres

RUBRIQUE_VALEURS = "[VALEURS AUTORISÉES — exercice traité]"
RUBRIQUE_VARIATIONS = "[VARIATIONS CALCULÉES — autorisées]"
RUBRIQUE_MODELES = "[MODÈLES DE RÉDACTION — exercices antérieurs, NE PAS reprendre leurs chiffres]"


@dataclass
class Contexte:
    code: str
    exercice: int
    indicateur: str = ""
    tableau_n: int | None = None
    tableau_intitule: str = ""
    doc_annuaire: str = ""
    statut_appariement: str = ""
    valeurs: list[dict] = field(default_factory=list)
    variations: list[dict] = field(default_factory=list)
    modeles: list[dict] = field(default_factory=list)
    abstention: str | None = None

    @property
    def provisoire(self) -> bool:
        return self.statut_appariement != "valide"

    def autorisees(self) -> list[dict]:
        """Valeurs admises par le contrôle littéral, chacune avec sa source."""
        out = []
        for v in self.valeurs:
            src = {"nature": "valeur", "valeur_id": v["valeur_id"], "doc_id": v["doc_id"],
                   "page": v["page"], "tableau_n": v["tableau_n"], "ligne": v["ligne"], "colonne": v["colonne"]}
            out.append({"texte": v["valeur_texte"], "source": src})
            # nombres des libellés (« 30-40 ans », « 2024 (e) ») : texte sourcé du tableau
            for n in nombres(f"{v['ligne']} ; {v['colonne']}"):
                out.append({"texte": n, "source": {**src, "nature": "libellé"}})
        for d in self.variations:
            src = {"nature": "variation", "valeur_id": d["valeur_id"], "valeur_ref_id": d["valeur_ref_id"],
                   "exercice_ref": d["exercice_ref"], "ligne": d["ligne"]}
            out.append({"texte": d["var_abs_texte"], "source": {**src, "grandeur": "var_abs"}})
            if d["var_rel_texte"]:
                out.append({"texte": d["var_rel_texte"], "source": {**src, "grandeur": "var_rel_pct"}})
        return out

    def textes_modeles(self) -> list[str]:
        return [m["texte"] for m in self.modeles]

    def rendu(self, max_valeurs: int = 120, max_variations: int = 40) -> str:
        """Texte du contexte transmis au modèle de langage."""
        lignes = [f"Indicateur : {self.indicateur} (exercice {self.exercice})",
                  f"Tableau {self.tableau_n} de l'Annuaire {self.exercice} : {self.tableau_intitule}", "",
                  RUBRIQUE_VALEURS]
        for v in _prioriser_valeurs(self.valeurs, self.exercice)[:max_valeurs]:
            u = f" {v['unite']}" if v["unite"] and v["unite"] != "%" else (" %" if v["unite"] == "%" else "")
            lignes.append(f"- {v['ligne']} | {v['colonne']} = {v['valeur_texte']}{u}")
        lignes += ["", RUBRIQUE_VARIATIONS]
        for d in _prioriser_variations(self.variations, self.exercice)[:max_variations]:
            pts = "points" if d["unite"] == "%" else (d["unite"] or "")
            rel = f" ; variation relative {d['var_rel_texte']} %" if d["var_rel_texte"] else ""
            sc = f" ({d['sous_colonne']})" if d["sous_colonne"] else ""
            lignes.append(f"- {d['ligne']}{sc}, {self.exercice} par rapport à {d['exercice_ref']} : "
                          f"écart {d['var_abs_texte']} {pts}{rel}".replace("  ", " "))
        lignes += ["", RUBRIQUE_MODELES]
        for m in self.modeles:
            lignes.append(f"- (Rapport d'analyse {m['exercice']}, p. {m['page']}) {m['texte'][:1200]}")
        return "\n".join(lignes)


def _prioriser_valeurs(vals: list[dict], ex: int) -> list[dict]:
    def cle(v):
        a = v["annee_colonne"]
        rang = 0 if a == ex else 1 if a == ex - 1 else 2 if a is None else 3
        return (rang, 0 if re.match(r"total", v["ligne"], re.I) else 1, v["valeur_id"])
    return sorted(vals, key=cle)


def _prioriser_variations(vs: list[dict], ex: int) -> list[dict]:
    return sorted(vs, key=lambda d: (0 if d["exercice_ref"] == ex - 1 else 1, -d["exercice_ref"],
                                     0 if re.match(r"total", d["ligne"], re.I) else 1))


def construire(con: sqlite3.Connection, code: str, exercice: int, statuts: list[str],
               nb_modeles: int = 3, moteur=None) -> Contexte:
    ctx = Contexte(code, exercice)
    app = con.execute(
        f"SELECT * FROM appariement WHERE code_indicateur=? AND exercice=? "
        f"AND statut IN ({','.join('?' * len(statuts))})", (code, exercice, *statuts)).fetchone()
    if not app or app["tableau_n"] is None:
        ctx.abstention = "aucun tableau apparié (et utilisable) pour cet indicateur et cet exercice"
        return ctx
    ctx.indicateur = app["graphique_intitule"]
    ctx.tableau_n, ctx.tableau_intitule = app["tableau_n"], app["tableau_intitule"]
    ctx.doc_annuaire, ctx.statut_appariement = app["doc_annuaire"], app["statut"]
    # Valeurs : tableau de l'Annuaire DE L'EXERCICE TRAITÉ uniquement.
    ctx.valeurs = [dict(r) for r in con.execute(
        "SELECT v.* FROM valeurs v JOIN documents d USING(doc_id) "
        "WHERE v.doc_id=? AND v.tableau_n=? AND d.exercice=? AND d.statut_diffusion='publie' "
        "ORDER BY v.valeur_id", (app["doc_annuaire"], app["tableau_n"], exercice))]
    ctx.variations = [dict(r) for r in con.execute(
        "SELECT * FROM variations WHERE code_indicateur=? AND exercice=?", (code, exercice))]
    # Modèles de rédaction : exercices STRICTEMENT antérieurs (BF6), dans la requête.
    ctx.modeles = [dict(r) for r in con.execute(
        "SELECT p.passage_id, p.doc_id, p.page, p.texte, d.exercice FROM passages p "
        "JOIN documents d USING(doc_id) WHERE p.code_indicateur=? AND p.nature='texte' "
        "AND d.type='rapport_analyse' AND d.exercice < ? AND d.statut_diffusion='publie' "
        "ORDER BY d.exercice DESC, p.passage_id LIMIT ?", (code, exercice, nb_modeles))]
    if not ctx.modeles and moteur is not None:
        # Repli : commentaires antérieurs les plus proches de l'intitulé (même filtre temporel).
        autorises = moteur.autorises("publie", exercice_max=exercice - 1, types=("rapport_analyse",))
        for r in moteur.rechercher(ctx.indicateur, autorises, mode="hybride", k=nb_modeles):
            p = con.execute("SELECT p.passage_id, p.doc_id, p.page, p.texte, d.exercice FROM passages p "
                            "JOIN documents d USING(doc_id) WHERE p.passage_id=? AND p.nature='texte'",
                            (r.passage_id,)).fetchone()
            if p:
                ctx.modeles.append(dict(p))
    if not any(v["valeur_num"] is not None for v in ctx.valeurs):
        ctx.abstention = "aucune valeur exploitable dans le tableau apparié"
    return ctx
