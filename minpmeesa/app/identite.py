"""Identité visuelle : nom, couleurs, logo (config.yaml, section `interface`).

Le logo n'est jamais inventé : il est lu dans le fichier indiqué par la
configuration (assets/logo.png) s'il existe, sinon seul le nom est affiché.
"""
from __future__ import annotations

import base64
from pathlib import Path

from .. import config

DEFAUT = {
    "nom": "ANALYS'PME",
    "sous_titre": "Assistant d'analyse des publications statistiques des PMEESA",
    "structure": "MINPMEESA — Cellule des Statistiques",
    "logo": "assets/logo.png",
    "couleurs": {"vert": "#007A5E", "rouge": "#CE1126", "jaune": "#FCD116",
                 "fond_doux": "#F2F7F5", "texte": "#1F2A2E"},
}


def charger() -> dict:
    i = {**DEFAUT, **(config.charger().get("interface") or {})}
    i["couleurs"] = {**DEFAUT["couleurs"], **(i.get("couleurs") or {})}
    return i


def logo(i: dict | None = None) -> Path | None:
    i = i or charger()
    p = Path(i["logo"])
    p = p if p.is_absolute() else config.RACINE / p
    return p if p.is_file() else None


def css(i: dict) -> str:
    c = i["couleurs"]
    return f"""
<style>
  .ap-bandeau {{ display:flex; align-items:center; gap:18px; padding:14px 20px; margin:-8px 0 14px 0;
                 background:{c['fond_doux']}; border-radius:10px; border-left:6px solid {c['vert']}; }}
  .ap-bandeau img {{ height:64px; width:auto; }}
  .ap-nom {{ font-size:1.9rem; font-weight:800; color:{c['vert']}; letter-spacing:.5px; line-height:1.1; }}
  .ap-sous {{ font-size:1rem; color:{c['texte']}; margin-top:2px; }}
  .ap-structure {{ font-size:.85rem; color:#5b6770; margin-top:2px; }}
  .ap-drapeau {{ height:5px; border-radius:3px; margin:-6px 0 18px 0;
                 background:linear-gradient(90deg,{c['vert']} 0 33.3%,{c['rouge']} 33.3% 66.6%,{c['jaune']} 66.6% 100%); }}
  .ap-pied {{ margin-top:32px; padding-top:8px; border-top:1px solid #dde3e6; font-size:.8rem; color:#6b767d; }}
  [data-testid="stSidebar"] {{ border-right:4px solid {c['vert']}; }}
  .stTabs [aria-selected="true"] {{ color:{c['vert']} !important; }}
  .stTabs [data-baseweb="tab-highlight"] {{ background-color:{c['rouge']} !important; }}
</style>"""


def bandeau(i: dict) -> str:
    lg = logo(i)
    img = (f'<img src="data:image/png;base64,{base64.b64encode(lg.read_bytes()).decode()}" alt="logo">'
           if lg else "")
    return (f'<div class="ap-bandeau">{img}<div><div class="ap-nom">{i["nom"]}</div>'
            f'<div class="ap-sous">{i["sous_titre"]}</div><div class="ap-structure">{i["structure"]}</div>'
            f'</div></div><div class="ap-drapeau"></div>')


def pied(i: dict) -> str:
    return (f'<div class="ap-pied">{i["nom"]} — {i["structure"]}. Prototype de recherche : chaque chiffre '
            f'renvoie à sa source ; aucune donnée ne quitte le poste en exploitation.</div>')
