@echo off
REM Lance l interface locale dans le navigateur (aucun acces reseau requis).
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist data\base\minpmeesa.sqlite (
  echo Premiere utilisation : construction de la base, quelques minutes...
  python -m minpmeesa.ingestion.build --silencieux
)
python -m streamlit run minpmeesa\app\streamlit_app.py --browser.gatherUsageStats false --server.address 127.0.0.1
pause
