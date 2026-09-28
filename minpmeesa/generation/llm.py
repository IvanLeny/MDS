"""Client du modèle de langage local (Tableau 3.2) : Ollama, ou llama-cpp-python en repli.

Température 0, graine fixe, délai maximal. Aucun appel réseau hors de la
machine : Ollama est joint sur l'adresse locale (127.0.0.1) uniquement.
Si aucun moteur n'est disponible, les services basculent en mode EXTRACTIF
(gabarits déterministes), signalé dans toute sortie.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse


class ErreurLLM(RuntimeError):
    pass


class ClientLLM:
    nom = ""

    def generer(self, systeme: str, utilisateur: str, json_attendu: bool = True) -> str:
        raise NotImplementedError


class Ollama(ClientLLM):
    def __init__(self, modele: str, url: str, temperature: float = 0, delai: float = 180, graine: int = 42):
        hote = urlparse(url).hostname
        if hote not in ("127.0.0.1", "localhost", "::1"):
            raise ErreurLLM(f"Ollama doit être local (adresse reçue : {hote})")
        self.nom, self.url, self.t, self.delai, self.graine = f"ollama:{modele}", url.rstrip("/"), temperature, delai, graine
        self.modele = modele

    def disponible(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
                noms = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
            return any(n == self.modele or n.split(":")[0] == self.modele.split(":")[0] and self.modele in n
                       for n in noms) or self.modele in noms
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def generer(self, systeme, utilisateur, json_attendu=True):
        corps = {"model": self.modele, "stream": False,
                 "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
                 "options": {"temperature": self.t, "seed": self.graine}}
        if json_attendu:
            corps["format"] = "json"
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.delai) as r:
                return json.loads(r.read())["message"]["content"]
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            raise ErreurLLM(f"Ollama : {e}") from e


class LlamaCpp(ClientLLM):
    def __init__(self, chemin_gguf: str, temperature: float = 0, graine: int = 42):
        from llama_cpp import Llama
        self.nom = f"llamacpp:{chemin_gguf}"
        self._m = Llama(model_path=chemin_gguf, n_ctx=8192, seed=graine, verbose=False)
        self.t = temperature

    def generer(self, systeme, utilisateur, json_attendu=True):
        kw = {"response_format": {"type": "json_object"}} if json_attendu else {}
        r = self._m.create_chat_completion(
            messages=[{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
            temperature=self.t, **kw)
        return r["choices"][0]["message"]["content"]


def obtenir(cfg: dict, moteur: str | None = None, modele: str | None = None) -> tuple[ClientLLM | None, str]:
    """(client, explication). Client None = mode extractif (sans modèle de langage)."""
    l = cfg["llm"]
    moteur = moteur or l["moteur"]
    if moteur == "none":
        return None, "mode sans modèle de langage (--llm none)"
    if moteur == "ollama":
        c = Ollama(modele or l["modele"], l["url"], l["temperature"], l["delai_max_s"], cfg["graine"])
        if c.disponible():
            return c, c.nom
        moteur = "llamacpp"
        raison = f"Ollama indisponible ou modèle {modele or l['modele']} absent"
    else:
        raison = ""
    if moteur == "llamacpp":
        from .. import config
        g = config.RACINE / l["gguf"]
        try:
            if g.exists():
                c = LlamaCpp(str(g), l["temperature"], cfg["graine"])
                return c, c.nom
            raison = (raison + " ; " if raison else "") + f"fichier GGUF absent ({l['gguf']})"
        except ImportError:
            raison = (raison + " ; " if raison else "") + "llama-cpp-python non installé"
    return None, f"repli en mode extractif : {raison}"
