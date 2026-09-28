#!/usr/bin/env bash
# Lance l'interface locale dans le navigateur (aucun accès réseau requis).
cd "$(dirname "$0")"
[ -d .venv ] && source .venv/bin/activate
if [ ! -f data/base/minpmeesa.sqlite ]; then
  echo "Première utilisation : construction de la base (quelques minutes)..."
  python -m minpmeesa.ingestion.build --silencieux
fi
python -m streamlit run minpmeesa/app/streamlit_app.py --server.headless false --browser.gatherUsageStats false --server.address 127.0.0.1
