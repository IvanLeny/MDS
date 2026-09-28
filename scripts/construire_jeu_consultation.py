"""Construit data/gold/consultation.json (jeu de questions de consultation, H1).

Les questions sont rédigées par l'auteur à partir des publications (source « auteur »).
Les pages pertinentes ne sont PAS saisies à la main : pour chaque question, on
retient toutes les pages (doc_id, page) de documents publiés dont le texte
contient TOUTES les valeurs attendues et TOUS les termes clés. Le document
visé à la rédaction (« cible ») doit figurer parmi elles, sinon le script
s'arrête : la question est mal ancrée.

Les champs annotateur_1 / annotateur_2 recevront le jugement de pertinence
des deux lecteurs (kappa de Cohen calculé par l'évaluation dès que la seconde
annotation existe). Les questions des cadres s'ajoutent avec source « cellule ».

    python scripts/construire_jeu_consultation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from minpmeesa import config  # noqa: E402
from minpmeesa.guards.normalize import cles, extraire_nombres  # noqa: E402
from minpmeesa.retrieval.text import plat  # noqa: E402
from minpmeesa.store.db import Base  # noqa: E402

# (id, question, cible, valeurs attendues, termes clés, réponse attendue)
QUESTIONS = [
    # --- Annuaires statistiques ---
    ("Q01", "À combien est estimé le nombre d'entreprises en activité au Cameroun en 2021, et combien sont des PME ?",
     "annuaire_2021", ["324 899", "324 250"], ["PME"], "324 899 entreprises en activité, dont 324 250 PME."),
    ("Q02", "Combien d'entreprises étaient en activité en 2022 et combien de PME ?",
     "annuaire_2022", ["350 422", "349 722"], ["PME"], "350 422 entreprises, dont 349 722 PME."),
    ("Q03", "Combien d'organisations de l'économie sociale ont été enregistrées auprès du MINADER en 2022 et quelle hausse cela représente-t-il ?",
     "annuaire_2022", ["3 405", "57,21"], ["OES"], "3 405 OES, soit +57,21 % par rapport à 2021."),
    ("Q04", "Combien d'unités de production artisanale ont été enregistrées dans les bureaux communaux d'artisanat en 2022 ?",
     "annuaire_2022", ["5 912", "3,59"], ["UPA"], "5 912 UPA, en baisse de 3,59 % par rapport à 2021."),
    ("Q05", "Combien de PME ont été créées dans les CFCE en 2022 ?",
     "annuaire_2022", ["15 601"], ["CFCE"], "15 601 PME créées dans les CFCE."),
    ("Q06", "Quelle est la part des promoteurs de sexe masculin parmi les entreprises créées en 2023 ?",
     "annuaire_2023", ["73,43"], ["masculin"], "73,43 % des promoteurs sont des hommes."),
    ("Q07", "Quelle proportion d'entreprises a été créée par des femmes en 2023, comparée à 2022 ?",
     "annuaire_2023", ["26,57", "25,87"], ["féminin"], "26,57 % en 2023 contre 25,87 % en 2022."),
    ("Q08", "Combien d'UPA les bureaux communaux ont-ils enregistrées en 2023 et comment ce chiffre a-t-il évolué depuis 2022 ?",
     "annuaire_2023", ["3 557", "39,83"], ["UPA"], "3 557 UPA, soit une baisse de 39,83 %."),
    ("Q09", "Quel est le stock de PME estimé en 2024 et le nombre total d'entreprises en activité ?",
     "annuaire_2024", ["443 524", "444 302"], ["PME"], "443 524 PME sur 444 302 entreprises."),
    ("Q10", "Combien d'entreprises créées dans les CFCE en 2024 relèvent du secteur tertiaire ?",
     "annuaire_2024", ["18 029", "85,4"], ["tertiaire"], "18 029 créations, soit 85,4 %."),
    ("Q11", "Combien d'UPA les bureaux communaux d'artisanat ont-ils enregistrées en 2024 ?",
     "annuaire_2024", ["3 602", "1,3"], ["UPA"], "3 602 UPA, en hausse de 1,3 %."),
    ("Q12", "Sur quelles enquêtes repose l'estimation du nombre d'unités de production informelles en 2024 ?",
     "annuaire_2024", ["2,5", "3,4"], ["EESI"], "Interpolation à partir de l'EESI2 (2,5 millions, 2010) et de l'EESI3 (3,4 millions, 2021)."),
    ("Q13", "Combien de PME du secteur secondaire comptait-on en 2016 ?",
     "annuaire_2024", ["31 694"], ["Secondaire"], "31 694 PME du secteur secondaire en 2016."),
    ("Q14", "Combien de PME ont été créées au CFCE de Douala en 2024 ?",
     "annuaire_2024", ["6 815"], ["Douala"], "6 815 PME créées au CFCE de Douala."),
    ("Q15", "Quelle a été la croissance économique mondiale en 2024 selon le FMI ?",
     "annuaire_2024", ["3,2", "3,0"], ["FMI", "mondiale"], "3,2 % en 2024 contre 3,0 % en 2023."),
    ("Q16", "À combien s'élève le concours financier du FMI au Cameroun ?",
     "annuaire_2021", ["483", "375"], ["DTS"], "483 millions de DTS, environ 375 milliards de FCFA."),
    # --- Rapports d'analyse ---
    ("Q17", "Quelle part du stock de PME est concentrée à Douala et à Yaoundé ?",
     "rapport_analyse_2024", ["33,5", "23,9", "57,4"], ["Douala"], "Douala 33,5 %, Yaoundé 23,9 %, soit 57,4 %."),
    ("Q18", "Quelle est la part des PME du secteur secondaire en 2022 et en 2024 ?",
     "rapport_analyse_2024", ["18,16", "22,70"], ["secondaire"], "18,16 % en 2022, 22,70 % en 2024."),
    ("Q19", "De combien les créations d'entreprises dans les CFCE ont-elles augmenté entre 2019 et 2024 ?",
     "rapport_analyse_2024", ["14 229", "21 132", "48,5"], ["CFCE"], "De 14 229 à 21 132, soit +48,5 %."),
    ("Q20", "Combien d'OES ont été créées en 2024 et quelle est l'évolution par rapport à 2023 ?",
     "rapport_analyse_2024", ["3 909", "3 865", "1,1"], ["OES"], "3 909 contre 3 865 en 2023, soit +1,1 %."),
    ("Q21", "Dans quelles régions se concentrent les créations d'OES en 2024 ?",
     "rapport_analyse_2024", ["31,10", "18,1"], ["Sud"], "Sud (31,10 %), Centre (18,1 %), Littoral, Nord."),
    ("Q22", "Comment ont évolué les enregistrements d'UPA dans les bureaux communaux depuis 2019 ?",
     "rapport_analyse_2024", ["68,74"], ["UPA"], "Forte baisse : -68,74 %."),
    ("Q23", "Quelle proportion des UPA enregistrées en 2024 est portée par des femmes ?",
     "rapport_analyse_2024", ["53,7", "46,3"], ["femmes"], "53,7 % contre 46,3 % pour les hommes."),
    ("Q24", "Combien de PME formelles le Cameroun pourrait-il compter au regard de la vitalité du secteur informel ?",
     "rapport_analyse_2024", ["2 000 000"], ["informel"], "Environ 2 000 000 de PME formelles."),
    ("Q25", "Combien de PME sont bien structurées et font une déclaration statistique et fiscale ?",
     "rapport_analyse_2024", ["62 124"], ["déclaration"], "62 124 PME, soit 14 %."),
    ("Q26", "Quelle proportion des promoteurs de PME a au plus 40 ans en 2023 ?",
     "rapport_analyse_2023", ["69,77"], ["40 ans"], "69,77 %."),
    ("Q27", "Comment a évolué la part des OES dans le secteur secondaire entre 2022 et 2023 ?",
     "rapport_analyse_2023", ["15,18"], ["secondaire"], "De 15,18 % à 20,39 %."),
    ("Q28", "Comment évolue la part des hommes dans les enregistrements d'UPA depuis 2018 ?",
     "rapport_analyse_2023", ["64,9", "51,22"], ["hommes"], "De 64,9 % en 2018 à 51,22 % en 2023."),
    ("Q29", "Quel montant de crédits la BC-PME a-t-elle débloqué en 2022 et pour combien d'entreprises ?",
     "rapport_analyse_2022", ["10 942 703 443", "434"], ["BC-PME"], "10 942 703 443 FCFA pour 434 entreprises."),
    ("Q30", "Quelle quantité de blé le Cameroun a-t-il importée en 2021 ?",
     "rapport_analyse_2022", ["966 400"], ["blé"], "966 400 tonnes."),
    ("Q31", "Dans quelles régions l'enregistrement des UPA est-il majoritaire en 2022 ?",
     "rapport_analyse_2022", ["26,49", "16,85"], ["Extrême-Nord"], "Extrême-Nord (26,49 %), Centre (16,85 %), Littoral."),
    ("Q32", "Combien d'artisans ont été enregistrés dans les registres communaux en 2021 ?",
     "rapport_analyse_2021", ["6 132", "7 482"], ["artisans"], "6 132 contre 7 482 en 2020."),
    ("Q33", "Combien de formalisations d'entreprises supplémentaires a-t-on dénombré en 2021 par rapport à 2020 ?",
     "rapport_analyse_2021", ["4 910", "45,96"], ["formalisations"], "4 910 de plus, soit +45,96 %."),
    ("Q34", "Quel est le taux de mortalité des très petites entreprises selon le RGE-2 ?",
     "rapport_analyse_2021", ["45,6"], ["mortalité"], "45,6 %."),
    # --- Notes de conjoncture ---
    ("Q35", "Sur combien d'entreprises repose la note de conjoncture du 3e trimestre 2022 et quel est le taux de couverture ?",
     "note_conjoncture_2022_T3", ["314", "62,8"], ["couverture"], "314 entreprises, taux de couverture de 62,8 %."),
    ("Q36", "Quelle proportion de chefs d'entreprise n'a pas recruté de personnel au 3e trimestre 2022 ?",
     "note_conjoncture_2022_T3", ["88,2"], ["recruté"], "88,2 %."),
    ("Q37", "Quelle part des chefs d'entreprise a réalisé de nouveaux investissements au 3e trimestre 2022 ?",
     "note_conjoncture_2022_T3", ["18,9"], ["investissements"], "18,9 %."),
    ("Q38", "Quelle proportion de PME a recruté au moins un employé au 4e trimestre 2023 ?",
     "note_conjoncture_2023_T4", ["23,1", "14,8"], ["recruté"], "23,1 % contre 14,8 % au trimestre précédent."),
    ("Q39", "Quelle part des OES a connu une trésorerie difficile au 4e trimestre 2023 ?",
     "note_conjoncture_2023_T4", ["63,8", "53,4"], ["trésorerie"], "63,8 % contre 53,4 % au 3e trimestre."),
    ("Q40", "Quelle proportion d'UPA a vu son volume d'activité s'améliorer au 4e trimestre 2023 ?",
     "note_conjoncture_2023_T4", ["72,8"], ["UPA"], "72,8 %."),
    ("Q41", "Quelle proportion de PME a enregistré un résultat net négatif au premier trimestre 2024 ?",
     "note_conjoncture_2024_T1", ["48,7", "26,2"], ["résultat net"], "48,7 % négatif, 26,2 % nul."),
    ("Q42", "Quelles sont les principales raisons de la hausse des coûts de production au premier trimestre 2024 ?",
     "note_conjoncture_2024_T1", ["38,35", "27,78"], ["matières premières"], "Matières premières (38,35 %), transport (27,78 %), énergie."),
    ("Q43", "Quelle part des PME n'a pas réalisé de nouveaux investissements au 1er trimestre 2024 ?",
     "note_conjoncture_2024_T1", ["71,3"], ["investissements"], "71,3 %."),
    ("Q44", "Quelle proportion de PME déclare une trésorerie difficile au 2e trimestre 2024 ?",
     "note_conjoncture_2024_T2", ["69,80"], ["trésorerie"], "Plus de 69,80 %."),
    ("Q45", "Quelles raisons les PME avancent-elles pour expliquer leur niveau d'activité au deuxième trimestre 2024 ?",
     "note_conjoncture_2024_T2", ["56,20", "30,60"], ["concurrence"], "Inflation (56,20 %), concurrence (30,60 %), financement, insécurité."),
    ("Q46", "Comment a évolué la part des chefs d'entreprise percevant une dynamique positive de leur activité jusqu'au 3e trimestre 2024 ?",
     "note_conjoncture_2024_T3", ["55,7", "41,0", "38,0"], ["dynamique"], "55,7 % (T3 2023), 41,0 % (T2 2024), 38,0 % (T3 2024)."),
    ("Q47", "Quelle proportion des chefs d'entreprise jugeait ses coûts de production compétitifs au 3e trimestre 2024 ?",
     "note_conjoncture_2024_T3", ["73,8"], ["compétitifs"], "73,8 %."),
    ("Q48", "Quelle part des PME juge sa situation de trésorerie soutenable au premier trimestre 2025 ?",
     "note_conjoncture_2025_T1", ["30,6", "36,1"], ["trésorerie"], "30,6 % contre 36,1 % au trimestre précédent."),
    ("Q49", "Quelle part des entreprises déclarait un résultat net négatif au premier trimestre 2025 ?",
     "note_conjoncture_2025_T1", ["53,5", "51,6"], ["résultat net"], "53,5 % contre 51,6 % au T4 2024."),
    # --- Documents de contexte ---
    ("Q50", "Quel était le taux d'inflation mondial en 2022 ?",
     "contexte_inflation_2023", ["8,8", "4,7"], ["inflation"], "8,8 % en 2022 contre 4,7 % en 2021."),
    ("Q51", "Quel était le taux d'inflation dans la zone CEMAC en 2022 ?",
     "contexte_inflation_2023", ["5,5", "1,5"], ["CEMAC"], "5,5 % en 2022 contre 1,5 % en 2021."),
    ("Q52", "Quelles régions portent l'inflation au Cameroun en 2022 ?",
     "contexte_inflation_2023", ["7,4", "7,3", "7,1"], ["Adamaoua"], "Adamaoua (7,4 %), Ouest (7,3 %), Sud-Ouest (7,1 %)."),
    ("Q53", "Quel montant de subvention sur les carburants le Cameroun a-t-il levé en 2023 ?",
     "contexte_inflation_2023", ["700"], ["subvention"], "Près de 700 milliards de FCFA."),
    ("Q54", "Quelle part des emplois créés par les entreprises est fournie par les PME ?",
     "contexte_competitivite_pme_2024", ["70,20", "3,38"], ["emplois"], "70,20 % des emplois ; 3,38 millions d'entreprises."),
    ("Q55", "Quel montant la loi de finances 2021 a-t-elle alloué à la ligne de garantie et quelle part revient aux PME ?",
     "contexte_competitivite_pme_2024", ["200", "70"], ["garantie"], "200 milliards de FCFA, dont 70 % pour les PME."),
    ("Q56", "Quel volume d'huile de palme le Cameroun a-t-il importé en 2023 ?",
     "contexte_competitivite_pme_2024", ["144 068", "21,2"], ["huile de palme"], "144 068 tonnes, couvrant 21,2 % du déficit."),
    ("Q57", "Quel montant de ligne de crédit a été mis en place en faveur des TPE et des PME ?",
     "contexte_bulletin_2024", ["10"], ["ligne de credits de 10 milliards"], "Une ligne de crédits de 10 milliards de FCFA."),
    ("Q58", "Quelle proportion des chefs d'entreprise juge les coûts et conditionnalités du crédit comme des obstacles ?",
     "contexte_competitivite_pme_2024", ["92"], ["conditionnalités"], "92 %."),
    ("Q59", "Quelles croissance et inflation le Cameroun a-t-il connues en 2022 selon le bulletin sur la loi de finances 2023 ?",
     "contexte_bulletin_2023", ["3.4", "6.2"], ["inflation"], "Croissance de 3,4 % et inflation de 6,2 %."),
]

HORS_CORPUS = [
    ("H01", "Quel est le taux de chômage des jeunes diplômés au Sénégal en 2023 ?"),
    ("H02", "Combien d'entreprises ont été créées au Gabon en 2024 ?"),
    ("H03", "Quel est le cours de l'action MTN à la bourse de Douala ?"),
    ("H04", "Quelle est la recette traditionnelle du ndolé ?"),
    ("H05", "Quels ont été les résultats des Lions indomptables à la CAN 2024 ?"),
    ("H06", "Quel est le salaire moyen des enseignants du secondaire au Cameroun ?"),
    ("H07", "Combien de touristes étrangers ont visité le Kenya en 2022 ?"),
    ("H08", "Combien de lits d'hôpital compte le Tchad par habitant ?"),
    ("H09", "Quelle est la production de cacao de la Côte d'Ivoire en 2024 ?"),
    ("H10", "Quel est le taux de pénétration de l'internet mobile en Europe ?"),
]


def pages_pertinentes(base: Base, valeurs, termes):
    """(doc_id, page) des documents publiés dont la page contient toutes les
    valeurs et tous les termes (comparaison sans accents, écritures harmonisées)."""
    cles_att = [cles(extraire_nombres(v, bornes_annees=(0, -1), garder_references=True)[0]) for v in valeurs]
    termes_p = [plat(t) for t in termes]
    out = []
    for d in base.q("SELECT * FROM documents WHERE statut_diffusion='publie'"):
        doc = pymupdf.open(config.chemin("corpus") / d["fichier"])
        for i, page in enumerate(doc, start=1):
            t = page.get_text()
            tp = plat(" ".join(t.split()))
            if not all(x in tp for x in termes_p):
                continue
            k = set()
            for n in extraire_nombres(t, bornes_annees=(0, -1), garder_references=True):
                k |= cles(n)
            if all(c & k for c in cles_att):
                out.append({"doc_id": d["doc_id"], "page": i})
        doc.close()
    return out


def main():
    base = Base(config.chemin("base"))
    items = []
    for qid, q, cible, vals, termes, rep in QUESTIONS:
        pert = pages_pertinentes(base, vals, termes)
        if not any(p["doc_id"] == cible for p in pert):
            raise SystemExit(f"{qid} : aucune page du document cible {cible} ne contient {vals} + {termes}")
        items.append({"id": qid, "question": q, "hors_corpus": False, "source": "auteur",
                      "document_cible": cible, "pertinents": pert, "valeurs_attendues": vals,
                      "termes_cles": termes, "reponse_attendue": rep,
                      "annotateur_1": {"pertinence": None}, "annotateur_2": {"pertinence": None}})
        print(f"{qid} {len(pert):2d} page(s) pertinente(s) : " + ", ".join(f"{p['doc_id']} p{p['page']}" for p in pert[:6]))
    for qid, q in HORS_CORPUS:
        items.append({"id": qid, "question": q, "hors_corpus": True, "source": "auteur", "pertinents": [],
                      "valeurs_attendues": [], "reponse_attendue": "Abstention attendue.",
                      "annotateur_1": {"pertinence": None}, "annotateur_2": {"pertinence": None}})
    sortie = config.chemin("gold") / "consultation.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({
        "_description": ("Jeu de questions de consultation (H1). Rédigé par l'auteur à partir des publications "
                         "(source « auteur ») ; pages pertinentes calculées automatiquement (toutes les valeurs "
                         "attendues et tous les termes clés présents sur la page). Les questions des cadres "
                         "s'ajoutent avec source « cellule ». annotateur_1/annotateur_2 : jugement de pertinence "
                         "(1/0) des passages restitués, pour le kappa de Cohen."),
        "questions": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} questions ({len(HORS_CORPUS)} hors corpus) -> {sortie}")


if __name__ == "__main__":
    main()
