"""Moteur `api` (développement) : clé lue dans l'environnement, limite de débit,
nouvelles tentatives, file d'attente sur 429, cache disque. Faux serveur local
compatible OpenAI : aucun appel ne sort de la machine."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from minpmeesa import config
from minpmeesa.generation import llm


class Faux(BaseHTTPRequestHandler):
    scenario: list = []          # liste de (code, entêtes, contenu)
    recus: list = []

    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Faux.recus.append({"auth": self.headers.get("Authorization"), "corps": corps})
        code, entetes, contenu = Faux.scenario.pop(0) if Faux.scenario else (200, {}, '{"enonces": []}')
        self.send_response(code)
        for k, v in entetes.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code == 200:
            self.wfile.write(json.dumps({"choices": [{"message": {"content": contenu}}]}).encode())

    def log_message(self, *a):
        pass


@pytest.fixture
def serveur():
    Faux.scenario, Faux.recus = [], []
    s = HTTPServer(("127.0.0.1", 0), Faux)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{s.server_address[1]}/v1"
    s.shutdown()


def _client(url, tmp_path, monkeypatch, **kw):
    monkeypatch.setenv("CLE_TEST", "secret-123")
    attentes = []
    c = llm.ClientAPI(url, "llama-3.1-8b-instant", "CLE_TEST", "groq", essais=3, attente_base=0.01,
                      cache=tmp_path / "cache", dormir=attentes.append, **kw)
    return c, attentes


def test_cle_absente(monkeypatch):
    monkeypatch.delenv("CLE_ABSENTE", raising=False)
    with pytest.raises(llm.ErreurLLM, match="CLE_ABSENTE"):
        llm.ClientAPI("http://127.0.0.1:1/v1", "m", "CLE_ABSENTE")


def test_cle_jamais_dans_le_code():
    import pathlib
    for f in pathlib.Path(config.RACINE, "minpmeesa").rglob("*.py"):
        assert "gsk_" not in f.read_text(encoding="utf-8"), f   # préfixe des clés Groq


def test_appel_parametres_et_cache(serveur, tmp_path, monkeypatch):
    c, _ = _client(serveur, tmp_path, monkeypatch)
    Faux.scenario = [(200, {}, '{"enonces": [{"type": "constat", "texte": "x"}]}')]
    r1 = c.generer("sys", "user")
    r2 = c.generer("sys", "user")                      # servi par le cache
    assert r1 == r2 and len(Faux.recus) == 1 and c.succes_cache == 1
    envoi = Faux.recus[0]
    assert envoi["auth"] == "Bearer secret-123"
    assert envoi["corps"]["temperature"] == 0 and envoi["corps"]["model"] == "llama-3.1-8b-instant"
    assert envoi["corps"]["response_format"] == {"type": "json_object"}
    assert c.nom == "api:groq:llama-3.1-8b-instant"


def test_trois_essais_puis_echec(serveur, tmp_path, monkeypatch):
    c, attentes = _client(serveur, tmp_path, monkeypatch)
    Faux.scenario = [(503, {}, "")] * 3
    with pytest.raises(llm.ErreurLLM, match="3 essais"):
        c.generer("s", "u")
    assert len(Faux.recus) == 3
    assert [round(a, 3) for a in attentes if a >= 0.01] == [0.01, 0.02]      # attente croissante


def test_reprise_apres_coupure(serveur, tmp_path, monkeypatch):
    c, _ = _client(serveur, tmp_path, monkeypatch)
    Faux.scenario = [(502, {}, ""), (200, {}, '{"ok": 1}')]
    assert c.generer("s", "u2") == '{"ok": 1}' and len(Faux.recus) == 2


def test_429_mis_en_file_et_non_perdu(serveur, tmp_path, monkeypatch):
    c, attentes = _client(serveur, tmp_path, monkeypatch)
    Faux.scenario = [(429, {"retry-after": "7"}, ""), (429, {"retry-after": "7"}, ""),
                     (429, {"retry-after": "7"}, ""), (200, {}, '{"ok": 2}')]
    assert c.generer("s", "u3") == '{"ok": 2}'           # 3 refus de débit ne comptent pas comme échecs
    assert sum(1 for a in attentes if a > 5) == 3


def test_entetes_de_debit_ralentissent(serveur, tmp_path, monkeypatch):
    c, attentes = _client(serveur, tmp_path, monkeypatch)
    Faux.scenario = [(200, {"x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "2m59.5s"}, "{}"),
                     (200, {}, "{}")]
    c.generer("s", "a")
    c.generer("s", "b")
    assert any(a > 170 for a in attentes)                 # attend la réinitialisation annoncée
    assert c.journal_debit[0]["x-ratelimit-remaining-requests"] == "0"


def test_duree_entetes():
    assert llm._duree("2m59.56s") == pytest.approx(179.56)
    assert llm._duree("120ms") == pytest.approx(0.12)
    assert llm._duree("7") == 7


def test_selection_du_moteur_par_config(monkeypatch):
    cfg = config.charger()
    monkeypatch.delenv(cfg["llm"]["api"]["cle_env"], raising=False)
    c, expl = llm.obtenir(cfg, "api")
    assert c is None and "GROQ_API_KEY" in expl                # repli signalé, jamais d'appel sans clé
    c, expl = llm.obtenir(cfg, "none")
    assert c is None and llm.decrire(c)["moteur"] == "none"
    assert cfg["llm"]["ollama"]["modele"] == "llama3.1:8b"
    assert cfg["llm"]["api"]["modele"] == "llama-3.1-8b-instant"
