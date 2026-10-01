"""Étape 4 : variations, contrôle littéral, service Commentaire, filtre temporel, JSON, réseau."""
import json
import socket

import pytest

from minpmeesa.compute import variations as V
from minpmeesa.generation import commentary as cm
from minpmeesa.generation.llm import ClientLLM
from minpmeesa.guards import literal_check as lc
from minpmeesa.retrieval import indicator_context as ic

STATUTS = ["valide", "candidat"]
CODE = "pme-creees-sur-periode"           # graphique 4 (2024) <-> tableau 7 : PME créées dans les CFCE


# ------------------------------------------------------------ variations
def test_variation_arrondi_convention():
    va, vat, vr, vrt = V.calculer(21132, "21 132", 19651, "19 651")
    assert (va, vat) == (1481, "1 481")
    assert (vr, vrt) == (7.5, "7,5")                 # 7,536… -> 1 décimale


def test_variation_arrondi_demi_superieur():
    assert V.calculer(1.05, "1,05", 1.0, "1,00")[3] == "5,0"
    assert V.arrondir(0.25, 1) == 0.3 and V.arrondir(-0.25, 1) == -0.3


def test_variation_reference_nulle():
    va, vat, vr, vrt = V.calculer(5, "5", 0, "0")
    assert (va, vr, vrt) == (5, None, None)


def test_variation_parts_en_points():
    va, vat, vr, vrt = V.calculer(77.2, "77,2", 79.6, "79,6")
    assert vat == "-2,4" and vrt == "-3,0"


def test_variation_valeur_manquante(base_complete):
    # aucune variation n'est produite pour un indicateur sans tableau apparié
    assert V.variations_indicateur(base_complete, "code-inexistant", 2024) == []


def test_variations_tracent_deux_valeurs_sources(base_complete):
    r = base_complete.execute("SELECT * FROM variations WHERE code_indicateur=? AND exercice=2024 "
                              "AND exercice_ref=2023 AND ligne='Total'", (CODE,)).fetchone()
    assert r["var_rel_texte"] == "7,5"
    v, vr = (base_complete.execute("SELECT valeur_texte, annee_colonne FROM valeurs WHERE valeur_id=?", (i,)).fetchone()
             for i in (r["valeur_id"], r["valeur_ref_id"]))
    assert (v[0], v[1], vr[0], vr[1]) == ("21 132", 2024, "19 651", 2023)


# ------------------------------------------------------------ filtre temporel
def test_filtre_temporel_aucune_fuite(base_complete):
    ctx = ic.construire(base_complete, CODE, 2024, STATUTS, nb_modeles=10)
    assert ctx.modeles, "des commentaires antérieurs doivent servir de modèles"
    assert all(m["exercice"] < 2024 for m in ctx.modeles)
    docs = {v["doc_id"] for v in ctx.valeurs}
    assert docs == {"annuaire_2024"}
    assert all((v["annee_colonne"] or 0) <= 2024 for v in ctx.valeurs)
    ctx23 = ic.construire(base_complete, CODE, 2023, STATUTS, nb_modeles=10)
    assert all(m["exercice"] < 2023 for m in ctx23.modeles)
    assert {v["doc_id"] for v in ctx23.valeurs} == {"annuaire_2023"}


def test_contexte_trois_rubriques(base_complete):
    r = ic.construire(base_complete, CODE, 2024, STATUTS).rendu()
    assert ic.RUBRIQUE_VALEURS in r and ic.RUBRIQUE_VARIATIONS in r and ic.RUBRIQUE_MODELES in r
    assert r.index(ic.RUBRIQUE_VALEURS) < r.index(ic.RUBRIQUE_VARIATIONS) < r.index(ic.RUBRIQUE_MODELES)


# ------------------------------------------------------------ contrôle littéral
class Faux(ClientLLM):
    """Modèle de langage simulé : renvoie des réponses préparées."""
    nom = "faux"

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = 0

    def generer(self, systeme, utilisateur, json_attendu=True):
        self.appels += 1
        return self.reponses.pop(0) if self.reponses else ""


def _json(*enonces):
    return json.dumps({"enonces": [{"type": t, "texte": x, "valeurs": []} for t, x in enonces]}, ensure_ascii=False)


def test_valeur_inventee_ecartee_valeur_calculee_acceptee(base_complete):
    rep = _json(("constat", "En 2024, les CFCE ont enregistré 21 132 PME, soit une hausse de 7,5 % par rapport à 2023."),
                ("constat", "Ce total dépasserait 25 000 PME dans les régions."),
                ("perspective", "Les créations pourraient atteindre 30 000 PME en 2025."))
    r = cm.commenter(base_complete, CODE, 2024, Faux([rep]), journaliser=False)
    assert not r["abstention"]
    textes = [e["texte"] for e in r["enonces"]]
    assert textes[0].startswith("En 2024, les CFCE ont enregistré 21 132 PME, soit une hausse de 7,5 %")
    ecartees = {e["valeur"] for e in r["valeurs_ecartees"]}
    assert ecartees == {"25 000", "30 000"}                  # perspective contrôlée aussi
    natures = {s["valeur"]: s["nature"] for s in r["enonces"][0]["sources"]}
    assert natures == {"21 132": "valeur", "7,5": "variation"}


def test_valeur_d_un_modele_anterieur_ecartee(base_complete):
    ctx = ic.construire(base_complete, CODE, 2024, STATUTS)
    modele = " ".join(ctx.textes_modeles())
    aut = {x["texte"] for x in ctx.autorisees()}
    # un chiffre des commentaires antérieurs absent des valeurs autorisées de 2024
    candidat = next(n for n in lc.nombres(modele) if not lc.trouver(n, lc.index_autorise(ctx.autorisees())))
    rep = _json(("constat", f"Le nombre de créations s'établit à {candidat} unités sur la période."))
    r = cm.commenter(base_complete, CODE, 2024, Faux([rep]), journaliser=False)
    assert candidat in {e["valeur"] for e in r["valeurs_ecartees"]}
    assert all(e["dans_modele"] for e in r["valeurs_ecartees"] if e["valeur"] == candidat)


def test_json_invalide_une_nouvelle_tentative_puis_abstention(base_complete):
    f = Faux(["ceci n'est pas du JSON", "{toujours pas"])
    r = cm.commenter(base_complete, CODE, 2024, f, journaliser=False)
    assert f.appels == 2 and r["abstention"] and "JSON invalide" in r["motif"]
    assert r["mention"] == "sources insuffisantes, à commenter manuellement"


def test_json_invalide_puis_valide(base_complete):
    f = Faux(["pas du json", _json(("constat", "En 2024, les CFCE ont enregistré 21 132 PME."))])
    r = cm.commenter(base_complete, CODE, 2024, f, journaliser=False)
    assert f.appels == 2 and not r["abstention"]


def test_abstention_du_modele(base_complete):
    r = cm.commenter(base_complete, CODE, 2024, Faux(['{"abstention": "données insuffisantes"}']), journaliser=False)
    assert r["abstention"] and "données insuffisantes" in r["motif"]


def test_abstention_sans_appariement(base_complete):
    r = cm.commenter(base_complete, "indicateur-inexistant", 2024, None, journaliser=False)
    assert r["abstention"] and r["mention"] == "sources insuffisantes, à commenter manuellement"


def test_mode_extractif_signale_et_entierement_source(base_complete):
    r = cm.commenter(base_complete, CODE, 2024, None, journaliser=False)
    assert r["mode_extractif"] and r["modele"] == cm.MODE_EXTRACTIF
    assert r["valeurs_ecartees"] == []
    assert all(s["nature"] in ("valeur", "variation", "libellé") for e in r["enonces"] for s in e["sources"])
    assert r["provisoire"] is True        # appariement non encore validé


def test_journal_des_productions(base_complete):
    n0 = base_complete.execute("SELECT COUNT(*) FROM productions").fetchone()[0]
    cm.commenter(base_complete, CODE, 2024, None, journaliser=True)
    assert base_complete.execute("SELECT COUNT(*) FROM productions").fetchone()[0] == n0 + 1


# ------------------------------------------------------------ réseau
def test_aucun_appel_reseau_sortant(base_complete, monkeypatch):
    """Consultation et commentaire ne tentent aucune connexion hors de la machine."""
    tentatives = []
    original = socket.socket.connect

    def connect(self, adresse):
        hote = adresse[0] if isinstance(adresse, tuple) else str(adresse)
        if hote not in ("127.0.0.1", "localhost", "::1"):
            tentatives.append(hote)
            raise OSError(f"appel réseau interdit vers {hote}")
        return original(self, adresse)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection",
                        lambda addr, *a, **k: (_ for _ in ()).throw(OSError(f"interdit {addr}"))
                        if addr[0] not in ("127.0.0.1", "localhost", "::1") else socket.socket().connect(addr))
    from minpmeesa.retrieval import consultation, hybrid
    m = hybrid.Moteur()
    consultation.consulter("Combien de PME ont été créées dans les CFCE en 2024 ?", m, journaliser=False)
    cm.commenter(base_complete, CODE, 2024, None, journaliser=False)
    assert tentatives == []


def test_ollama_refuse_une_adresse_distante():
    from minpmeesa.generation.llm import ErreurLLM, Ollama
    with pytest.raises(ErreurLLM):
        Ollama("qwen", "http://exemple.org:11434")


def test_a1_variation_tracee_vers_la_bonne_ligne(base_complete):
    """A1 : 7,5 % est la variation de trois lignes (Total, Yaoundé, Douala) ; « ce total » -> Total."""
    from minpmeesa.generation import commentary
    r = commentary.commenter(base_complete, "pme-creees-sur-periode", 2024, journaliser=False)
    e = next(e for e in r["enonces"] if "ce total" in e["texte"])
    assert e["references"][0]["libelle"].startswith("variation calculée (var_rel_pct) : Total,")


def test_a1_trouver_prefere_le_libelle_cite():
    from minpmeesa.guards import literal_check as lc
    aut = [{"texte": "7,5", "source": {"nature": "variation", "ligne": "Yaoundé", "exercice_ref": 2023}},
           {"texte": "7,5", "source": {"nature": "variation", "ligne": "Douala", "exercice_ref": 2023}},
           {"texte": "7,5", "source": {"nature": "variation", "ligne": "Total", "exercice_ref": 2023}}]
    idx = lc.index_autorise(aut)
    t = "Par rapport à 2023, « Douala » progresse de 7,5 %."
    assert lc.trouver("7,5", idx, t, t.index("7,5"))["ligne"] == "Douala"
    t = "Par rapport à 2023, ce total progresse de 7,5 %."
    assert lc.trouver("7,5", idx, t, t.index("7,5"))["ligne"] == "Total"
    assert lc.trouver("7,5", idx)["ligne"] == "Yaoundé"          # sans phrase : ordre de priorité


def test_a2_a3_a4_grandeur_unite_dimension(base_complete):
    """A2 : indicateur de VA -> on parle de la VA, pas du stock ; A3 : nature précisée ; A4 : dimension nommée."""
    from minpmeesa.generation import commentary
    r = commentary.commenter(base_complete, "pme-typologie", 2024, journaliser=False)
    txt = commentary.texte(r)
    assert "VA des PME" in txt and "Stock des PME" not in txt
    assert "millions de Francs CFA" in txt and "de la valeur ajoutée" in txt
    r = commentary.commenter(base_complete, "upa-enregistrees-dans-bureaux-communaux-region", 2024, journaliser=False)
    assert "répartition par sexe" in commentary.texte(r)
