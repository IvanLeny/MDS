"""Construit data/gold/consultation.json (jeu de questions de consultation, H1).

Chaque question est rédigée par l'auteur à partir des publications (source
« auteur »). Les pages pertinentes ne sont PAS saisies à la main : elles sont
localisées dans le PDF à partir d'un extrait exact, et les valeurs attendues
doivent figurer sur ces pages. Le script échoue sinon : aucune page, aucune
valeur n'est inventée.

Les colonnes `annotateur_1` / `annotateur_2` reçoivent le jugement de
pertinence des deux lecteurs (le second lecteur les remplit ; kappa ensuite).
Les questions réelles des cadres s'ajoutent avec source « cellule ».
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

RACINE = Path(__file__).resolve().parent.parent
CORPUS = RACINE / "data" / "corpus"

# (id, question, [(doc_id, extrait)], valeurs attendues, réponse attendue, catégorie)
QUESTIONS = [
    # --- Annuaires et rapports 2024 ---
    ("Q01", "À combien est estimé le stock d'entreprises en activité au Cameroun en 2024 ?",
     [("rapport_analyse_2024", "estimé à 444 302 unités")], ["444 302", "443 524", "778"],
     "444 302 entreprises, dont 443 524 PME et 778 grandes entreprises.", "valeur"),
    ("Q02", "Quelle part du stock de PME est concentrée à Douala et à Yaoundé en 2024 ?",
     [("rapport_analyse_2024", "Douala (33,5%)")], ["33,5", "23,9", "57,4"],
     "Douala 33,5 % et Yaoundé 23,9 %, soit 57,4 % du stock.", "valeur"),
    ("Q03", "Quelle est la tranche d'âge des promoteurs de PME la plus représentée en 2024 ?",
     [("rapport_analyse_2024", "celle de 30 à 40 ans")], ["39,8"],
     "Les 30-40 ans, 39,8 % des dirigeants.", "valeur"),
    ("Q04", "Combien de PME ont été créées dans les CFCE en 2024 ?",
     [("rapport_analyse_2024", "ont enregistré 21 132 PME")], ["21 132", "7,5"],
     "21 132 PME, en hausse de 7,5 % par rapport à 2023.", "valeur"),
    ("Q05", "Dans quel secteur se concentrent les PME créées dans les CFCE en 2024 ?",
     [("rapport_analyse_2024", "secteur tertiaire (85,4%)")], ["85,4"],
     "Le tertiaire (85,4 %).", "valeur"),
    ("Q06", "Combien d'UPA les Bureaux Communaux de l'Artisanat ont-ils enregistrées en 2024 ?",
     [("rapport_analyse_2024", "ont enregistré 3 602 Unités de Production Artisanale")], ["3 602"],
     "3 602 UPA.", "valeur"),
    ("Q07", "Quelle est la part des UPA portées par des femmes parmi les enregistrements de 2024 ?",
     [("rapport_analyse_2024", "portées par les femmes (53,7%")], ["53,7"],
     "53,7 %.", "valeur"),
    ("Q08", "Comment a évolué la valeur ajoutée des PME entre 2019 et 2024 ?",
     [("rapport_analyse_2024", "a augmenté de 48,46%")], ["48,46"],
     "Hausse de 48,46 % sur la période.", "valeur"),
    ("Q09", "Quel est le stock de PME par région dans l'Annuaire 2024, par exemple dans l'Adamaoua ?",
     [("annuaire_2024", "Tableau 4 : Répartition du stock des PME par Région")], ["12 862"],
     "Adamaoua : 12 862 PME en 2024 (2,9 %).", "valeur"),
    ("Q10", "Quelle est la répartition du stock de PME selon la forme juridique ?",
     [("annuaire_2024", "Tableau 3 : Répartition du stock des PME selon la forme juridique")], ["430 218"],
     "Les EI/ETS dominent (430 218 en 2024, 97 %).", "valeur"),
    ("Q11", "Combien d'OES ont été créées en 2024 ?",
     [("rapport_analyse_2024", "En 2024 on dénombre 3 9")], ["3 909"],
     "3 909 OES.", "valeur"),
    ("Q12", "Dans quelles régions se concentrent les créations d'OES en 2024 ?",
     [("rapport_analyse_2024", "régions du Sud (31,10%)")], ["31,10", "18,1"],
     "Sud (31,10 %), Centre (18,1 %), Littoral, Nord.", "valeur"),
    ("Q13", "Quelle est la proportion d'entreprises formelles au sens strict selon le dernier recensement ?",
     [("rapport_analyse_2024", "formelles au sens strict à 62 902")], ["62 902", "14,6"],
     "62 902 entreprises, soit 14,6 % du stock.", "valeur"),
    ("Q14", "Quels sont les défis majeurs à relever pour les PMEESA selon le rapport d'analyse 2024 ?",
     [("rapport_analyse_2024", "Défis majeurs à relever pour les PMEESA")], [],
     "Chapitre 4 du rapport 2024 : défis (financement, informel, compétitivité…).", "analyse"),
    ("Q15", "Quelle méthode est utilisée pour estimer le stock des PME ?",
     [("rapport_analyse_2024", "Modèle d’Équilibre Général Calculable Dynamique")], [],
     "Un modèle d'équilibre général calculable dynamique (MEGC-D).", "definition"),
    # --- Éditions 2021 à 2023 ---
    ("Q16", "Quel était le stock de PME estimé en 2023 ?",
     [("rapport_analyse_2023", "393 954 Entreprises, soit 393 166 PME")], ["393 954", "393 166"],
     "393 166 PME sur 393 954 entreprises.", "valeur"),
    ("Q17", "De combien a augmenté le stock d'entreprises en 2023 par rapport à 2022 ?",
     [("rapport_analyse_2023", "hausse de stock de +12,42%")], ["12,42"],
     "+12,42 %.", "valeur"),
    ("Q18", "Combien de PME ont été créées dans les CFCE en 2022 ?",
     [("rapport_analyse_2022", "ont enregistré 15 601 PME")], ["15 601"],
     "15 601 PME.", "valeur"),
    ("Q19", "Combien d'UPA ont été enregistrées dans les BCA en 2022 et comment ce chiffre a-t-il évolué ?",
     [("rapport_analyse_2022", "5 912 Unités de Production Artisanale")], ["5 912", "6 132", "3,59"],
     "5 912 UPA contre 6 132 en 2021, soit une baisse de 3,59 %.", "valeur"),
    ("Q20", "Dans quelles régions l'enregistrement des UPA était-il majoritaire en 2022 ?",
     [("rapport_analyse_2022", "l’Extrême-Nord (26,49 %)")], ["26,49", "16,85"],
     "Extrême-Nord (26,49 %), Centre (16,85 %), Littoral (11,82 %).", "valeur"),
    ("Q21", "Combien de PME ont été créées par les CFCE en 2021 et sur la période 2016-2021 ?",
     [("rapport_analyse_2021", "on dénombre 15 591 entreprises")], ["15 591", "82 486"],
     "15 591 en 2021 ; 82 486 sur 2016-2021.", "valeur"),
    ("Q22", "À combien était estimé le stock de PME en 2021 ?",
     [("rapport_analyse_2021", "stock de PME évalué à 324 250")], ["324 250"],
     "324 250 PME.", "valeur"),
    ("Q23", "Quelle était la croissance du PIB estimée par le FMI pour 2021 ?",
     [("rapport_analyse_2021", "croissance du PIB en 2021 à 3,5%")], ["3,5"],
     "3,5 %.", "valeur"),
    ("Q24", "Pourquoi le nombre de PME créées dans les CFCE en 2023 est-il inférieur au nombre estimé de créations ?",
     [("rapport_analyse_2023", "la réduction de la mortalité des PME")], ["19 651"],
     "Écart expliqué par la baisse de la mortalité et les créations hors CFCE (notaires).", "analyse"),
    ("Q25", "Combien de réseaux de l'économie sociale (RELESS, REDESS, RERESS) ont été mis en place ?",
     [("rapport_analyse_2023", "292 RELESS, 49 REDESS et 9 RERESS")], ["292", "49", "9"],
     "292 RELESS, 49 REDESS et 9 RERESS.", "valeur"),
    ("Q26", "Combien d'UPA ont été enregistrées en 2023 ?",
     [("rapport_analyse_2023", "on dénombre 3 557 UPA")], ["3 557"],
     "3 557 UPA (hors Nord-Ouest).", "valeur"),
    ("Q27", "Quel était le stock de PME en 2022 et quelle part des entreprises représentent-elles ?",
     [("rapport_analyse_2022", "349 722 sont des PME et représentent 99,8 %")], ["349 722", "99,8"],
     "349 722 PME, 99,8 % des entreprises.", "valeur"),
    ("Q28", "Quelle est l'évolution du nombre de PME créées dans les CFCE à Yaoundé entre 2018 et 2024 ?",
     [("annuaire_2024", "Tableau 7 : Évolution du nombre de PME créées dans les CFCE entre 2018 et 2024")],
     ["9 858", "5 033"], "De 5 033 en 2018 à 9 858 en 2024.", "valeur"),
    ("Q29", "Quelle est la valeur ajoutée des PME par secteur d'activité dans l'Annuaire 2024 ?",
     [("annuaire_2024", "Tableau 17 : Évolution de la Valeur Ajoutée des PME de 2018 à 2024 selon")], [],
     "Tableau 17 de l'Annuaire 2024.", "valeur"),
    ("Q30", "Combien d'UPI compte-t-on et comment ce nombre a-t-il évolué depuis 2010 ?",
     [("annuaire_2024", "Tableau 36 : Évolution du nombre d’UPI entre 2010 et 2024")], [],
     "Tableau 36 de l'Annuaire 2024.", "valeur"),
    # --- Notes de conjoncture ---
    ("Q31", "Quelle part des PME déclarait une trésorerie difficile au 2e trimestre 2024 ?",
     [("note_conjoncture_T2_2024", "plus de 69,80% des PME")], ["69,80", "8,70"],
     "Plus de 69,80 % ; seulement 8,70 % une trésorerie aisée.", "valeur"),
    ("Q32", "Quelle proportion d'entreprises déclarait une baisse d'activité au 2e trimestre 2024 ?",
     [("note_conjoncture_T2_2024", "59% d’entreprises déclarent")], ["59", "36,2", "43,3"],
     "59 %, contre 36,2 % un an plus tôt et 43,3 % au T1 2024.", "valeur"),
    ("Q33", "Quel était le taux d'inflation au Cameroun au 2e trimestre 2024 ?",
     [("note_conjoncture_T2_2024", "retomber à 5,7%")], ["5,7"],
     "5,7 %, au-dessus de la norme communautaire de 3 %.", "valeur"),
    ("Q34", "Quelles sont les principales causes de la hausse des coûts de production au 3e trimestre 2024 ?",
     [("note_conjoncture_T3_2024", "prix élevé des matières premières (42,35%)")], ["42,35", "37,88"],
     "Prix des matières premières (42,35 %) et coûts de transport (37,88 %).", "valeur"),
    ("Q35", "Quelle part des PME affichait un résultat net négatif au 3e trimestre 2024 ?",
     [("note_conjoncture_T3_2024", "proportion légèrement réduite en T3_2024 (47,6%)")], ["47,6"],
     "47,6 %.", "valeur"),
    ("Q36", "Quelle a été la croissance économique dans la zone CEMAC au troisième trimestre 2024 ?",
     [("note_conjoncture_T3_2024", "atteignant 6,2% contre 5,7%")], ["6,2"],
     "6,2 % (contre 5,7 % au trimestre précédent).", "valeur"),
    ("Q37", "De combien ont augmenté les prix à la production industrielle au 3e trimestre 2024 ?",
     [("note_conjoncture_T3_2024", "(+5,7% en glissement annuel). Essentiellement")], ["5,7"],
     "+5,7 % en glissement annuel.", "valeur"),
    ("Q38", "Quelle proportion des PME n'a pas créé d'emploi au 1er trimestre 2024 ?",
     [("note_conjoncture_T1_2024", "77,8% des PME n’ont pas créé d’emploi")], ["77,8", "22,2"],
     "77,8 % ; 22,2 % ont recruté.", "valeur"),
    ("Q39", "Quelles raisons les PME évoquent-elles pour la baisse de leur activité au 1er trimestre 2024 ?",
     [("note_conjoncture_T1_2024", "le manque de financement (40%)")], ["40", "37,18"],
     "Manque de financement (40 %), forte concurrence (37,18 %)…", "valeur"),
    ("Q40", "De combien les prix à la pompe ont-ils été relevés en février 2024 ?",
     [("note_conjoncture_T1_2024", "la hausse est de +15% sur les prix du super")], ["15"],
     "+15 % sur le super et le gasoil.", "valeur"),
    ("Q41", "Quelle proportion des PME déclarait avoir augmenté ses prix de vente au 4e trimestre 2023 ?",
     [("note_conjoncture_T4_2023", "(40,4 %) déclarent avoir augmenté le prix")], ["40,4", "8,8"],
     "40,4 %, en hausse de 8,8 % sur le trimestre.", "valeur"),
    ("Q42", "Comment les OES perçoivent-elles leur niveau d'activité au 4e trimestre 2023 ?",
     [("note_conjoncture_T4_2023", "près de 73,8% d’entre elles")], ["73,8", "67,6"],
     "73,8 % en hausse ou stable, contre 67,6 % au trimestre précédent.", "valeur"),
    ("Q43", "Quelle proportion d'UPA a connu une amélioration de son volume d'activité au 4e trimestre 2023 ?",
     [("note_conjoncture_T4_2023", "précédent est de 72,8")], ["72,8"],
     "72,8 %.", "valeur"),
    ("Q44", "Quelle est la principale raison de la hausse des coûts de production au 3e trimestre 2022 ?",
     [("note_conjoncture_T3_2022", "56,83% des chefs d’entreprise")], ["56,83"],
     "Le prix élevé des matières premières (56,83 %).", "valeur"),
    ("Q45", "De combien les prix à la consommation ont-ils augmenté au 3e trimestre 2022 ?",
     [("note_conjoncture_T3_2022", "augmentent de 2,23%")], ["2,23", "8,54"],
     "+2,23 % sur le trimestre (huiles et graisses +8,54 %).", "valeur"),
    ("Q46", "Quelle proportion des PME estime sa trésorerie soutenable au 1er trimestre 2025 ?",
     [("note_conjoncture_T1_2025", "30,6 % des PME estiment")], ["30,6"],
     "30,6 %, en dégradation de près de 6 points.", "valeur"),
    ("Q47", "Quelle est la croissance révisée de la zone CEMAC au premier trimestre 2025 ?",
     [("note_conjoncture_T1_2025", "révisée à 2,4% au premier trimestre 2025")], ["2,4", "2,9"],
     "2,4 % (prévision initiale 2,9 %).", "valeur"),
    ("Q48", "Dans quels domaines les PME ont-elles créé des emplois au 1er trimestre 2025 ?",
     [("note_conjoncture_T1_2025", "53,5% se retrouvent dans les domaines du commerce général")], ["53,5", "29,9"],
     "Commerce général (53,5 %), BTP (29,9 %), agroalimentaire (16,6 %).", "valeur"),
    # --- Documents de contexte ---
    ("Q49", "Quelles sont les conditions d'éligibilité à la garantie de portefeuille de l'État ?",
     [("contexte_bulletin_2024", "Conditions d’éligibilité")], [],
     "Entreprise de droit camerounais à capitaux majoritairement camerounais, sans procédure collective, dans une filière prioritaire de la SND30.", "definition"),
    ("Q50", "Quelles innovations fiscales de la loi de finances 2023 favorisent l'import-substitution ?",
     [("contexte_bulletin_2023_05", "innovations fiscales et douanières de la loi de finances 2023")], [],
     "Accès au foncier, plan de soutien à la production locale, exonérations dans l'agro-industrie et le bois.", "analyse"),
    ("Q51", "Quel a été le taux d'inflation au Cameroun en 2022 selon la note de perspective sur l'inflation ?",
     [("contexte_perspective_inflation_2023", "le taux d’inflation s’est établi à 6,3%")], ["6,3", "15,3"],
     "6,3 % en 2022 ; niveau des prix +15,3 % de 2017 à 2022.", "valeur"),
    ("Q52", "Quelle est la contribution des secteurs primaire et secondaire à la croissance de 2023 ?",
     [("contexte_perspective_competitivite_pme", "0,4 pour le primaire et 0,6 pour le secondaire")], ["0,4", "0,6", "3,2"],
     "0,4 point (primaire) et 0,6 point (secondaire) sur 3,2 %.", "valeur"),
]

# Questions hors corpus : la bonne réponse est l'ABSTENTION.
HORS_CORPUS = [
    ("H01", "Quelle est la capitale de l'Australie ?"),
    ("H02", "Combien de médailles le Cameroun a-t-il remportées aux Jeux olympiques de 2024 ?"),
    ("H03", "Quel est le taux directeur de la Réserve fédérale américaine ?"),
    ("H04", "Quelle est la recette traditionnelle du ndolé ?"),
    ("H05", "Qui a remporté la Coupe d'Afrique des nations de football en 2024 ?"),
    ("H06", "Quelle est la population du Nigeria selon les Nations unies ?"),
    ("H07", "Quel est le cours de l'action Apple à la bourse de New York ?"),
    ("H08", "Combien de lits d'hôpital compte le Centre hospitalier universitaire de Yaoundé ?"),
    ("H09", "Quelle est la distance entre la Terre et la Lune ?"),
    ("H10", "Comment configurer une imprimante réseau sous Windows 11 ?"),
]


def _norm(s: str) -> str:
    s = s.replace(" ", " ").replace(" ", " ").replace("’", "'")
    s = re.sub(r"-\s*\n\s*", "-", s)
    return re.sub(r"\s+", " ", s)


def _pages(doc_id: str) -> list[str]:
    d = pymupdf.open(str(CORPUS / f"{doc_id}.pdf"))
    return [_norm(p.get_text()) for p in d]


def localiser(doc_id: str, extrait: str, cache: dict) -> list[int]:
    pages = cache.setdefault(doc_id, _pages(doc_id))
    e = _norm(extrait)
    out = []
    for i, t in enumerate(pages, start=1):
        if e in t and len(re.findall(r"(\.\s?){5,}", t)) < 5:   # pas les pages de sommaire
            out.append(i)
    return out


def construire() -> dict:
    cache: dict = {}
    questions, erreurs = [], []
    for qid, q, extraits, valeurs, rep, cat in QUESTIONS:
        pertinents = []
        for doc_id, ex in extraits:
            pages = localiser(doc_id, ex, cache)
            if not pages:
                erreurs.append(f"{qid} : extrait introuvable dans {doc_id} : {ex!r}")
                continue
            texte = " ".join(cache[doc_id][p - 1] for p in pages)
            for v in valeurs:
                if _norm(v) not in texte:
                    erreurs.append(f"{qid} : valeur {v!r} absente des pages {pages} de {doc_id}")
            pertinents.append({"doc_id": doc_id, "pages": pages})
        questions.append({"id": qid, "question": q, "pertinents": pertinents,
                          "valeurs_attendues": valeurs, "reponse_attendue": rep,
                          "categorie": cat, "hors_corpus": False, "source": "auteur",
                          "annotateur_1": "auteur", "annotateur_2": None})
    for qid, q in HORS_CORPUS:
        questions.append({"id": qid, "question": q, "pertinents": [], "valeurs_attendues": [],
                          "reponse_attendue": "Abstention : aucune source suffisante.",
                          "categorie": "hors_corpus", "hors_corpus": True, "source": "auteur",
                          "annotateur_1": "auteur", "annotateur_2": None})
    if erreurs:
        print("\n".join(erreurs))
        sys.exit(1)
    return {
        "_description": ("Jeu de questions de consultation (H1). Pertinence au niveau (document, page), "
                         "pages localisées automatiquement à partir d'extraits exacts. "
                         "source = auteur | cellule. annotateur_2 : à remplir par le second lecteur "
                         "(liste des (doc_id, page) jugés pertinents) ; kappa calculé ensuite."),
        "questions": questions,
    }


if __name__ == "__main__":
    jeu = construire()
    dest = RACINE / "data" / "gold" / "consultation.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(jeu, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(jeu["questions"])
    print(f"{n} questions écrites dans {dest} "
          f"({sum(q['hors_corpus'] for q in jeu['questions'])} hors corpus)")
