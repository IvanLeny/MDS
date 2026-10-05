"""Client du modèle de langage (Tableau 3.2) : une interface, deux moteurs.

- `ollama` : moteur CIBLE, local (127.0.0.1), sans réseau — gpt-oss:20b ;
- `api`    : service distant compatible OpenAI (Groq), pendant le DÉVELOPPEMENT seulement,
             avec les mêmes poids ouverts (openai/gpt-oss-20b) pour que les résultats
             restent transposables au déploiement local ;
- `llamacpp` : repli local (fichier GGUF) ; `none` : mode extractif (gabarits), signalé.

Température 0 et graine fixe. Le moteur `api` lit sa clé dans une variable
d'environnement, respecte les en-têtes de limite de débit (ralentit, met les appels
en file plutôt que de les perdre), refait jusqu'à 3 essais en cas de coupure réseau
(attente croissante) et garde un cache disque des réponses réussies.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

LOCAUX = ("127.0.0.1", "localhost", "::1")


class ErreurLLM(RuntimeError):
    pass


class ClientLLM:
    nom = ""          # « moteur:modèle », enregistré dans chaque sortie
    moteur = ""
    modele = ""

    def generer(self, systeme: str, utilisateur: str, json_attendu: bool = True) -> str:
        raise NotImplementedError


# ------------------------------------------------------------------ Ollama (cible)
class Ollama(ClientLLM):
    moteur = "ollama"

    def __init__(self, modele: str, url: str, temperature: float = 0, delai: float = 180, graine: int = 42,
                 num_ctx: int | None = None):
        hote = urlparse(url).hostname
        if hote not in LOCAUX:
            raise ErreurLLM(f"Ollama doit être local (adresse reçue : {hote})")
        self.modele, self.url, self.t, self.delai, self.graine = modele, url.rstrip("/"), temperature, delai, graine
        self.num_ctx = num_ctx
        self.nom = f"ollama:{modele}"

    def disponible(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
                noms = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
        except (urllib.error.URLError, OSError, ValueError):
            return False
        cible = self.modele if ":" in self.modele else f"{self.modele}:latest"
        return cible in noms or self.modele in noms

    def generer(self, systeme, utilisateur, json_attendu=True):
        corps = {"model": self.modele, "stream": False,
                 "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
                 "options": {"temperature": self.t, "seed": self.graine}}
        if self.num_ctx:                 # fenêtre explicite : un contexte tronqué ferait perdre les consignes
            corps["options"]["num_ctx"] = self.num_ctx
        if json_attendu:
            corps["format"] = "json"
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.delai) as r:
                return json.loads(r.read())["message"]["content"]
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            raise ErreurLLM(f"Ollama : {e}") from e


# ------------------------------------------------------------------ API compatible OpenAI (développement)
def _duree(s: str | None) -> float | None:
    """Durée d'un en-tête de réinitialisation : « 2m59.56s », « 7.66s », « 120ms », « 3 »."""
    if not s:
        return None
    s = str(s).strip()
    try:
        return float(s)
    except ValueError:
        pass
    total, ok = 0.0, False
    for n, u in re.findall(r"([\d.]+)\s*(ms|h|m|s)", s):
        total += float(n) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[u]
        ok = True
    return total if ok else None


class ClientAPI(ClientLLM):
    """Point d'accès compatible OpenAI (/chat/completions). Clé lue dans l'environnement."""
    moteur = "api"
    _verrou = threading.Lock()      # file d'attente : un appel à la fois, dans l'ordre

    def __init__(self, url: str, modele: str, cle_env: str, fournisseur: str = "groq",
                 temperature: float = 0, delai: float = 60, graine: int = 42, essais: int = 3,
                 attente_base: float = 2.0, intervalle_min: float = 0.0, cache: Path | None = None,
                 dormir=time.sleep):
        cle = os.environ.get(cle_env)
        if not cle:
            raise ErreurLLM(f"clé API absente : définir la variable d'environnement {cle_env}")
        self._cle = cle
        self.url, self.modele, self.fournisseur = url.rstrip("/"), modele, fournisseur
        self.nom = f"api:{fournisseur}:{modele}"
        self.t, self.delai, self.graine = temperature, delai, graine
        self.essais, self.attente_base, self.intervalle_min = essais, attente_base, intervalle_min
        self.cache = Path(cache) if cache else None
        self._dormir = dormir
        self._prochain = 0.0            # instant avant lequel on n'appelle pas (débit)
        self.journal_debit: list[dict] = []
        self.appels_reseau = 0
        self.succes_cache = 0

    # -- cache disque ---------------------------------------------------
    def _cle_cache(self, systeme, utilisateur, json_attendu) -> str:
        brut = json.dumps([self.url, self.modele, self.t, self.graine, json_attendu, systeme, utilisateur],
                          ensure_ascii=False)
        return hashlib.sha256(brut.encode()).hexdigest()

    def _lire_cache(self, k):
        if self.cache and (self.cache / f"{k}.json").exists():
            return json.loads((self.cache / f"{k}.json").read_text(encoding="utf-8"))["contenu"]
        return None

    def _ecrire_cache(self, k, contenu):
        if self.cache:
            self.cache.mkdir(parents=True, exist_ok=True)
            (self.cache / f"{k}.json").write_text(json.dumps(
                {"modele": self.nom, "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S"), "contenu": contenu},
                ensure_ascii=False), encoding="utf-8")

    # -- limite de débit ------------------------------------------------
    def _lire_debit(self, entetes) -> None:
        g = {k.lower(): v for k, v in (entetes or {}).items()}
        info = {k: g.get(k) for k in ("x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens",
                                      "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens", "retry-after")}
        self.journal_debit.append(info)
        attente = 0.0
        for reste, reset in (("x-ratelimit-remaining-requests", "x-ratelimit-reset-requests"),
                             ("x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens")):
            try:
                if info[reste] is not None and float(info[reste]) <= 1:
                    attente = max(attente, _duree(info[reset]) or 1.0)
            except ValueError:
                pass
        if attente:
            self._prochain = max(self._prochain, time.monotonic() + attente)

    def _attendre_tour(self):
        maintenant = time.monotonic()
        if self._prochain > maintenant:
            self._dormir(self._prochain - maintenant)
        self._prochain = time.monotonic() + self.intervalle_min

    # -- appel ----------------------------------------------------------
    def generer(self, systeme, utilisateur, json_attendu=True):
        k = self._cle_cache(systeme, utilisateur, json_attendu)
        en_cache = self._lire_cache(k)
        if en_cache is not None:
            self.succes_cache += 1
            return en_cache
        corps = {"model": self.modele, "temperature": self.t, "seed": self.graine,
                 "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}]}
        if json_attendu:
            corps["response_format"] = {"type": "json_object"}
        with ClientAPI._verrou:
            derniere = None
            essai, attentes_429 = 0, 0
            while essai < self.essais:
                self._attendre_tour()
                req = urllib.request.Request(
                    f"{self.url}/chat/completions", data=json.dumps(corps).encode(),
                    headers={"Content-Type": "application/json", "Accept": "application/json",
                             "Authorization": f"Bearer {self._cle}",
                             # un identifiant explicite : certains pare-feu (Cloudflare) refusent « Python-urllib »
                             "User-Agent": "minpmeesa-prototype/5.1 (evaluation memoire ISSEA)"})
                try:
                    self.appels_reseau += 1
                    with urllib.request.urlopen(req, timeout=self.delai) as r:
                        self._lire_debit(dict(r.headers))
                        contenu = json.loads(r.read())["choices"][0]["message"]["content"]
                    self._ecrire_cache(k, contenu)
                    return contenu
                except urllib.error.HTTPError as e:
                    self._lire_debit(dict(e.headers or {}))
                    if e.code == 429 and attentes_429 < 20:
                        # limite atteinte : on patiente puis on remet l'appel en file (non compté comme échec)
                        attentes_429 += 1
                        attente = _duree((e.headers or {}).get("retry-after")) or self.attente_base * 2
                        self._prochain = time.monotonic() + attente
                        derniere = e
                        continue
                    if 500 <= e.code < 600:
                        derniere = e
                    else:
                        try:
                            detail = e.read().decode("utf-8", "replace")[:300]
                        except Exception:
                            detail = ""
                        raise ErreurLLM(f"API {self.fournisseur} : HTTP {e.code} {detail}".strip()) from e
                except (urllib.error.URLError, OSError, TimeoutError) as e:
                    derniere = e
                except (KeyError, ValueError) as e:
                    raise ErreurLLM(f"API {self.fournisseur} : réponse illisible ({e})") from e
                essai += 1
                if essai < self.essais:
                    self._dormir(self.attente_base * 2 ** (essai - 1))
            raise ErreurLLM(f"API {self.fournisseur} : échec après {self.essais} essais ({derniere})")


# ------------------------------------------------------------------ llama-cpp (repli local)
class LlamaCpp(ClientLLM):
    moteur = "llamacpp"

    def __init__(self, chemin_gguf: str, temperature: float = 0, graine: int = 42):
        from llama_cpp import Llama
        self.modele = Path(chemin_gguf).name
        self.nom = f"llamacpp:{self.modele}"
        self._m = Llama(model_path=chemin_gguf, n_ctx=8192, seed=graine, verbose=False)
        self.t = temperature

    def generer(self, systeme, utilisateur, json_attendu=True):
        kw = {"response_format": {"type": "json_object"}} if json_attendu else {}
        r = self._m.create_chat_completion(
            messages=[{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
            temperature=self.t, **kw)
        return r["choices"][0]["message"]["content"]


# ------------------------------------------------------------------ fabrique
def client_api(cfg: dict, modele: str | None = None) -> ClientAPI:
    from .. import config
    a = cfg["llm"]["api"]
    cache = config.RACINE / a["cache"] if a.get("cache") else None
    return ClientAPI(a["url"], modele or a["modele"], a["cle_env"], a.get("fournisseur", "api"),
                     cfg["llm"]["temperature"], a["delai_max_s"], cfg["graine"], a["essais_reseau"],
                     a["attente_base_s"], a["intervalle_min_s"], cache)


def obtenir(cfg: dict, backend: str | None = None, modele: str | None = None,
            delai: float | None = None) -> tuple[ClientLLM | None, str]:
    """(client, explication). Client None = mode extractif (sans modèle de langage).
    `delai` : attente maximale d'une réponse Ollama (l'interface en fixe une plus courte ; au-delà,
    le commentaire est rédigé par les gabarits, repli signalé)."""
    l = cfg["llm"]
    backend = backend or l["backend"]
    if backend == "none":
        return None, "mode sans modèle de langage (--llm none)"
    if backend == "api":
        try:
            c = client_api(cfg, modele)
            return c, f"{c.nom} (moteur de développement, service distant)"
        except ErreurLLM as e:
            return None, f"repli en mode extractif : moteur api indisponible ({e})"
    raison = ""
    if backend == "ollama":
        o = l["ollama"]
        c = Ollama(modele or o["modele"], o["url"], l["temperature"], delai or o["delai_max_s"], cfg["graine"],
                   o.get("num_ctx"))
        if c.disponible():
            return c, c.nom
        raison = f"Ollama indisponible ou modèle {modele or o['modele']} absent"
        backend = "llamacpp"
    if backend == "llamacpp":
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


def decrire(client: ClientLLM | None) -> dict:
    """Moteur et modèle, enregistrés dans chaque sortie."""
    if client is None:
        return {"moteur": "none", "modele": "aucun (mode extractif)"}
    return {"moteur": client.moteur, "modele": client.modele}
