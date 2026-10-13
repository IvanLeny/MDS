@echo off
REM Cree deux raccourcis sur le bureau, avec le logo du MINPMEESA :
REM   - "ANALYS'PME" : lance la version locale (demarrer.bat) ;
REM   - "ANALYS'PME (en ligne)" : ouvre la version de demonstration dans le navigateur.
REM A lancer une seule fois (double-clic). Les raccourcis restent valables tant que le dossier MDS ne bouge pas.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bureau = [Environment]::GetFolderPath('Desktop');" ^
  "$dossier = (Get-Location).Path;" ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "$s = $w.CreateShortcut((Join-Path $bureau 'ANALYS''PME.lnk'));" ^
  "$s.TargetPath = (Join-Path $dossier 'demarrer.bat');" ^
  "$s.WorkingDirectory = $dossier;" ^
  "$s.IconLocation = (Join-Path $dossier 'assets\logo.ico');" ^
  "$s.Description = 'ANALYS''PME - version locale (MINPMEESA, Cellule des Statistiques)';" ^
  "$s.WindowStyle = 7;" ^
  "$s.Save();" ^
  "$u = Join-Path $bureau 'ANALYS''PME (en ligne).url';" ^
  "Set-Content -Path $u -Encoding ASCII -Value @('[InternetShortcut]','URL=https://analyspme-minpmeesa.streamlit.app/',('IconFile=' + (Join-Path $dossier 'assets\logo.ico')),'IconIndex=0');" ^
  "Write-Host ('Raccourcis crees sur le bureau : ' + $bureau)"
pause
