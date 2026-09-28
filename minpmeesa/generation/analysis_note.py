"""Service 3 : note d'analyse (BF9, section 3.5.1).

La note ASSEMBLE des commentaires déjà validés, dans l'ordre du plan du
document source (numéro de tableau dans l'Annuaire), sous des intertitres
(chapitre / section de l'Annuaire). Aucune reformulation, aucune valeur
nouvelle. Le modèle de langage ne peut rédiger que des phrases de transition
SANS chiffre ; elles passent par le contrôle littéral avec une liste de
valeurs autorisées vide (tout chiffre est donc retiré).

Si un commentaire n'est pas encore validé et que l'appelant le demande
explicitement (inclure_non_valides=True), il est inclus avec la mention
« commentaire généré, non validé » et la note porte la mention PROJET.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from .. import config
from ..guards.literal_check import controler
from . import prompts
from .commentary import Commentaire, commenter
from .llm import ClientLLM, LLMIndisponible


@dataclass
class Bloc:
    intertitre: str
    code: str
    intitule: str
    tableau_n: Optional[int]
    page_tableau: Optional[int]
    enonces: List[dict]
    valide: bool
    transition: str = ""
    abstention: Optional[str] = None


@dataclass
class NoteAnalyse:
    exercice: int
    titre: str
    perimetre: str
    mode: str
    blocs: List[Bloc] = field(default_factory=list)
    projet: bool = False
    avertissements: List[str] = field(default_factory=list)
    duree_s: float = 0.0
    prod_id: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


def indicateurs_du_chapitre(base, exercice: int, motif_chapitre: str) -> List[str]:
    """Codes des indicateurs dont le tableau apparié appartient au chapitre
    de l'Annuaire désigné (recherche dans l'intitulé du chapitre)."""
    rows = base.q(
        "SELECT a.code_indicateur, a.tableau_n, MIN(p.chapitre) chapitre FROM appariement a "
        "JOIN passages p ON p.doc_id = a.doc_annuaire AND p.nature = 'tableau' "
        "AND p.texte LIKE 'Tableau ' || a.tableau_n || ' :%' "
        "WHERE a.exercice = ? AND a.statut != 'rejete' GROUP BY a.code_indicateur ORDER BY a.tableau_n",
        (exercice,))
    return [r["code_indicateur"] for r in rows if re.search(motif_chapitre, r["chapitre"] or "", re.I)]


def _plan(base, exercice: int, codes: List[str]) -> List[dict]:
    """Ordre du plan : numéro de tableau dans l'Annuaire, puis numéro de graphique."""
    out = []
    for c in codes:
        a = base.q("SELECT * FROM appariement WHERE code_indicateur=? AND exercice=?", (c, exercice))
        if not a:
            continue
        a = dict(a[0])
        p = base.q("SELECT chapitre, section, page FROM passages WHERE doc_id=? AND nature='tableau' "
                   "AND texte LIKE ? ORDER BY page LIMIT 1",
                   (a["doc_annuaire"], f"Tableau {a['tableau_n']} :%")) if a.get("tableau_n") else []
        a["chapitre"] = p[0]["chapitre"] if p else "Autres indicateurs"
        a["section"] = p[0]["section"] if p else ""
        a["page_tableau"] = p[0]["page"] if p else None
        out.append(a)
    return sorted(out, key=lambda a: (a["tableau_n"] if a["tableau_n"] is not None else 10 ** 6, a["graphique_n"] or 0))


def _transition(llm: ClientLLM, avant: str, apres: str) -> str:
    """Phrase de transition sans chiffre (modèle de langage), contrôlée : toute
    valeur est écartée puisque la liste des valeurs autorisées est vide."""
    if not llm.actif:
        return ""
    try:
        rep = llm.generer(prompts.SYSTEME_TRANSITION,
                          [{"role": "user", "content": f"Section précédente : {avant}\nSection suivante : {apres}"}])
        t = json.loads(rep.texte).get("transition", "")
    except (LLMIndisponible, ValueError, AttributeError):
        return ""
    res = controler([{"type": "constat", "texte": t}], [])
    return res.enonces[0].texte if res.enonces else ""


def rediger_note_analyse(base, exercice: int, codes: List[str], llm: ClientLLM, perimetre: str = "",
                         inclure_non_valides: bool = False, journal: bool = True) -> NoteAnalyse:
    t0 = time.time()
    note = NoteAnalyse(exercice, f"Note d'analyse — exercice {exercice}", perimetre or "indicateurs choisis",
                       llm.nom)
    valides = {r["code_indicateur"]: r for r in base.commentaires_valides(exercice)}
    precedent = ""
    for a in _plan(base, exercice, codes):
        code = a["code_indicateur"]
        intertitre = a["chapitre"]
        if code in valides:
            enonces, valide, abst = json.loads(valides[code]["enonces_json"]), True, None
        elif inclure_non_valides:
            c: Commentaire = commenter(base, code, exercice, llm, journal=journal)
            enonces, valide, abst = c.enonces, False, c.abstention
            note.projet = True
        else:
            note.avertissements.append(f"{code} : commentaire non validé, non repris dans la note")
            continue
        bloc = Bloc(intertitre, code, a["graphique_intitule"] or code, a["tableau_n"], a["page_tableau"],
                    enonces, valide, abstention=abst)
        if precedent and precedent != intertitre:
            bloc.transition = _transition(llm, precedent, intertitre)
        precedent = intertitre
        note.blocs.append(bloc)
    if note.projet:
        note.avertissements.insert(0, "PROJET : certains commentaires ont été générés et ne sont pas encore "
                                      "validés par un cadre de la Cellule.")
    if not llm.actif:
        note.avertissements.append("Mode extractif (sans modèle de langage) : commentaires composés par "
                                   "gabarits, sans transition rédigée.")
    note.duree_s = round(time.time() - t0, 3)
    if journal:
        note.prod_id = base.journaliser(
            "note_analyse", {"exercice": exercice, "codes": codes, "perimetre": perimetre},
            note.to_dict(), sources=[{"code": b.code, "tableau_n": b.tableau_n, "page": b.page_tableau}
                                     for b in note.blocs],
            abstentions=[f"{b.code} : {b.abstention}" for b in note.blocs if b.abstention],
            modele=note.mode, config_hash=config.config_hash(), duree_s=note.duree_s)
    return note
