"""Table d'appariement indicateur / tableau / commentaire (section 2.3.2).

Pour chaque exercice disposant d'un couple Rapport d'analyse + Annuaire :
  - chaque GRAPHIQUE commenté du Rapport est rapproché du TABLEAU de l'Annuaire
    qui en porte les valeurs ;
  - score = poids_intitule x similarité des intitulés
            + poids_valeurs x part des valeurs affichées du graphique retrouvées
              dans le tableau (signal fort : un graphique trace les valeurs d'un tableau) ;
  - un code indicateur STABLE d'une édition à l'autre est attribué par
    rapprochement des intitulés.
Le module PROPOSE ; il ne tranche pas. Toute ligne naît « candidat » (ou
« a_verifier » sous le seuil) et doit être validée par double lecture humaine.
Les décisions humaines, consignées dans data/pairing/appariement_AAAA.csv,
sont conservées d'une reconstruction à l'autre.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

from ..texte import ensemble, jaccard, normaliser
from .tables import valeur_num, est_valeur, est_millesime

CHAMPS = ["code_indicateur", "exercice", "graphique_n", "graphique_intitule", "tableau_n",
          "tableau_intitule", "doc_rapport", "doc_annuaire", "score", "score_intitule",
          "score_valeurs", "tableau_n_2e", "score_2e", "statut", "valide_par", "date_validation"]


@dataclass
class Ligne:
    code_indicateur: str
    exercice: int
    graphique_n: int
    graphique_intitule: str
    tableau_n: int | None
    tableau_intitule: str
    doc_rapport: str
    doc_annuaire: str
    score: float
    score_intitule: float
    score_valeurs: float
    tableau_n_2e: int | None = None
    score_2e: float | None = None
    statut: str = "candidat"
    valide_par: str = ""
    date_validation: str = ""
    extrait_commentaire: str = field(default="", repr=False)
    extrait_tableau: str = field(default="", repr=False)


_UNITE = re.compile(r"\((en|in)\s[^)]*\)|\(\s*%\s*\)|\ben\s*%", re.I)
_PERIODE = re.compile(r"\b(de|entre|en|depuis)?\s*(19|20)\d{2}(\s*(a|à|et|-)\s*(19|20)?\d{0,2})?\b", re.I)


def intitule_normalise(intitule: str) -> str:
    """Intitulé sans années, périodes ni unités (comparable d'une édition à l'autre)."""
    s = _UNITE.sub(" ", intitule)
    s = _PERIODE.sub(" ", s)
    s = normaliser(s).replace("crees", "creees")
    return re.sub(r"\s+", " ", s).strip(" .,:")


def slug(intitule: str, n: int = 6) -> str:
    mots = [m for m in re.findall(r"[a-z0-9]+", intitule_normalise(intitule))
            if m in ensemble(intitule_normalise(intitule)) or len(m) > 2]
    vus = []
    for m in mots:
        if m not in vus and m not in {"des", "les", "par", "selon", "evolution", "repartition"}:
            vus.append(m)
    return "-".join(vus[:n]) or "indicateur"


def _valeurs(textes: list[str]) -> set[float]:
    out = set()
    for t in textes:
        for m in re.findall(r"\d[\d\s .,]*\d|\d", t):
            m = m.strip()
            if est_valeur(m) and not est_millesime(m):
                v = valeur_num(m)
                if v is not None:
                    out.add(round(v, 2))
    return out


def recouvrement(etiquettes: list[str], valeurs_tableau: set[float]) -> float:
    """Part des valeurs affichées par le graphique présentes dans le tableau."""
    vg = _valeurs(etiquettes)
    if not vg:
        return 0.0
    # Un graphique affiche parfois une décimale de plus que le tableau (82,75 / 82,7).
    arrondis = {round(v, 1) for v in valeurs_tableau} | {round(v) for v in valeurs_tableau}
    return sum(1 for v in vg if v in valeurs_tableau or round(v, 1) in arrondis) / len(vg)


def proposer(exercice: int, graphiques: list[dict], tableaux: dict[int, dict],
             doc_rapport: str, doc_annuaire: str, cfg: dict) -> list[Ligne]:
    """graphiques : [{numero, titre, etiquettes, commentaire}] ;
    tableaux : {numero: {intitule, valeurs:set, extrait}}."""
    pa = cfg["appariement"]
    out = []
    for g in graphiques:
        scores = []
        for n, t in tableaux.items():
            si = jaccard(intitule_normalise(g["titre"]), intitule_normalise(t["intitule"]))
            sv = recouvrement(g["etiquettes"], t["valeurs"])
            scores.append((pa["poids_intitule"] * si + pa["poids_valeurs"] * sv, si, sv, n))
        scores.sort(reverse=True)
        best = scores[0] if scores else (0.0, 0.0, 0.0, None)
        second = scores[1] if len(scores) > 1 else None
        n = best[3]
        out.append(Ligne(
            code_indicateur="", exercice=exercice, graphique_n=g["numero"],
            graphique_intitule=g["titre"], tableau_n=n,
            tableau_intitule=tableaux[n]["intitule"] if n is not None else "",
            doc_rapport=doc_rapport, doc_annuaire=doc_annuaire,
            score=round(best[0], 3), score_intitule=round(best[1], 3), score_valeurs=round(best[2], 3),
            tableau_n_2e=second[3] if second else None, score_2e=round(second[0], 3) if second else None,
            statut="candidat" if best[0] >= pa["seuil_candidat"] else "a_verifier",
            extrait_commentaire=g.get("commentaire", "")[:400],
            extrait_tableau=tableaux[n]["extrait"] if n is not None else ""))
    return out


def attribuer_codes(par_exercice: dict[int, list[Ligne]], seuil: float) -> None:
    """Code indicateur stable : une édition reprend le code de l'édition
    antérieure dont l'intitulé normalisé est le plus proche (>= seuil)."""
    connus: dict[str, str] = {}              # code -> dernier intitulé normalisé
    for ex in sorted(par_exercice):
        pris = set()
        for l in par_exercice[ex]:
            if l.code_indicateur:            # code fixé par une validation humaine
                pris.add(l.code_indicateur)
                connus[l.code_indicateur] = intitule_normalise(l.graphique_intitule)
        for l in par_exercice[ex]:
            if l.code_indicateur:
                continue
            norm = intitule_normalise(l.graphique_intitule)
            cands = sorted(((jaccard(norm, t), c) for c, t in connus.items() if c not in pris),
                           reverse=True)
            if cands and cands[0][0] >= seuil:
                code = cands[0][1]
            else:
                base = slug(l.graphique_intitule)
                code, k = base, 2
                while code in connus or code in pris:
                    code, k = f"{base}-{k}", k + 1
            l.code_indicateur = code
            pris.add(code)
            connus[code] = norm


# ------------------------------------------------------------ fichiers
def lire_csv(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def fusionner_decisions(lignes: list[Ligne], chemin_csv: Path) -> list[Ligne]:
    """Conserve les décisions humaines (valide / rejete, tableau corrigé, code)
    déjà consignées dans le CSV de l'exercice."""
    anciennes = {int(r["graphique_n"]): r for r in lire_csv(chemin_csv)
                 if r.get("statut") in ("valide", "rejete")}
    for l in lignes:
        r = anciennes.get(l.graphique_n)
        if not r:
            continue
        l.statut = r["statut"]
        l.valide_par = r.get("valide_par", "")
        l.date_validation = r.get("date_validation", "")
        if r.get("tableau_n"):
            l.tableau_n = int(float(r["tableau_n"]))
        if r.get("tableau_intitule"):
            l.tableau_intitule = r["tableau_intitule"]
        if r.get("code_indicateur"):
            l.code_indicateur = r["code_indicateur"]
    return lignes


def ecrire_csv(lignes: list[Ligne], chemin: Path) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
        w.writeheader()
        for l in lignes:
            d = asdict(l)
            w.writerow({k: d[k] for k in CHAMPS})
    return chemin


def ecrire_xlsx_validation(lignes: list[Ligne], chemin: Path) -> Path:
    """Fichier de double lecture humaine (2.3.2) : une ligne par graphique, avec
    les extraits nécessaires pour juger, et deux colonnes de décision."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "a_valider"
    entetes = ["code_indicateur", "exercice", "graphique_n", "graphique_intitule",
               "extrait_commentaire", "tableau_n", "tableau_intitule", "extrait_tableau",
               "score", "score_intitule", "score_valeurs", "tableau_n_2e", "score_2e",
               "statut_propose", "lecteur_1_decision", "lecteur_1_tableau_corrige",
               "lecteur_2_decision", "lecteur_2_tableau_corrige", "remarques"]
    ws.append(entetes)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E79")
    for l in lignes:
        ws.append([l.code_indicateur, l.exercice, l.graphique_n, l.graphique_intitule,
                   l.extrait_commentaire, l.tableau_n, l.tableau_intitule, l.extrait_tableau,
                   l.score, l.score_intitule, l.score_valeurs, l.tableau_n_2e, l.score_2e,
                   l.statut, "", "", "", "", ""])
    dv = DataValidation(type="list", formula1='"valide,rejete,corrige"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"O2:O{len(lignes) + 1}")
    dv.add(f"Q2:Q{len(lignes) + 1}")
    largeurs = [26, 9, 9, 45, 60, 9, 45, 60, 7, 8, 8, 9, 8, 11, 14, 14, 14, 14, 30]
    for i, w in enumerate(largeurs):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    notice = wb.create_sheet("mode_emploi")
    for t in [
        "Double lecture de l'appariement (mémoire, section 2.3.2).",
        "Chaque lecteur remplit SA colonne sans regarder celle de l'autre :",
        "  valide  : le tableau proposé porte bien les valeurs du graphique ;",
        "  rejete  : aucun tableau de l'Annuaire ne correspond ;",
        "  corrige : le bon tableau est un autre ; indiquer son numéro dans la colonne voisine.",
        "Puis : python -m minpmeesa.ingestion.pairing importer data/pairing/a_valider_AAAA.xlsx",
        "Accord des deux lecteurs -> statut valide / rejete ; désaccord -> a_verifier (à arbitrer).",
        "Le kappa de Cohen entre les deux lecteurs est calculé et écrit dans data/pairing/accord_AAAA.json.",
    ]:
        notice.append([t])
    notice.column_dimensions["A"].width = 110
    chemin.parent.mkdir(parents=True, exist_ok=True)
    wb.save(chemin)
    return chemin


def kappa_cohen(a: list, b: list) -> float | None:
    """Kappa de Cohen entre deux listes de décisions appariées."""
    from collections import Counter
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 4)


def importer_validation(chemin_xlsx: Path, dossier_csv: Path) -> dict:
    """Lit les décisions des deux lecteurs et met à jour appariement_AAAA.csv."""
    import json
    from datetime import date
    from openpyxl import load_workbook

    ws = load_workbook(chemin_xlsx)["a_valider"]
    lignes = list(ws.iter_rows(values_only=True))
    ent = list(lignes[0])
    rows = [dict(zip(ent, r)) for r in lignes[1:] if any(r)]
    if not rows:
        return {"lignes": 0}
    ex = int(rows[0]["exercice"])
    chemin_csv = dossier_csv / f"appariement_{ex}.csv"
    csv_rows = {int(r["graphique_n"]): r for r in lire_csv(chemin_csv)}
    d1, d2, bilan = [], [], {"valide": 0, "rejete": 0, "a_verifier": 0, "non_lu": 0}
    for r in rows:
        a = (r.get("lecteur_1_decision") or "").strip().lower()
        b = (r.get("lecteur_2_decision") or "").strip().lower()
        ta = r.get("lecteur_1_tableau_corrige") if a == "corrige" else r.get("tableau_n")
        tb = r.get("lecteur_2_tableau_corrige") if b == "corrige" else r.get("tableau_n")
        cible = csv_rows.get(int(r["graphique_n"]))
        if cible is None:
            continue
        if not a or not b:
            bilan["non_lu"] += 1
            continue
        d1.append(f"{a}:{ta}")
        d2.append(f"{b}:{tb}")
        if a == b and str(ta) == str(tb):
            statut = "rejete" if a == "rejete" else "valide"
            cible["statut"] = statut
            if a == "corrige":
                cible["tableau_n"] = str(ta)
            cible["valide_par"] = "double lecture"
            cible["date_validation"] = date.today().isoformat()
            bilan[statut] += 1
        else:
            cible["statut"] = "a_verifier"
            bilan["a_verifier"] += 1
    with open(chemin_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
        w.writeheader()
        for r in csv_rows.values():
            w.writerow({k: r.get(k, "") for k in CHAMPS})
    bilan["kappa_cohen"] = kappa_cohen(d1, d2)
    bilan["exercice"] = ex
    (dossier_csv / f"accord_{ex}.json").write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")
    return bilan


if __name__ == "__main__":
    import sys
    from .. import config
    if len(sys.argv) >= 3 and sys.argv[1] == "importer":
        print(importer_validation(Path(sys.argv[2]), config.chemin("appariement")))
        print("Relancez la reconstruction pour appliquer : python -m minpmeesa.ingestion.build")
    else:
        print("Usage : python -m minpmeesa.ingestion.pairing importer data/pairing/a_valider_AAAA.xlsx")
