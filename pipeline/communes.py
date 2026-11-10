"""Correspondance commune -> circonscription(s) législative(s), pour « Trouver mon député ».

Sources (téléchargées une seule fois, résultat versionné dans data/communes.json) :
- Ministère de l'Intérieur, table de correspondance communes / circonscriptions (découpage en vigueur
  depuis 2012, inchangé en 2024) : data.gouv.fr ;
- La Poste, base officielle des codes postaux : data.gouv.fr.
Format : [[nom, département, [circonscriptions], [codes postaux]], …] trié par nom.
Les communes créées après 2017 par fusion n'y figurent pas sous leur nouveau nom : le site propose
alors les députés du département."""
import csv
import io
import json

import requests

from . import config

URL_CIRCO = ("https://static.data.gouv.fr/resources/circonscriptions-legislatives-table-de-correspondance-des-communes-"
             "et-des-cantons-pour-les-elections-legislatives-de-2012-et-sa-mise-a-jour-pour-les-elections-legislatives-"
             "2017/20170411-141128/Table_de_correspondance_circo_legislatives2017-1.xlsx")
URL_CP = "https://data.laposte.fr/data-fair/api/v1/datasets/laposte-hexasmal/raw"
FICHIER = config.DATA / "communes.json"
DOM = {"ZA": "97", "ZB": "97", "ZC": "97", "ZD": "97", "ZM": "97", "ZN": "98", "ZP": "98", "ZS": "97", "ZW": "98", "ZX": "97"}


def _get(url):
    r = requests.get(url, timeout=180, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    return r.content


def _insee(dep, com):
    dep = str(dep).strip()
    com = str(com).strip().split(".")[0]
    if dep in DOM:
        return DOM[dep] + com.zfill(3)
    return dep.zfill(2) + com.zfill(3)


# Noms de départements alignés sur ceux de l'open data de l'Assemblée.
RENOMMER = {"Saint-Martin/Saint-Barthélemy": "Saint-Barthélemy et Saint-Martin"}


def _arrondissement(code):
    """Paris, Lyon et Marseille : les codes postaux sont rattachés aux arrondissements."""
    if code.startswith("751") and len(code) == 5:
        return "75056"
    if code.startswith("6938"):
        return "69123"
    if "13201" <= code <= "13216":
        return "13055"
    return code


def construire(xlsx_bytes, cp_bytes):
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(xlsx_bytes), read_only=True).worksheets[0]
    communes = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0 or not row or row[2] is None:
            continue
        dep, nom_dep, com, nom, circ = row[:5]
        c = communes.setdefault(_insee(dep, com), [str(nom).strip(), str(nom_dep).strip(), set(), set()])
        try:
            c[2].add(int(circ))
        except (TypeError, ValueError):
            pass
    try:
        texte = cp_bytes.decode("utf-8")
    except UnicodeDecodeError:
        texte = cp_bytes.decode("latin-1")
    # Collectivités absentes de la table du ministère.
    communes.setdefault("97502", ["Saint-Pierre", "Saint-Pierre-et-Miquelon", {1}, set()])
    communes.setdefault("97501", ["Miquelon-Langlade", "Saint-Pierre-et-Miquelon", {1}, set()])
    for c in communes.values():
        c[1] = RENOMMER.get(c[1], c[1])
    for row in csv.reader(io.StringIO(texte), delimiter=";"):
        if len(row) < 3 or not row[2].strip():
            continue
        code = _arrondissement(row[0].strip())
        if code in communes:
            communes[code][3].add(row[2].strip())
    sortie = [[n, d, sorted(c), sorted(p)] for n, d, c, p in communes.values() if c]
    sortie.sort(key=lambda x: (x[0].lower(), x[1]))
    return sortie


def assurer():
    """Construit data/communes.json s'il n'existe pas encore. Ne bloque jamais le reste du passage."""
    if FICHIER.exists():
        return True
    try:
        donnees = construire(_get(URL_CIRCO), _get(URL_CP))
        FICHIER.write_text(json.dumps(donnees, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Communes : {len(donnees)} communes enregistrées.")
        return True
    except Exception as e:  # noqa: BLE001 — fonctionnalité secondaire
        print(f"Communes : table non construite ({e}).")
        return False
