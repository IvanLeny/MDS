"""Test rapide du moteur `api` (Groq) : un seul appel, quelques secondes.

    python scripts/tester_groq.py                 # teste le modèle de config.yaml
    python scripts/tester_groq.py --lister        # liste les modèles disponibles pour votre clé
    python scripts/tester_groq.py --modele NOM    # teste un autre modèle

N'affiche jamais la clé.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from minpmeesa import config  # noqa: E402
from minpmeesa.generation.llm import ErreurLLM, client_api  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--lister", action="store_true")
ap.add_argument("--modele", default=None)
a = ap.parse_args()
cfg = config.charger()
try:
    c = client_api(cfg, a.modele)
except ErreurLLM as e:
    print("ÉCHEC :", e)
    sys.exit(1)

if a.lister:
    req = urllib.request.Request(f"{c.url}/models", headers={
        "Authorization": f"Bearer {c._cle}", "Accept": "application/json",
        "User-Agent": "minpmeesa-prototype/5.1 (evaluation memoire ISSEA)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            modeles = sorted(m["id"] for m in json.loads(r.read())["data"])
    except urllib.error.HTTPError as e:
        print("ÉCHEC :", e.code, e.read().decode("utf-8", "replace")[:300])
        sys.exit(1)
    print("Modèles disponibles pour votre clé :")
    for m in modeles:
        marque = "  <- famille Llama (poids ouverts)" if "llama" in m.lower() else ""
        print(" -", m + marque)
    sys.exit(0)

print("Clé lue. Moteur :", c.nom)
try:
    r = c.generer("Réponds uniquement en JSON.", 'Renvoie exactement {"ok": true, "langue": "français"}.')
except ErreurLLM as e:
    m = str(e)
    print("ÉCHEC de l'appel :", m)
    if "401" in m:
        print("-> Clé refusée : vérifiez-la sur console.groq.com (ou créez-en une nouvelle).")
    elif "403" in m:
        print("-> Accès refusé : pare-feu/proxy, VPN, ou pays non desservi. Essayez un autre réseau.")
    elif "404" in m or "model_not_found" in m:
        print("-> Modèle indisponible : lancez  python scripts\\tester_groq.py --lister")
    else:
        print("Vérifiez la connexion Internet, la validité de la clé et le pare-feu.")
    sys.exit(1)
print("Réponse du service :", r)
print("OK : le moteur api fonctionne. Vous pouvez lancer : python -m minpmeesa.evaluation.run_all --llm api")
