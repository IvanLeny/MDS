"""Captures d'écran des 4 parcours (Annexe III), automatisées avec Playwright.

Prérequis : l'interface tourne (./demarrer.sh ou streamlit run ...) sur le port 8501.
    python scripts/captures.py [--url http://127.0.0.1:8501]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

DEST = Path(__file__).resolve().parent.parent / "data" / "outputs" / "captures"


def attendre(page, ms=1500):
    page.wait_for_timeout(ms)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180000)
    page.wait_for_timeout(ms)


def main(url: str):
    DEST.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        import glob, os
        exe = os.environ.get("CHROMIUM") or next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        nav = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = nav.new_page(viewport={"width": 1400, "height": 1100})
        page.goto(url)
        page.wait_for_selector(".ap-nom", timeout=180000)
        attendre(page, 3000)
        # 1. Consulter
        page.get_by_placeholder("Ex. : Combien").fill("Combien de PME ont été créées dans les CFCE en 2024 ?")
        page.keyboard.press("Enter")
        page.wait_for_selector("text=Temps de réponse", timeout=180000)
        attendre(page)
        page.screenshot(path=str(DEST / "1_consulter.png"), full_page=True)
        # 2. Commenter
        page.get_by_role("tab", name="Commenter un indicateur").click()
        attendre(page)
        page.get_by_role("button", name="Rédiger le commentaire").click()
        page.wait_for_selector("text=Sources", timeout=300000)
        attendre(page)
        page.screenshot(path=str(DEST / "2_commenter.png"), full_page=True)
        # 3. Note d'analyse
        page.get_by_role("tab", name="Note d'analyse").click()
        attendre(page)
        page.get_by_role("button", name="Rédiger la note d'analyse").click()
        page.wait_for_selector("text=Tableau 1 :", timeout=600000)
        attendre(page)
        page.screenshot(path=str(DEST / "3_note_analyse.png"), full_page=False)
        # 4. Note stratégique
        page.get_by_role("tab", name="Note stratégique").click()
        attendre(page)
        page.get_by_role("button", name="Rédiger la note stratégique").click()
        page.wait_for_selector("text=Pistes pour la décision", timeout=600000)
        attendre(page)
        page.screenshot(path=str(DEST / "4_note_strategique.png"), full_page=True)
        nav.close()
    print(sorted(str(x) for x in DEST.glob("*.png")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8501")
    main(ap.parse_args().url)
