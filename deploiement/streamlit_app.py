"""Point d'entrée de la version de démonstration en ligne (Streamlit Community Cloud).

- active le mode démonstration (MINPMEESA_DEMO=1) : consultation seule, rédaction par gabarits ;
- construit la base au premier démarrage (corpus public du dépôt, encodeur hors ligne), une seule fois ;
- lance ensuite l'interface habituelle (minpmeesa/app/streamlit_app.py).

Sur le poste de la Cellule, on n'utilise pas ce fichier : voir docs/DEPLOIEMENT.md.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
os.chdir(RACINE)
os.environ.setdefault("MINPMEESA_DEMO", "1")

import streamlit as st  # noqa: E402


@st.cache_resource(show_spinner="Premier démarrage : construction de la base documentaire (3 à 5 minutes)…")
def base_prete() -> bool:
    from minpmeesa.store import db
    if not db.chemin_base().exists():
        from minpmeesa.ingestion.build import construire
        construire(verbeux=False)
    return True


base_prete()
runpy.run_path(str(RACINE / "minpmeesa" / "app" / "streamlit_app.py"), run_name="__main__")
