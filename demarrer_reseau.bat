@echo off
REM Lance ANALYS'PME pour tout le reseau local de la Cellule (les collegues l'ouvrent dans leur navigateur).
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist data\base\minpmeesa.sqlite (
  echo Premiere utilisation : construction de la base, quelques minutes...
  python -m minpmeesa.ingestion.build --silencieux
)
echo.
echo Adresse a communiquer aux collegues (adresse IPv4 de ce poste, port 8501) :
setlocal enabledelayedexpansion
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (set ip=%%a& echo    http://!ip: =!:8501)
endlocal
echo.
python -m streamlit run minpmeesa\app\streamlit_app.py --browser.gatherUsageStats false --server.address 0.0.0.0 --server.port 8501
pause
