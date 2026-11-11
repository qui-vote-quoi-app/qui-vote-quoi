"""Contours des circonscriptions législatives, pour « Trouver mon député.e » à partir d'une adresse.

Source : « Contours géographiques des circonscriptions législatives » (data.gouv.fr, Licence Ouverte 2.0),
construits à partir des bureaux de vote du ministère de l'Intérieur. Téléchargée une seule fois et découpée
par département dans data/circos/<département>.json : [[numéro de circonscription, multipolygone], …].
Les codes de département suivent ceux de l'Assemblée (971 et non ZA)."""
import json

import requests

from . import config

URL = ("https://static.data.gouv.fr/resources/contours-geographiques-des-circonscriptions-legislatives/"
       "20240613-191520/circonscriptions-legislatives-p10.geojson")
DOSSIER = config.DATA / "circos"
OUTRE_MER = {"ZA": "971", "ZB": "972", "ZC": "973", "ZD": "974", "ZS": "975", "ZM": "976"}


def decouper(geojson):
    par_dep = {}
    for f in geojson["features"]:
        p, g = f["properties"], f["geometry"]
        dep = OUTRE_MER.get(p["codeDepartement"], p["codeDepartement"])
        num = int(str(p["codeCirconscription"])[-2:])
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        par_dep.setdefault(dep, []).append([num, polys])
    return par_dep


def assurer():
    if DOSSIER.exists() and any(DOSSIER.glob("*.json")):
        return True
    try:
        r = requests.get(URL, timeout=180, headers={"User-Agent": config.USER_AGENT})
        r.raise_for_status()
        par_dep = decouper(r.json())
        DOSSIER.mkdir(parents=True, exist_ok=True)
        for dep, circos in par_dep.items():
            (DOSSIER / f"{dep}.json").write_text(json.dumps(sorted(circos), separators=(",", ":")), encoding="utf-8")
        print(f"Contours : {sum(len(c) for c in par_dep.values())} circonscriptions dans {len(par_dep)} départements.")
        return True
    except Exception as e:  # noqa: BLE001 — fonctionnalité secondaire
        print(f"Contours des circonscriptions non construits ({e}).")
        return False
