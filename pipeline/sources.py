"""Téléchargement des dumps open data et lecture partielle de ZIP distants."""
import json
import struct
import time
import zlib
from pathlib import Path

import requests

from . import config

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


def _get(url, **kw):
    for essai in range(4):
        try:
            r = _session.get(url, timeout=120, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if essai == 3:
                raise
            time.sleep(5 * (essai + 1))


def entete(url):
    """ETag / date / taille d'un fichier distant, sans le télécharger."""
    r = _session.head(url, timeout=60, allow_redirects=True)
    r.raise_for_status()
    return {
        "etag": r.headers.get("ETag"),
        "modifie": r.headers.get("Last-Modified"),
        "taille": int(r.headers.get("Content-Length") or 0),
    }


def telecharger(url, destination: Path, essais=5):
    """Télécharge en entier, avec reprise complète si la connexion est coupée en cours de route
    (le serveur de l'Assemblée interrompt parfois les gros transferts) et contrôle de la taille."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".part")
    for essai in range(essais):
        try:
            with _get(url, stream=True) as r, open(tmp, "wb") as f:
                attendu = int(r.headers.get("Content-Length") or 0)
                for bloc in r.iter_content(1 << 20):
                    f.write(bloc)
            recu = tmp.stat().st_size
            if attendu and recu != attendu:
                raise requests.exceptions.ChunkedEncodingError(f"{recu} octets reçus sur {attendu}")
            tmp.replace(destination)
            return destination
        except (requests.RequestException, OSError) as e:
            print(f"Téléchargement interrompu ({url.rsplit('/', 1)[-1]}, essai {essai + 1}/{essais}) : {e}")
            if essai == essais - 1:
                raise
            time.sleep(15 * (essai + 1))


class ZipDistant:
    """Lit un ZIP distant fichier par fichier grâce aux requêtes HTTP Range,
    sans télécharger l'archive entière (utile pour les comptes rendus, ~60 Mo)."""

    def __init__(self, url):
        self.url = url
        self.taille = entete(url)["taille"]
        self.entrees = self._repertoire()

    def _plage(self, debut, fin):
        r = _get(self.url, headers={"Range": f"bytes={debut}-{fin}"})
        return r.content

    def _repertoire(self):
        queue = min(self.taille, 65557)
        buf = self._plage(self.taille - queue, self.taille - 1)
        i = buf.rfind(b"PK\x05\x06")
        if i < 0:
            raise ValueError("Fin de répertoire ZIP introuvable")
        taille_cd, offset_cd = struct.unpack("<II", buf[i + 12:i + 20])
        cd = self._plage(offset_cd, offset_cd + taille_cd - 1)
        entrees, p = {}, 0
        while p + 46 <= len(cd) and cd[p:p + 4] == b"PK\x01\x02":
            methode = struct.unpack("<H", cd[p + 10:p + 12])[0]
            csz, usz = struct.unpack("<II", cd[p + 20:p + 28])
            ln, le, lc = struct.unpack("<HHH", cd[p + 28:p + 34])
            offset = struct.unpack("<I", cd[p + 42:p + 46])[0]
            nom = cd[p + 46:p + 46 + ln].decode("utf-8")
            entrees[nom] = (methode, csz, offset)
            p += 46 + ln + le + lc
        return entrees

    def _donnees(self, nom, limite=None):
        methode, csz, offset = self.entrees[nom]
        tete = self._plage(offset, offset + 29)
        ln, le = struct.unpack("<HH", tete[26:30])
        debut = offset + 30 + ln + le
        n = csz if limite is None else min(csz, limite)
        return methode, self._plage(debut, debut + n - 1)

    def lire(self, nom) -> bytes:
        methode, brut = self._donnees(nom)
        return brut if methode == 0 else zlib.decompress(brut, -15)

    def lire_debut(self, nom, octets=4000) -> bytes:
        methode, brut = self._donnees(nom, limite=octets)
        if methode == 0:
            return brut
        return zlib.decompressobj(-15).decompress(brut)


def charger_json(chemin, defaut):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def ecrire_json(chemin, donnees, compact=False):
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        texte = json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
    else:
        texte = json.dumps(donnees, ensure_ascii=False, indent=1)
    chemin.write_text(texte, encoding="utf-8")
