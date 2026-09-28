"""Tableaux -> triplets (valeur, ligne, colonne) + unité (section 3.2.2).

Reprise de l'ancien `src/ingestion/tables.py` (en-têtes sur plusieurs niveaux,
remplissage des cellules fusionnées, millésimes traités comme en-têtes et non
comme données), complétée pour les défauts observés dans les Annuaires :
  - libellé de ligne placé sur une rangée distincte de ses valeurs (centrage
    vertical des cellules fusionnées) ;
  - libellés hiérarchiques (ex. « Yaoundé » puis « Primaire ») ;
  - rangées décalées (ex. ligne « Total » dont les valeurs glissent d'une
    colonne) : réalignées dans l'ordre quand leur nombre correspond ;
  - intitulé « Tableau N : ... » lu au-dessus du cadre, unité tirée de
    l'intitulé ou de la sous-colonne « % » ;
  - tableau poursuivi sur la page suivante : l'intitulé précédent est repris.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

from .extract import Ligne

_ANNEE = re.compile(r"\b(20\d{2}|19\d{2})\b")
_NOMBRE = re.compile(r"^[-+]?\(?\d[\d\s  .,]*\)?\s*%?$")
_LEGENDE = re.compile(r"^Tableau\s+(\d+)\s*[:.\-–]\s*(.*)$", re.I)


@dataclass
class Triplet:
    ligne: str
    colonne: str
    valeur_texte: str
    annee_colonne: int | None
    sous_colonne: str
    unite: str | None


@dataclass
class TableauExtrait:
    page: int
    numero: int | None
    intitule: str
    bbox: tuple[float, float, float, float]
    triplets: list[Triplet] = field(default_factory=list)
    suite: bool = False                # tableau poursuivi depuis la page précédente
    source: str = ""

    def texte_linearise(self) -> list[str]:
        """Énoncés élémentaires « ligne | colonne = valeur »."""
        out = []
        for t in self.triplets:
            u = f" {t.unite}" if t.unite and t.unite != "%" and t.unite not in t.colonne else ""
            out.append(f"{t.ligne} | {t.colonne} = {t.valeur_texte}{u}")
        return out


def _c(s) -> str:
    return "" if s is None else re.sub(r"\s+", " ", str(s).replace("\n", " ")).strip()


def est_nombre(s: str) -> bool:
    s = s.strip()
    return bool(s) and bool(_NOMBRE.match(s)) and any(ch.isdigit() for ch in s)


def est_millesime(s: str) -> bool:
    s = re.sub(r"\(\s*e\s*\)|\*", "", s).strip()
    return bool(re.fullmatch(r"(19|20)\d{2}", s))


def est_valeur(s: str) -> bool:
    return est_nombre(s) and not est_millesime(s)


def valeur_num(s: str) -> float | None:
    """Conversion d'une écriture française (« 12 500 », « 7,8 », « 79,6 % »)."""
    t = s.replace(" ", " ").replace(" ", " ").replace("%", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def unite_intitule(intitule: str) -> str | None:
    m = re.search(r"\(\s*en\s+([^)]*)\)", intitule, re.I)
    if m:
        u = m.group(1).strip()
        return "%" if u.startswith("%") else u
    if re.search(r"\(\s*%\s*\)", intitule):
        return "%"
    if re.search(r"en\s+millions?\s+de\s+(francs\s+)?f?cfa", intitule, re.I):
        return "millions de FCFA"
    return None


# ------------------------------------------------------------ linéarisation
def lineariser(rangees: list[list], unite_titre: str | None = None) -> list[Triplet]:
    """Transforme la grille brute de PyMuPDF en triplets."""
    g = [[_c(c) if c is not None else None for c in r] for r in rangees]
    g = [r for r in g if any(c for c in r)]
    if not g:
        return []
    ncol = max(len(r) for r in g)
    g = [r + [None] * (ncol - len(r)) for r in g]
    # Colonnes entièrement vides : retirées.
    garder = [j for j in range(ncol) if any(r[j] for r in g)]
    g = [[r[j] for j in garder] for r in g]
    ncol = len(garder)

    def n_val(r):
        return sum(1 for c in r if c and est_valeur(c))

    # Rangées d'en-tête : celles qui précèdent la première rangée porteuse de valeurs.
    prof = 0
    for r in g:
        if n_val(r) >= 1 and not all(est_millesime(c) or not c for c in r[1:] if c):
            break
        prof += 1
    prof = min(prof, 4)
    entetes, donnees = g[:prof], g[prof:]

    # Colonnes de libellés : majoritairement du texte non numérique dans les données.
    col_lib = []
    for j in range(ncol):
        cel = [r[j] for r in donnees if r[j]]
        if cel and sum(1 for c in cel if not est_nombre(c)) / len(cel) >= 0.6:
            col_lib.append(j)
        else:
            break
    if not col_lib:
        col_lib = [0]
    col_val = [j for j in range(ncol) if j not in col_lib
               and sum(1 for r in donnees if r[j] and est_valeur(r[j])) >= max(1, 0.3 * len(donnees))]

    # Chemins de colonne : en-têtes remplis horizontalement (cellules fusionnées).
    remplis = []
    for r in entetes:
        out, der = [], ""
        for j, c in enumerate(r):
            if c:
                der = c
            out.append(c if c else (der if j not in col_lib else ""))
        remplis.append(out)
    chemins = {}
    for j in range(ncol):
        parts = []
        for r in remplis:
            v = r[j]
            if v and v not in parts:
                parts.append(v)
        chemins[j] = " · ".join(parts)

    # Rattachement des libellés placés sur une rangée distincte des valeurs.
    lignes = []                        # (libellés, valeurs par colonne)
    en_attente = None                  # rangée de valeurs sans libellé
    lib_orphelin = None                # libellé sans valeurs
    hier = [""] * len(col_lib)
    for r in donnees:
        libs = [r[j] or "" for j in col_lib]
        vals = {j: r[j] for j in range(ncol) if j not in col_lib and r[j] and est_valeur(r[j])}
        a_lib = any(libs)
        if vals and a_lib:
            lignes.append([libs, vals])
            en_attente = None
        elif vals and not a_lib:
            if lib_orphelin:
                lignes.append([lib_orphelin, vals])
                lib_orphelin = None
            else:
                en_attente = [[""] * len(col_lib), vals]
                lignes.append(en_attente)
        elif a_lib and not vals:
            if en_attente is not None and not any(en_attente[0]):
                en_attente[0] = libs
                en_attente = None
            else:
                lib_orphelin = libs
    # Libellés hiérarchiques : le niveau supérieur se propage vers le bas.
    triplets = []
    n_vc = len(col_val)
    for libs, vals in lignes:
        for k, v in enumerate(libs):
            if v:
                hier[k] = v
                for kk in range(k + 1, len(hier)):
                    hier[kk] = ""
        libelle = " / ".join(x for x in hier if x) or "(sans libellé)"
        # Réalignement d'une rangée décalée (même nombre de valeurs que de colonnes).
        if n_vc and len(vals) == n_vc and set(vals) != set(col_val):
            vals = dict(zip(col_val, [vals[j] for j in sorted(vals)]))
        for j, v in sorted(vals.items()):
            chem = chemins.get(j, "")
            annees = _ANNEE.findall(chem)
            annee = int(annees[-1]) if annees else None
            sous = re.sub(r"(19|20)\d{2}\s*(\(\s*e\s*\))?", "", chem).strip(" ·")
            sous = sous.split(" · ")[-1].strip() if sous else ""
            unite = "%" if ("%" in sous or v.endswith("%")) else unite_titre
            triplets.append(Triplet(libelle, chem or f"colonne {j + 1}", v, annee, sous, unite))
    return triplets


# ------------------------------------------------------------ par les mots
_MOT_NUM = re.compile(r"^[-+]?\(?\d[\d.,]*\)?%?$")


def _mots_en_cellules(mots: list) -> list[dict]:
    """Regroupe les mots d'une même ligne visuelle : « 202 » + « 746 » -> « 202 746 »,
    « 79,6 » + « % » -> « 79,6 % » ; les libellés contigus forment une phrase."""
    mots = sorted(mots, key=lambda w: w[0])
    cel: list[dict] = []
    for x0, y0, x1, y1, t in mots:
        h = y1 - y0
        if cel:
            c = cel[-1]
            ecart = x0 - c["x1"]
            num_prec = c["num"]
            if (num_prec and ecart < 0.45 * h and re.fullmatch(r"\d{3}([.,]\d+)?%?", t)
                    and "," not in c["t"] and re.search(r"\d{1,3}$", c["t"])):
                c["t"] += " " + t; c["x1"] = x1; continue
            if num_prec and t == "%" and ecart < 0.6 * h:
                c["t"] += " %"; c["x1"] = x1; continue
            if (not num_prec and not _MOT_NUM.match(t) and ecart < 0.6 * h):
                c["t"] += " " + t; c["x1"] = x1; continue
            # Nombre collé à un libellé (« Moins de 20 ans ») : partie du libellé.
            if ecart < 0.45 * h and (not num_prec) != (not _MOT_NUM.match(t)) and c["t"][-1:].isalpha() | t[:1].isalpha():
                c["t"] += " " + t; c["x1"] = x1; c["num"] = False; c["lib"] = True; continue
            if c["t"].strip() and re.fullmatch(r"(19|20)\d{2}", c["t"]) and t.startswith("(") and ecart < 0.6 * h:
                c["t"] += " " + t; c["x1"] = x1; c["num"] = False; continue
        cel.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1, "t": t,
                    "num": bool(_MOT_NUM.match(t)) and not re.fullmatch(r"(19|20)\d{2}", t)})
    for c in cel:
        c["cx"] = (c["x0"] + c["x1"]) / 2
        c["cy"] = (c["y0"] + c["y1"]) / 2
        c["num"] = (not c.get("lib")) and est_valeur(c["t"])
    return cel


def _lignes_visuelles(mots: list, tol: float = 2.5) -> list[list]:
    lignes: list[list] = []
    for w in sorted(mots, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        if lignes and abs(cy - lignes[-1][0]) <= tol:
            lignes[-1][1].append(w)
        else:
            lignes.append([cy, [w]])
    return [l[1] for l in lignes]


def _grappes(xs: list[float], ecart: float) -> list[list[float]]:
    xs = sorted(xs)
    g: list[list[float]] = []
    for x in xs:
        if g and x - g[-1][-1] <= ecart:
            g[-1].append(x)
        else:
            g.append([x])
    return g


def lineariser_mots(mots: list, unite_titre: str | None = None) -> list[Triplet]:
    """Reconstruit un tableau à partir de la position des mots dans son cadre.

    - colonnes de valeurs = grappes des abscisses des valeurs numériques ;
    - en-tête = lignes situées au-dessus de la première ligne de valeurs ;
      chaque colonne prend le millésime et la sous-colonne les plus proches ;
    - libellés = texte à gauche de la première colonne de valeurs, rattaché à la
      ligne de valeurs la plus proche verticalement (cellules centrées) ;
      libellés hiérarchiques (niveau 0 couvrant plusieurs lignes) propagés.
    """
    lignes = [_mots_en_cellules(l) for l in _lignes_visuelles(
        [(w[0], w[1], w[2], w[3], w[4]) for w in mots])]
    lignes = [l for l in lignes if l]
    idx_val = [i for i, l in enumerate(lignes) if sum(c["num"] for c in l) >= 1]
    if len(idx_val) < 1:
        return []
    # Colonnes de valeurs.
    xs = [c["cx"] for i in idx_val for c in lignes[i] if c["num"]]
    larg = sorted(c["x1"] - c["x0"] for i in idx_val for c in lignes[i] if c["num"])
    ecart = max(8.0, larg[len(larg) // 2] * 0.9)
    colonnes = [sum(g) / len(g) for g in _grappes(xs, ecart)
                if len(g) >= max(1, 0.25 * len(idx_val)) or len(idx_val) <= 2]
    if not colonnes:
        return []
    x_premiere = min(c["x0"] for i in idx_val for c in lignes[i] if c["num"])
    premiere = idx_val[0]
    # En-têtes (au-dessus de la première ligne de valeurs, hors zone des libellés).
    tetes = [c for l in lignes[:premiere] for c in l]
    tetes_val = [c for c in tetes if c["x1"] > x_premiere - 4]
    annees = [c for c in tetes_val if _ANNEE.search(c["t"])]
    sous = [c for c in tetes_val if not _ANNEE.search(c["t"]) and not c["num"]]
    pas = min((b - a for a, b in zip(colonnes, colonnes[1:])), default=60.0)

    def entete(cx: float) -> tuple[str, int | None, str]:
        a = min(annees, key=lambda c: abs(c["cx"] - cx), default=None)
        if a and abs(a["cx"] - cx) > 1.6 * pas:
            a = None
        s_cand = [c for c in sous if c["x0"] - 3 <= cx <= c["x1"] + 3]
        if not s_cand:
            s_cand = [c for c in sous if abs(c["cx"] - cx) < 0.5 * pas]
        s = " ".join(c["t"] for c in sorted(s_cand, key=lambda c: (c["cy"], c["x0"])))
        annee = int(_ANNEE.findall(a["t"])[-1]) if a else None
        chemin = " · ".join(x for x in [a["t"] if a else "", s] if x)
        return chemin, annee, s

    # Libellés : texte à gauche des valeurs, rattaché à la ligne de valeurs la plus proche.
    # Un libellé sur deux lignes peut commencer au-dessus de la première ligne de valeurs.
    hauteurs = sorted(c["y1"] - c["y0"] for l in lignes for c in l)
    h_ligne = hauteurs[len(hauteurs) // 2] if hauteurs else 10.0
    cy0 = min(c["cy"] for c in lignes[premiere] if c["num"])
    debut_lib = premiere
    while debut_lib > 0 and all(not _ANNEE.search(c["t"]) for c in lignes[debut_lib - 1]) \
            and min(c["cy"] for c in lignes[debut_lib - 1]) >= cy0 - 1.6 * h_ligne \
            and all(c["x1"] <= x_premiere + 2 for c in lignes[debut_lib - 1]):
        debut_lib -= 1
    libs = [c for l in lignes[debut_lib:] for c in l if not c["num"] and c["x1"] <= x_premiere + 2]
    libs += [c for l in lignes[premiere:] for c in l
             if c["num"] is False and est_millesime(c["t"]) and c["x1"] <= x_premiere + 2 and c not in libs]
    rangs = [(i, lignes[i]) for i in idx_val if i >= premiere]
    cy_rang = [sum(c["cy"] for c in l if c["num"]) / max(1, sum(c["num"] for c in l)) for _, l in rangs]
    niveaux = _grappes([c["x0"] for c in libs], 12.0)
    hier = False
    if len(niveaux) >= 2:
        n0 = [c for c in libs if c["x0"] <= niveaux[0][-1] + 0.1]
        n1 = [c for c in libs if c not in n0]
        hier = len({round(c["cy"]) for c in n0}) < 0.6 * len(rangs) and len(n1) >= 0.6 * len(rangs)
        if hier:
            # Vraie hiérarchie : la ligne la plus proche d'un libellé de niveau 0
            # porte elle-même un libellé de niveau 1 (le niveau 0 couvre un groupe).
            # Sinon, ce n'est qu'un retrait typographique : un seul niveau.
            def rang_proche(c):
                return min(range(len(rangs)), key=lambda k: abs(cy_rang[k] - c["cy"]))
            rangs_n1 = {rang_proche(c) for c in n1}
            hier = sum(rang_proche(c) in rangs_n1 for c in n0) >= 0.6 * len(n0)
    else:
        n0, n1 = libs, []
    if not hier:
        n0, n1 = libs, []

    def plus_proche(c) -> int:
        return min(range(len(rangs)), key=lambda k: abs(cy_rang[k] - c["cy"]))

    etiq = [[] for _ in rangs]
    etiq0 = [None] * len(rangs)
    if hier:
        for k in range(len(rangs)):
            cands = [c for c in n0 if c["cy"] <= cy_rang[k] + 30]
            # le libellé de niveau 0 le plus proche verticalement
            if n0:
                etiq0[k] = min(n0, key=lambda c: abs(c["cy"] - cy_rang[k]))["t"]
        for c in n1:
            etiq[plus_proche(c)].append(c)
    else:
        for c in n0:
            etiq[plus_proche(c)].append(c)

    triplets = []
    entetes = {j: entete(cx) for j, cx in enumerate(colonnes)}
    for k, (_, l) in enumerate(rangs):
        lib = " ".join(c["t"] for c in sorted(etiq[k], key=lambda c: (c["cy"], c["x0"])))
        if hier and etiq0[k]:
            lib = f"{etiq0[k]} / {lib}" if lib else etiq0[k]
        lib = lib or "(sans libellé)"
        annee_ligne = int(lib) if re.fullmatch(r"(19|20)\d{2}", lib) else None
        for c in (c for c in l if c["num"]):
            j = min(range(len(colonnes)), key=lambda j: abs(colonnes[j] - c["cx"]))
            chemin, annee, sous_col = entetes[j]
            unite = "%" if ("%" in sous_col or c["t"].endswith("%")) else unite_titre
            if unite and unite != "%" and re.match(r"(stock|nombre|effectif)", lib, re.I):
                unite = None           # ligne de dénombrement dans un tableau monétaire
            triplets.append(Triplet(lib, chemin or f"colonne {j + 1}", c["t"],
                                    annee if annee else annee_ligne, sous_col, unite))
    return triplets


# ------------------------------------------------------------ par page
def legendes_page(lignes: list[Ligne]) -> list[tuple[int, str, float]]:
    """Légendes « Tableau N : ... » de la page : (numéro, intitulé, y)."""
    out = []
    lignes = sorted(lignes, key=lambda l: (l.y0, l.x0))
    for i, l in enumerate(lignes):
        m = _LEGENDE.match(l.texte)
        if not m:
            continue
        titre = m.group(2).strip()
        # L'intitulé peut continuer sur la ligne suivante.
        if i + 1 < len(lignes):
            s = lignes[i + 1]
            if (0 < s.y0 - l.y1 < 6 and not _LEGENDE.match(s.texte) and len(s.texte) < 90
                    and not est_nombre(s.texte) and not s.texte.lower().startswith("source")):
                titre = f"{titre} {s.texte}"
        out.append((int(m.group(1)), titre.strip(" ."), l.y0))
    return out


def extraire_page(page: pymupdf.Page, numero_page: int, lignes: list[Ligne],
                  dernier: tuple) -> list[TableauExtrait]:
    """Tableaux d'une page, avec leur intitulé.

    `dernier` = (numéro, intitulé, page) du dernier tableau vu : repris seulement
    pour un tableau sans légende en haut de la page qui suit (tableau scindé)."""
    try:
        trouves = page.find_tables().tables
    except Exception:
        return []
    legendes = legendes_page(lignes)
    out = []
    for t in sorted(trouves, key=lambda t: t.bbox[1]):
        rangees = t.extract()
        # Légende la plus proche au-dessus du cadre.
        cand = [(n, tit, y) for n, tit, y in legendes if y <= t.bbox[1] + 5]
        if cand:
            n, tit, _ = max(cand, key=lambda c: c[2])
            suite = False
        elif (dernier and len(dernier) == 3 and dernier[2] == numero_page - 1
              and t.bbox[1] < page.rect.height * 0.3):
            n, tit = dernier[0], dernier[1]
            suite = True
        else:
            n, tit, suite = None, "", False
        x0, y0, x1, y1 = t.bbox
        mots = [w for w in page.get_text("words")
                if w[0] >= x0 - 2 and w[2] <= x1 + 2 and w[1] >= y0 - 2 and w[3] <= y1 + 2]
        trip = lineariser_mots(mots, unite_intitule(tit or ""))
        if not trip:                   # repli : grille de PyMuPDF
            trip = lineariser(rangees, unite_intitule(tit or ""))
        if len(trip) < 2:              # cadre décoratif ou bloc isolé
            continue
        source = next((l.texte for l in sorted(lignes, key=lambda l: l.y0)
                       if l.y0 >= t.bbox[3] - 2 and l.texte.lower().startswith("source")), "")
        out.append(TableauExtrait(numero_page, n, tit or "", tuple(t.bbox), trip, suite, source))
        dernier = (n, tit, numero_page)
    return out
