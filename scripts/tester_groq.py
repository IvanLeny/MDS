"""Test rapide du moteur `api` (Groq) : un seul appel, quelques secondes.

    python scripts/tester_groq.py

Vérifie que la clé GROQ_API_KEY est lue et que le service répond. N'affiche jamais la clé.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from minpmeesa import config  # noqa: E402
from minpmeesa.generation.llm import ErreurLLM, client_api  # noqa: E402

cfg = config.charger()
try:
    c = client_api(cfg)
except ErreurLLM as e:
    print("ÉCHEC :", e)
    sys.exit(1)
print("Clé lue. Moteur :", c.nom)
try:
    r = c.generer("Réponds uniquement en JSON.", 'Renvoie exactement {"ok": true, "langue": "français"}.')
except ErreurLLM as e:
    print("ÉCHEC de l'appel :", e)
    print("Vérifiez la connexion Internet, la validité de la clé (console.groq.com) et le pare-feu.")
    sys.exit(1)
print("Réponse du service :", r)
print("OK : le moteur api fonctionne. Vous pouvez lancer : python -m minpmeesa.evaluation.run_all --llm api")
