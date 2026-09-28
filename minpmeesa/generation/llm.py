"""Client du modèle de langage local (section 3.1.3).

  - ollama    : serveur Ollama sur la boucle locale (127.0.0.1), format JSON,
                température 0, graine fixe, délai maximal ;
  - llama_cpp : repli sans serveur, fichier .gguf local (llama-cpp-python) ;
  - none      : pas de modèle ; les services passent en mode extractif
                (gabarits déterministes), signalé dans toute sortie.
Aucun appel ne sort de la machine : l'hôte Ollama doit être local.
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

from .. import config

MODE_EXTRACTIF = "extractif (sans modèle de langage)"


class LLMIndisponible(RuntimeError):
    pass


@dataclass
class ReponseLLM:
    texte: str
    duree_s: float
    modele: str


class ClientLLM:
    def __init__(self, moteur: Optional[str] = None, modele: Optional[str] = None):
        self.moteur = (moteur or config.get("llm.moteur")).lower()
        self.modele = modele or config.get("llm.modele")
        self.hote = config.get("llm.hote")
        self.temperature = float(config.get("llm.temperature", 0))
        self.max_tokens = int(config.get("llm.max_tokens", 700))
        self.delai = float(config.get("llm.delai_max_s", 180))
        self.graine = int(config.get("graine", 42))
        self._llama = None
        if self.moteur == "ollama":
            h = urlparse(self.hote).hostname or ""
            if h not in ("127.0.0.1", "localhost", "::1"):
                raise ValueError(f"hôte Ollama non local refusé : {self.hote}")

    @property
    def actif(self) -> bool:
        return self.moteur != "none"

    @property
    def nom(self) -> str:
        return MODE_EXTRACTIF if not self.actif else f"{self.moteur}:{self.modele}"

    def disponible(self) -> bool:
        if self.moteur == "none":
            return False
        if self.moteur == "ollama":
            try:
                with urllib.request.urlopen(self.hote.rstrip("/") + "/api/tags", timeout=3) as r:
                    tags = json.loads(r.read().decode("utf-8"))
                return any(m.get("name", "").startswith(self.modele.split(":")[0]) for m in tags.get("models", []))
            except Exception:
                return False
        if self.moteur == "llama_cpp":
            try:
                import llama_cpp  # noqa: F401
                from pathlib import Path
                return bool(config.get("llm.gguf")) and Path(config.get("llm.gguf")).exists()
            except ImportError:
                return False
        return False

    def generer(self, systeme: str, messages: List[dict], json_attendu: bool = True) -> ReponseLLM:
        if self.moteur == "none":
            raise LLMIndisponible("aucun modèle de langage configuré (mode extractif)")
        t0 = time.time()
        msgs = [{"role": "system", "content": systeme}] + messages
        if self.moteur == "ollama":
            texte = self._ollama(msgs, json_attendu)
        elif self.moteur == "llama_cpp":
            texte = self._llama_cpp(msgs, json_attendu)
        else:
            raise ValueError(f"moteur inconnu : {self.moteur}")
        return ReponseLLM(texte, round(time.time() - t0, 3), self.nom)

    def _ollama(self, msgs, json_attendu) -> str:
        charge = {"model": self.modele, "messages": msgs, "stream": False,
                  "options": {"temperature": self.temperature, "seed": self.graine,
                              "num_predict": self.max_tokens}}
        if json_attendu:
            charge["format"] = "json"
        req = urllib.request.Request(self.hote.rstrip("/") + "/api/chat",
                                     data=json.dumps(charge).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.delai) as r:
                return json.loads(r.read().decode("utf-8"))["message"]["content"]
        except Exception as e:
            raise LLMIndisponible(f"Ollama injoignable ou délai dépassé : {e}") from e

    def _llama_cpp(self, msgs, json_attendu) -> str:
        if self._llama is None:
            from llama_cpp import Llama
            self._llama = Llama(model_path=config.get("llm.gguf"), n_ctx=8192, seed=self.graine,
                                verbose=False)
        kw = {"response_format": {"type": "json_object"}} if json_attendu else {}
        out = self._llama.create_chat_completion(messages=msgs, temperature=self.temperature,
                                                 max_tokens=self.max_tokens, **kw)
        return out["choices"][0]["message"]["content"]


def client(moteur: Optional[str] = None, modele: Optional[str] = None) -> ClientLLM:
    """Client configuré ; bascule sur le mode extractif si le moteur demandé
    n'est pas joignable (le repli est signalé dans les sorties)."""
    c = ClientLLM(moteur, modele)
    if c.actif and not c.disponible():
        return ClientLLM("none")
    return c
