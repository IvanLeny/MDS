"""Identité visuelle : nom, couleurs, logo (config.yaml, section `interface`).

Le logo n'est jamais inventé : il est lu dans le fichier indiqué par la
configuration (assets/logo.png) s'il existe, sinon seul le nom est affiché.
Aucune ressource externe (police, icône) n'est chargée : l'interface fonctionne hors ligne.
"""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path

from .. import config

DEFAUT = {
    "nom": "ANALYS'PME",
    "sous_titre": "Assistant d'analyse des publications statistiques des PMEESA",
    "structure": "MINPMEESA — Cellule des Statistiques",
    "logo": "assets/logo.png",
    "couleurs": {"vert": "#00A35C", "vert_fonce": "#00563B", "rouge": "#E2231A", "jaune": "#FFC20E",
                 "fond_doux": "#F3F7F5", "texte": "#13261F"},
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


def _img(p: Path) -> str:
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f'<img src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" alt="logo MINPMEESA">'


def css(i: dict) -> str:
    c = i["couleurs"]
    v, vf, r, j, fd, tx = c["vert"], c["vert_fonce"], c["rouge"], c["jaune"], c["fond_doux"], c["texte"]
    return f"""
<style>
  :root {{ --ap-vert:{v}; --ap-vert-fonce:{vf}; --ap-rouge:{r}; --ap-jaune:{j}; --ap-fond:{fd}; --ap-texte:{tx};
          --ap-gris:#5E6B66; --ap-bord:#E1E8E5; --ap-ombre:0 1px 2px rgba(16,40,30,.06),0 4px 16px rgba(16,40,30,.06); }}
  html, body, [class*="css"], .stApp {{ font-family:"Segoe UI","Inter",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif; }}
  .stApp {{ background:var(--ap-fond); }}
  [data-testid="stHeader"] {{ background:transparent; }}
  .block-container {{ padding-top:2.6rem; max-width:1280px; }}
  h1, h2, h3, h4 {{ color:var(--ap-texte); letter-spacing:-.01em; }}
  h3 {{ font-weight:700; }}

  /* ---------- en-tête */
  .ap-entete {{ position:relative; display:flex; align-items:center; gap:22px; padding:18px 26px 22px 22px;
               margin:0 0 18px 0; background:#fff; border-radius:16px; box-shadow:var(--ap-ombre);
               border:1px solid var(--ap-bord); overflow:hidden; }}
  .ap-entete img {{ height:76px; width:auto; flex:none; }}
  .ap-sep {{ width:1px; align-self:stretch; background:var(--ap-bord); }}
  .ap-titres {{ flex:1; min-width:0; }}
  .ap-nom {{ font-size:2.05rem; font-weight:800; line-height:1.05; color:var(--ap-vert-fonce); letter-spacing:.3px; }}
  .ap-nom span {{ color:var(--ap-vert); }}
  .ap-sous {{ font-size:1.02rem; color:var(--ap-texte); margin-top:4px; }}
  .ap-structure {{ font-size:.82rem; color:var(--ap-gris); margin-top:3px; text-transform:uppercase; letter-spacing:.06em; }}
  .ap-badges {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; max-width:300px; }}
  .ap-badge {{ font-size:.78rem; font-weight:600; padding:5px 11px; border-radius:999px; white-space:nowrap;
              background:#E8F6EF; color:var(--ap-vert-fonce); border:1px solid #C9EBDA; }}
  .ap-drapeau {{ position:absolute; left:0; right:0; bottom:0; height:5px;
                background:linear-gradient(90deg,var(--ap-vert) 0 33.3%,var(--ap-rouge) 33.3% 66.6%,var(--ap-jaune) 66.6% 100%); }}
  @media (max-width:900px) {{ .ap-badges, .ap-sep {{ display:none; }} .ap-entete img {{ height:56px; }} .ap-nom {{ font-size:1.6rem; }} }}

  /* ---------- barre latérale */
  [data-testid="stSidebar"] {{ background:linear-gradient(180deg,var(--ap-vert-fonce) 0%,#007A4A 100%); }}
  [data-testid="stSidebar"] * {{ color:#fff; }}
  [data-testid="stSidebar"] .react-aria-ComboBox [role="group"], [data-testid="stSidebar"] [data-baseweb="select"] > div {{
      background:#fff !important; border-radius:10px; border:none; }}
  [data-testid="stSidebar"] .react-aria-ComboBox input {{ font-size:.88rem; }}
  [data-testid="stSidebar"] .react-aria-ComboBox input, [data-testid="stSidebar"] .react-aria-ComboBox svg,
  [data-testid="stSidebar"] [data-baseweb="select"] * {{ color:var(--ap-texte) !important; -webkit-text-fill-color:var(--ap-texte); }}
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ opacity:.85; }}
  [data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,.25); }}
  [data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ background:#fff; border-radius:10px; padding:4px; }}
  .ap-side-titre {{ font-size:1.35rem; font-weight:800; letter-spacing:.3px; margin:4px 0 0 0; }}
  .ap-side-sous {{ font-size:.78rem; opacity:.85; text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px; }}
  .ap-etat {{ font-size:.8rem; background:rgba(255,255,255,.12); border-radius:10px; padding:8px 10px; line-height:1.35; }}

  /* ---------- onglets (Streamlit ≥ 1.5x : react-aria ; anciens sélecteurs baseweb gardés) */
  [role="tablist"] {{ gap:6px; background:#fff; padding:6px; border-radius:14px; border:1px solid var(--ap-bord);
                     box-shadow:var(--ap-ombre); width:fit-content; max-width:100%; flex-wrap:wrap; }}
  [data-testid="stTab"], .stTabs [data-baseweb="tab"] {{ height:auto; padding:10px 20px; border-radius:10px;
      background:transparent; transition:background .15s; }}
  [data-testid="stTab"] p, .stTabs [data-baseweb="tab"] p {{ font-weight:600; color:var(--ap-gris); font-size:.95rem; }}
  [data-testid="stTab"]:hover {{ background:#EEF7F2; }}
  [data-testid="stTab"][aria-selected="true"], .stTabs [aria-selected="true"] {{ background:var(--ap-vert) !important; }}
  [data-testid="stTab"][aria-selected="true"] p, .stTabs [aria-selected="true"] p {{ color:#fff !important; }}
  .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none !important; }}
  [role="tabpanel"] {{ padding-top:20px; }}

  /* ---------- boutons */
  [data-testid="stBaseButton-primary"], button[kind="primary"] {{ background:var(--ap-vert) !important; color:#fff !important;
      border:none !important; border-radius:10px; font-weight:600; padding:.55rem 1.3rem;
      box-shadow:0 2px 8px rgba(0,163,92,.28); }}
  [data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {{ background:var(--ap-vert-fonce) !important; }}
  [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {{ border-radius:10px;
      border:1.5px solid var(--ap-vert); color:var(--ap-vert-fonce); font-weight:600; background:#fff; }}
  [data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover {{
      background:#EEF7F2; color:var(--ap-vert-fonce); border-color:var(--ap-vert-fonce); }}

  /* ---------- champs, cartes, indicateurs */
  [data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"],
  .react-aria-ComboBox [role="group"] {{ border-radius:10px; }}
  .react-aria-ComboBox [role="group"], [data-baseweb="input"] {{ background:#fff !important; border:1px solid var(--ap-bord); }}
  [data-testid="stMetric"] {{ background:#fff; border:1px solid var(--ap-bord); border-left:5px solid var(--ap-vert);
                             border-radius:12px; padding:14px 16px; box-shadow:var(--ap-ombre); }}
  [data-testid="stMetricValue"] {{ color:var(--ap-texte); font-weight:800; font-size:clamp(1.35rem,2.1vw,2.1rem); }}
  [data-testid="stMetricValue"] * {{ overflow:visible !important; text-overflow:clip !important; }}
  [data-testid="stMetricLabel"] p {{ color:var(--ap-gris); font-weight:600; }}
  [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"] {{ background:#fff; border-radius:14px;
      box-shadow:var(--ap-ombre); border-color:var(--ap-bord) !important; }}
  [data-testid="stExpander"] details {{ background:#fff; border-radius:12px; border-color:var(--ap-bord); }}
  [data-testid="stAlert"] {{ border-radius:12px; }}

  /* ---------- éléments propres au prototype */
  .ap-eyebrow {{ font-size:.75rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--ap-vert); }}
  .ap-titre-service {{ font-size:1.45rem; font-weight:750; color:var(--ap-texte); margin:2px 0 4px 0; }}
  .ap-intro {{ color:var(--ap-gris); margin-bottom:14px; max-width:820px; }}
  .ap-enonce {{ display:flex; gap:12px; align-items:flex-start; background:#fff; border:1px solid var(--ap-bord);
               border-radius:12px; padding:12px 14px; margin:8px 0 2px 0; box-shadow:0 1px 2px rgba(16,40,30,.04); }}
  .ap-tag {{ flex:none; font-size:.68rem; font-weight:800; letter-spacing:.07em; padding:4px 8px; border-radius:6px; margin-top:2px; }}
  .ap-tag.constat {{ background:#E3F5EC; color:var(--ap-vert-fonce); }}
  .ap-tag.perspective {{ background:#FFF4D1; color:#7A5600; }}
  .ap-enonce-texte {{ color:var(--ap-texte); line-height:1.5; }}
  .ap-sources {{ font-size:.8rem; color:var(--ap-gris); margin:0 0 6px 14px; }}
  .ap-pied {{ margin-top:36px; padding:14px 0 6px 0; border-top:1px solid var(--ap-bord); font-size:.8rem; color:var(--ap-gris); }}
</style>"""


def bandeau(i: dict) -> str:
    lg = logo(i)
    img = (_img(lg) + '<div class="ap-sep"></div>') if lg else ""
    nom = escape(i["nom"])
    if nom.upper().endswith("PME"):                 # « ANALYS'PME » : PME en vert vif
        nom = f"{nom[:-3]}<span>{nom[-3:]}</span>"
    badges = "".join(f'<div class="ap-badge">{b}</div>' for b in
                     ("Chiffres sourcés", "Contrôle de citation", "Fonctionne hors ligne"))
    return (f'<div class="ap-entete">{img}<div class="ap-titres"><div class="ap-nom">{nom}</div>'
            f'<div class="ap-sous">{escape(i["sous_titre"])}</div>'
            f'<div class="ap-structure">{escape(i["structure"])}</div></div>'
            f'<div class="ap-badges">{badges}</div><div class="ap-drapeau"></div></div>')


def entete_service(numero: int, titre: str, intro: str) -> str:
    return (f'<div class="ap-eyebrow">Service {numero}</div><div class="ap-titre-service">{escape(titre)}</div>'
            f'<div class="ap-intro">{escape(intro)}</div>')


def enonce(type_: str, texte: str, sources: list[str]) -> str:
    t = "perspective" if type_ == "perspective" else "constat"
    src = f'<div class="ap-sources">Sources : {escape(" ; ".join(sources))}</div>' if sources else ""
    return (f'<div class="ap-enonce"><span class="ap-tag {t}">{t.upper()}</span>'
            f'<div class="ap-enonce-texte">{escape(texte)}</div></div>{src}')


def pied(i: dict) -> str:
    return (f'<div class="ap-pied">{escape(i["nom"])} — {escape(i["structure"])}. Prototype de recherche : chaque chiffre '
            f'renvoie à sa source ; aucune donnée ne quitte le poste en exploitation.</div>')
