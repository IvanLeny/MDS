"""Mise en forme « rapport » des productions : titres, sous-titres et paragraphes rédigés.

Les énoncés restent ceux qui ont passé le contrôle de citation : on ne fait que les ASSEMBLER
(ordre, enchaînement, suppression de l'intitulé répété, qui ne contient aucune valeur) et regrouper
leurs sources. Aucun chiffre n'est ajouté, modifié ou recalculé ici ; le détail énoncé par énoncé
reste disponible pour la vérification.
"""
from __future__ import annotations

import re

from ..guards.provenance import nom_document

_SIGLES = {"PME", "PMEESA", "MINPMEESA", "OES", "UPA", "UPI", "CGA", "CFCE", "TCAM", "BC-PME", "BSTP-CAM",
           "PNPE", "CTD", "VA", "ESS"}
_ACCENTS = {"donnees": "données", "developpement": "développement", "economie": "économie",
            "economique": "économique", "economiques": "économiques", "general": "général",
            "generale": "générale", "evolution": "évolution", "creation": "création", "secteur": "secteur",
            "activite": "activité", "activites": "activités", "strategique": "stratégique"}
_ROMAINS = re.compile(r"^(?:chapitre\s+)?([IVXLC]+)\s*[:.\-–]\s*(.+)$", re.I)


def phrase(t: str) -> str:
    """« DONNEES STATISTIQUES SUR LES PME » -> « Données statistiques sur les PME »."""
    mots = []
    for m in re.split(r"(\s+)", t.strip()):
        nu = m.strip("(),.;:")
        if nu.upper() in _SIGLES:
            mots.append(m.upper())
        elif m.isspace():
            mots.append(m)
        else:
            mots.append(_ACCENTS.get(m.lower(), m.lower()))
    s = "".join(mots)
    return s[:1].upper() + s[1:]


def titre_chapitre(ch: str | None) -> str:
    if not ch:
        return "Indicateurs"
    m = _ROMAINS.match(ch.strip())
    return f"Chapitre {m.group(1).upper()} — {phrase(m.group(2))}" if m else phrase(ch)


def titre_section(se: str | None) -> str | None:
    if not se or se.startswith("("):
        return None
    return re.sub(r"\s+", " ", se).strip()


def _sans_intitule(t: str) -> str:
    # le titre du tableau est déjà le sous-titre : « En 2024, pour « … », le total… » -> « En 2024, le total… »
    return re.sub(r"^(En \d{4}), pour « [^»]+ », ", r"\1, ", t)


_SUR_LE_TOTAL = re.compile(r"(le total s'établit à|^Par rapport à \d{4}, ce total|^Depuis \d{4}, la (hausse|baisse|variation) cumulée)")


def paragraphe(com: dict, deja_dit: dict[str, int] | None = None, tableau_n: int | None = None) -> str:
    """Les énoncés contrôlés d'un commentaire, en un paragraphe (constats, puis perspective).
    `deja_dit` : phrases sur le total déjà écrites dans la même section (-> tableau où elles figurent) ;
    elles ne sont pas répétées, un renvoi les remplace."""
    if com.get("abstention"):
        return ""
    cons, deja, renvoi = [], set(), None
    textes = [_sans_intitule(e["texte"]) for e in com.get("enonces", []) if e.get("type") != "perspective"]
    niveau = next((t for t in textes if "le total s'établit à" in t), None)
    if deja_dit is not None and niveau:
        if niveau in deja_dit:            # même total qu'un tableau précédent de la section : on n'y revient pas
            renvoi = deja_dit[niveau]
        else:
            deja_dit[niveau] = tableau_n
    for t in textes:
        if renvoi and _SUR_LE_TOTAL.search(t):
            continue
        if renvoi and not cons:
            cons.append(f"Ce tableau porte sur le même total que le tableau {renvoi}.")
        m = re.match(r"Par rapport à (\d{4}), ", t)
        if m and m.group(1) in deja:          # « Par rapport à 2023 » une seule fois par paragraphe
            reste = t[m.end():]
            t = "Sur la même période, " + reste
        elif m:
            deja.add(m.group(1))
        cons.append(t)
    pers = [e["texte"] for e in com.get("enonces", []) if e.get("type") == "perspective"]
    return " ".join(cons + pers)


def source(com: dict) -> str:
    """« Source : Annuaire 2024, tableau 4 (p. 18) ; évolutions calculées à partir des valeurs publiées. »"""
    tabs, variation = {}, False
    for e in com.get("enonces", []):
        for r in e.get("references", []):
            if r.get("nature") == "variation":
                variation = True
            for v in r.get("valeurs_sources") or []:
                if v:
                    tabs.setdefault((v["doc_id"], v["tableau_n"]), set()).add(v["page"])
    if not tabs:
        return ""
    lib = " ; ".join(f"{nom_document(d)}, tableau {t} (p. {'-'.join(map(str, sorted(p)))})"
                     for (d, t), p in sorted(tabs.items(), key=lambda x: (x[0][0], x[0][1] or 0)))
    return f"Source : {lib}" + (" ; évolutions calculées à partir des valeurs publiées." if variation else ".")


def structurer_note_analyse(note: dict) -> dict:
    """Plan du rapport : introduction, principaux enseignements, chapitres > sections > tableaux, annexes."""
    ex = note["exercice"]
    if "—" in note["titre"]:
        o = note["titre"].split("—", 1)[-1].strip()
        objet = ("l'" if o[:1].lower() in "aeiouéèêh" else "le ") + o
    else:
        objet = f"les tableaux de l'exercice {ex}"
    chapitres: list[dict] = []
    for s in note["sections"]:
        tc = titre_chapitre(s.get("chapitre"))
        if not chapitres or chapitres[-1]["titre"] != tc:
            chapitres.append({"titre": tc, "sections": []})
        ts = titre_section(s.get("section"))
        secs = chapitres[-1]["sections"]
        if not secs or secs[-1]["titre"] != ts:
            secs.append({"titre": ts, "tableaux": []})
        secs[-1].setdefault("_dit", {})
        secs[-1]["tableaux"].append({
            "titre": f"Tableau {s['tableau_n']} — {s['intitule']}", "tableau_n": s["tableau_n"],
            "transition": s.get("transition"),
            "paragraphe": paragraphe(s["commentaire"], secs[-1]["_dit"], s["tableau_n"]),
            "source": source(s["commentaire"]), "valide": s.get("valide")})
    n_tab = sum(len(se["tableaux"]) for c in chapitres for se in c["sections"])
    noms_ch = [(lambda x: x[:1].lower() + x[1:])(re.sub(r"^Chapitre [IVXLC]+ — ", "", c["titre"]))
               for c in chapitres]
    manuels = list(dict.fromkeys(a["tableau_n"] for a in note.get("abstentions", [])))
    intro = (f"La présente note analyse {objet}. Elle commente {n_tab} tableaux, répartis en "
             f"{len(chapitres)} chapitre{'s' if len(chapitres) > 1 else ''} : {', '.join(noms_ch)}. "
             "Chaque chiffre cité est repris de l'Annuaire ; les évolutions sont calculées à partir des valeurs "
             "publiées, et chaque paragraphe indique le tableau et la page dont il provient.")
    if manuels:
        intro += (f" {len(manuels)} tableau{'x' if len(manuels) > 1 else ''}, dont la structure ne se prête pas "
                  "à un commentaire automatique, sont signalés en annexe pour un commentaire par la Cellule.")
    # Principaux enseignements : pour chaque section, le niveau et l'évolution de son premier tableau
    # (phrases déjà contrôlées, reprises telles quelles)
    enseignements = []
    for c in chapitres:
        for se in c["sections"]:
            for t in se["tableaux"]:
                com = next(s["commentaire"] for s in note["sections"] if s["tableau_n"] == t["tableau_n"])
                txt = " ".join(e["texte"] for e in com.get("enonces", []))
                niv = re.search(r"s'établit à ([^.]+?)\.(?:\s|$)", txt)
                evo = re.search(rf"Par rapport à {ex - 1}, [^,.]*?(progresse|recule) de ([\d ,]+) %", txt)
                if niv and evo:
                    sujet = re.sub(r"^\d+(\.\d+)*\.?\s*", "", se["titre"] or t["titre"])
                    sens = "en hausse" if evo.group(1) == "progresse" else "en baisse"
                    enseignements.append(f"{sujet} : {niv.group(1)} en {ex}, {sens} de {evo.group(2)} % "
                                         f"par rapport à {ex - 1} (tableau {t['tableau_n']}).")
                    break
    return {"titre": note["titre"], "date": note.get("date"), "exercice": ex, "introduction": intro,
            "enseignements": enseignements, "chapitres": chapitres,
            "manuels": list({a["tableau_n"]: a for a in reversed(note.get("abstentions", []))}.values())[::-1],
            "incoherences": note.get("incoherences", [])}


def structurer_commentaire(res: dict) -> dict:
    return {"titre": res.get("indicateur") or res.get("tableau_intitule"),
            "paragraphe": paragraphe(res), "source": source(res)}


def html_note_analyse(doc: dict, avertissements: list[str]) -> str:
    """Rapport au format page (interface)."""
    from html import escape as e
    h = [f'<div class="ap-doc"><div class="ap-doc-titre">{e(doc["titre"])}</div>',
         f'<div class="ap-doc-meta">Établie le {e(doc.get("date") or "")} — ANALYS\'PME, MINPMEESA</div>']
    if avertissements:
        h.append('<div class="ap-doc-avert">' + "<br>".join(e(a) for a in avertissements) + "</div>")
    h.append(f'<h2>Introduction</h2><p>{e(doc["introduction"])}</p>')
    if doc["enseignements"]:
        h.append("<h2>Principaux enseignements</h2><ul>" +
                 "".join(f"<li>{e(x)}</li>" for x in doc["enseignements"]) + "</ul>")
    for c in doc["chapitres"]:
        h.append(f"<h2>{e(c['titre'])}</h2>")
        for se in c["sections"]:
            if se["titre"]:
                h.append(f"<h3>{e(se['titre'])}</h3>")
            for t in se["tableaux"]:
                h.append(f"<h4>{e(t['titre'])}</h4>")
                if t.get("transition"):
                    h.append(f"<p>{e(t['transition'])}</p>")
                h.append(f"<p>{e(t['paragraphe'])}</p>")
                if t["source"]:
                    h.append(f'<p class="ap-doc-source">{e(t["source"])}</p>')
    if doc["manuels"] or doc["incoherences"]:
        h.append("<h2>Annexes</h2>")
    if doc["manuels"]:
        h.append("<h3>A. Tableaux à commenter par la Cellule</h3><ul>" + "".join(
            f"<li>Tableau {a['tableau_n']} — {e(a.get('intitule') or a['code'])}</li>" for a in doc["manuels"]) + "</ul>")
    if doc["incoherences"]:
        h.append("<h3>B. Contrôle de cohérence de l'Annuaire</h3><ul>")
        for inc in doc["incoherences"]:
            det = " ; ".join(f"{ref} (tableau(x) {', '.join(map(str, n))})" for ref, n in inc["references"].items())
            h.append(f"<li>Pour un même total {inc['exercice']} ({e(inc['total'])}), la valeur "
                     f"{inc['exercice'] - 1} diffère selon le tableau : {e(det)}.</li>")
        h.append("</ul>")
    h.append("</div>")
    return "".join(h)


def html_commentaire(res: dict) -> str:
    from html import escape as e
    c = structurer_commentaire(res)
    src = f'<p class="ap-doc-source">{e(c["source"])}</p>' if c["source"] else ""
    return f'<div class="ap-doc ap-doc-court"><h4>{e(c["titre"] or "")}</h4><p>{e(c["paragraphe"])}</p>{src}</div>'
