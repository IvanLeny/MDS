"""Service 3 : note d'analyse (BF9, section 3.5.1).

La note ASSEMBLE des commentaires déjà validés, dans l'ordre du plan de
l'Annuaire (chapitre, section, numéro de tableau), sous des intertitres.
Aucune reformulation, aucune valeur nouvelle. Le modèle de langage ne peut
écrire que des phrases de transition SANS chiffre, elles-mêmes contrôlées.

Sélection : un ensemble d'indicateurs, un chapitre de l'Annuaire, ou des
documents (tous les tableaux commentables qu'ils contiennent).
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime

from .. import config
from ..guards import literal_check
from ..store import db
from . import commentary as cm
from . import prompts


def valider_production(con, prod_id: int, par: str, statut: str = "valide") -> None:
    """Validation humaine d'un commentaire (préalable à son assemblage)."""
    con.execute("UPDATE productions SET statut_validation=?, valide_par=? WHERE prod_id=?", (statut, par, prod_id))
    con.commit()


def commentaire_valide(con, code: str, exercice: int) -> dict | None:
    """Dernier commentaire VALIDÉ de l'indicateur pour l'exercice."""
    for r in con.execute("SELECT prod_id, entree, sortie FROM productions WHERE type='commentaire' "
                         "AND statut_validation='valide' ORDER BY prod_id DESC"):
        e = json.loads(r["entree"])
        if e.get("code_indicateur") == code and e.get("exercice") == exercice:
            s = json.loads(r["sortie"])
            s["prod_id"], s["valide"] = r["prod_id"], True
            return s
    return None


def tableaux_du_chapitre(con, exercice: int, motif_chapitre: str) -> list[tuple[int, str, str]]:
    """(tableau_n, chapitre, section) des tableaux d'un chapitre de l'Annuaire, dans l'ordre."""
    ann = con.execute("SELECT doc_id FROM documents WHERE type='annuaire' AND exercice=?", (exercice,)).fetchone()
    if not ann:
        return []
    vus, out = set(), []
    for r in con.execute("SELECT numero, chapitre, section FROM passages WHERE doc_id=? AND nature='tableau' "
                         "AND numero IS NOT NULL ORDER BY page, passage_id", (ann[0],)):
        if re.search(motif_chapitre, r["chapitre"], re.I) and r["numero"] not in vus:
            vus.add(r["numero"])
            out.append((r["numero"], r["chapitre"], r["section"]))
    return out


def code_pour_tableau(con, exercice: int, tableau_n: int) -> str:
    """Code de l'indicateur apparié à ce tableau, sinon « tableau-N »."""
    r = con.execute("SELECT code_indicateur FROM appariement WHERE exercice=? AND tableau_n=? "
                    "AND statut IN ('valide','candidat') ORDER BY statut='valide' DESC, score DESC LIMIT 1",
                    (exercice, tableau_n)).fetchone()
    return r[0] if r else f"tableau-{tableau_n}"


def rediger(con, exercice: int, codes: list[str] | None = None, chapitre: str | None = None,
            documents: list[str] | None = None, client=None, titre: str | None = None,
            journaliser: bool = True, moteur=None) -> dict:
    t0 = time.time()
    cfg = config.charger()
    accepter = cfg["note_analyse"]["accepter_non_valides"]
    # 1) plan : liste ordonnée (code, chapitre, section, tableau_n)
    plan = []
    if chapitre:
        for n, ch, se in tableaux_du_chapitre(con, exercice, chapitre):
            plan.append((code_pour_tableau(con, exercice, n), ch, se, n))
    for doc in documents or []:
        for r in con.execute("SELECT DISTINCT numero, chapitre, section FROM passages WHERE doc_id=? "
                             "AND nature='tableau' AND numero IS NOT NULL ORDER BY page", (doc,)):
            plan.append((code_pour_tableau(con, exercice, r["numero"]), r["chapitre"], r["section"], r["numero"]))
    for code in codes or []:
        a = con.execute("SELECT tableau_n FROM appariement WHERE code_indicateur=? AND exercice=?",
                        (code, exercice)).fetchone()
        n = a[0] if a else None
        p = con.execute("SELECT chapitre, section FROM passages p JOIN documents d USING(doc_id) WHERE "
                        "d.type='annuaire' AND d.exercice=? AND p.nature='tableau' AND p.numero=? LIMIT 1",
                        (exercice, n)).fetchone() if n else None
        plan.append((code, p[0] if p else "Indicateurs", p[1] if p else "", n))
    plan.sort(key=lambda x: (x[3] is None, x[3] or 0))
    # 2) commentaires : validés, sinon (démonstration) produits et signalés « à relire »
    sections, non_valides, abstentions = [], [], []
    for code, ch, se, n in dict.fromkeys(plan):
        res = commentaire_valide(con, code, exercice)
        if res is None:
            if not accepter:
                abstentions.append({"code": code, "tableau_n": n, "motif": "aucun commentaire validé"})
                continue
            res = cm.commenter(con, code, exercice, client, journaliser=journaliser, moteur=moteur)
            res["valide"] = False
        if res.get("abstention"):
            abstentions.append({"code": code, "tableau_n": n, "motif": res.get("motif"),
                                "mention": res.get("mention")})
            continue
        if not res["valide"]:
            non_valides.append(code)
        sections.append({"chapitre": ch, "section": se, "tableau_n": n, "code": code,
                         "intitule": res.get("tableau_intitule") or res.get("indicateur"),
                         "commentaire": res, "valide": res["valide"]})
    # 3) transitions sans chiffre (modèle de langage seulement), contrôlées
    for i in range(1, len(sections)):
        if client is None or sections[i]["chapitre"] == sections[i - 1]["chapitre"] and \
                sections[i]["section"] == sections[i - 1]["section"]:
            continue
        try:
            brut = client.generer(prompts.SYSTEME_TRANSITION,
                                  prompts.utilisateur_transition(sections[i - 1]["intitule"], sections[i]["intitule"]))
            t = json.loads(brut).get("transition", "")
        except Exception:
            t = ""
        c = literal_check.controler([{"type": "transition", "texte": t}], [], [])
        if t and c.enonces and not literal_check.nombres(t):
            sections[i]["transition"] = c.enonces[0]["texte"]
    note = {
        "type": "note_analyse", "exercice": exercice,
        "titre": titre or f"Note d'analyse — exercice {exercice}" + (f" — {chapitre}" if chapitre else ""),
        "date": datetime.now().strftime("%d/%m/%Y"), "sections": sections, "abstentions": abstentions,
        "commentaires_non_valides": non_valides, "mode_extractif": client is None,
        "modele": client.nom if client else cm.MODE_EXTRACTIF,
        "provisoire": any(s["commentaire"].get("provisoire") for s in sections),
    }
    note["duree_s"] = round(time.time() - t0, 3)
    if journaliser:
        note["prod_id"] = db.journaliser(
            con, "note_analyse", {"exercice": exercice, "codes": codes, "chapitre": chapitre, "documents": documents},
            {k: v for k, v in note.items() if k != "sections"} | {"codes": [s["code"] for s in sections]},
            sources=[{"code": s["code"], "prod_id": s["commentaire"].get("prod_id")} for s in sections],
            abstentions=abstentions, modele=note["modele"], duree_s=note["duree_s"])
    return note
