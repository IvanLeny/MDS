"""Configuration commune des tests : toute connexion réseau sortante (hors
boucle locale) fait échouer le test qui la tente."""
import ipaddress
import socket

import pytest

_connect_orig = socket.socket.connect
TENTATIVES: list = []


def _est_local(adresse) -> bool:
    if isinstance(adresse, (str, bytes)):          # socket Unix
        return True
    hote = adresse[0]
    if hote in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(hote).is_loopback
    except ValueError:
        return False


def _connect_garde(self, adresse):
    if not _est_local(adresse):
        TENTATIVES.append(adresse)
        raise RuntimeError(f"Appel réseau sortant interdit pendant l'exécution : {adresse}")
    return _connect_orig(self, adresse)


@pytest.fixture(autouse=True)
def pas_de_reseau(monkeypatch):
    TENTATIVES.clear()
    monkeypatch.setattr(socket.socket, "connect", _connect_garde)
    yield
    assert not TENTATIVES, f"connexions sortantes tentées : {TENTATIVES}"
