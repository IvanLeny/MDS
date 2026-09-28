"""Service 1 : consultation de la base (BF8, section 3.2.5).

Question libre -> 5 passages sourcés (document, page, extrait), ou abstention
« Aucune source suffisante trouvée dans les publications » si le meilleur
score est sous le seuil calibré (consultation.seuil_abstention).
Seuls les documents « publie » sont consultables (filtre dans la requête).
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from .. import config
from .hybrid import Recherche

MESSAGE_ABSTENTION = "Aucune source suffisante trouvée dans les publications."


@dataclass
class Source:
    passage_id: int
    doc_id: str
    titre: str
    type: str
    exercice: int
    page: int
    section: str
    nature: str
    extrait: str
    score: float


@dataclass
class ReponseConsultation:
    question: str
    abstention: bool
    message: str
    sources: List[Source] = field(default_factory=list)
    signal: float = 0.0
    seuil: float = 0.0
    duree_s: float = 0.0
    reponse_redigee: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def extrait(texte: str, question: str, n: int = 420) -> str:
    """Extrait centré sur les mots de la question."""
    from .text import plat, tokens
    t = " ".join(texte.split())
    p = plat(t)
    positions = [p.find(m) for m in tokens(question) if len(m) > 3 and p.find(m) >= 0]
    debut = max(0, min(positions) - 120) if positions else 0
    s = t[debut:debut + n]
    return ("… " if debut else "") + s + (" …" if debut + n < len(t) else "")


def consulter(recherche: Recherche, question: str, mode: str = "hybride",
              journal: bool = True, filtres: Optional[dict] = None) -> ReponseConsultation:
    t0 = time.time()
    seuil = float(config.get("consultation.seuil_abstention"))
    signal = recherche.score_bm25_brut(question)
    res = recherche.chercher(question, mode=mode, filtres=filtres)
    rep = ReponseConsultation(question=question, abstention=False, message="", signal=round(signal, 3),
                              seuil=seuil)
    if signal < seuil or not res:
        rep.abstention, rep.message = True, MESSAGE_ABSTENTION
    else:
        rows = recherche.base.passages([r.passage_id for r in res])
        for r, row in zip(res, rows):
            assert row["statut_diffusion"] == "publie"          # garde-fou du cloisonnement
            rep.sources.append(Source(row["passage_id"], row["doc_id"], row["titre"], row["type"],
                                      row["exercice"], row["page"], row["section"], row["nature"],
                                      extrait(row["texte"], question), round(r.score, 5)))
        rep.message = f"{len(rep.sources)} passages trouvés."
    rep.duree_s = round(time.time() - t0, 3)
    if journal:
        recherche.base.journaliser(
            "consultation", {"question": question, "mode": mode}, rep.message,
            sources=[{"doc_id": s.doc_id, "page": s.page, "passage_id": s.passage_id} for s in rep.sources],
            abstentions=[rep.message] if rep.abstention else [],
            modele=getattr(recherche.dense, "nom", "") or "bm25", config_hash=config.config_hash(),
            duree_s=rep.duree_s)
    return rep
