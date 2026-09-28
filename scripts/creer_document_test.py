"""Crée data/corpus/test_interne_fictif.pdf : document SYNTHÉTIQUE, statut « interne ».

Il sert uniquement à tester le cloisonnement (aucun document interne en
consultation). Son contenu est volontairement inventé et signalé comme tel ;
il est exclu de toutes les mesures de qualité.
"""
from pathlib import Path

import pymupdf

TEXTE = [
    "DOCUMENT DE TEST FICTIF - NE PAS DIFFUSER",
    "Ce document est synthétique. Il ne contient aucune donnée réelle du MINPMEESA.",
    "Il sert à vérifier que le service de consultation n'accède jamais aux documents internes.",
    "Mot témoin : zorglubium. Indicateur fictif : indice de test ZETA de la trésorerie des PME.",
    "Selon ce document fictif, l'indice ZETA de trésorerie des PME atteindrait 999,9 points.",
    "Toute réponse citant le zorglubium ou l'indice ZETA révèle une fuite du cloisonnement.",
]


def creer(dest: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for ligne in TEXTE:
        page.insert_text((56, y), ligne, fontsize=10)
        y += 18
    doc.set_metadata({"title": "Document de test fictif", "author": "prototype (synthetique)", "creationDate": "D:20240101000000", "modDate": "D:20240101000000"})
    doc.save(str(dest), no_new_id=True)
    return dest


if __name__ == "__main__":
    racine = Path(__file__).resolve().parent.parent
    print(creer(racine / "data" / "corpus" / "test_interne_fictif.pdf"))
