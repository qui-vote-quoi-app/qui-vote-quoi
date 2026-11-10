"""Photos officielles des députés (site de l'Assemblée nationale).

- téléchargées une seule fois, gardées dans .cache/photos/ (cache GitHub Actions) ;
- converties en petites vignettes WebP dans site/data/photos/ à chaque publication ;
- désactivables d'un coup (variable QVQ_PHOTOS=0 dans les réglages du dépôt)
  ou député par député (data/photos_retirees.txt, un identifiant PA… par ligne).
Crédit affiché sur le site : « Photo : Assemblée nationale »."""
import time

import requests
from PIL import Image

from . import config

URL = config.AN + "/dyn/static/tribun/{leg}/photos/carre/{num}.jpg"
CACHE = config.CACHE / "photos"
TAILLE = 160            # px, carré ; affiché au plus à 120 px de large
REESSAI_ABSENTE = 7 * 86400   # une photo absente est recherchée de nouveau au bout d'une semaine


def retirees():
    f = config.DATA / "photos_retirees.txt"
    if not f.exists():
        return set()
    return {l.split("#")[0].strip() for l in f.read_text(encoding="utf-8").splitlines() if l.split("#")[0].strip()}


def preparer(deputes, telecharger=True):
    """Télécharge les photos manquantes. Retourne l'ensemble des identifiants qui ont une photo."""
    if not config.PHOTOS:
        print("Photos désactivées (QVQ_PHOTOS=0).")
        return set()
    CACHE.mkdir(parents=True, exist_ok=True)
    exclus = retirees()
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    avec, nouvelles, echecs = set(), 0, 0
    for uid in deputes:
        if uid in exclus:
            continue
        num = uid.removeprefix("PA")
        jpg, absente = CACHE / f"{num}.jpg", CACHE / f"{num}.absente"
        if not jpg.exists() and telecharger and not (absente.exists() and time.time() - absente.stat().st_mtime < REESSAI_ABSENTE):
            try:
                r = session.get(URL.format(leg=config.LEGISLATURE, num=num), timeout=30)
                if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"):
                    jpg.write_bytes(r.content)
                    nouvelles += 1
                    absente.unlink(missing_ok=True)
                elif r.status_code == 404:
                    absente.touch()
                else:
                    echecs += 1
            except requests.RequestException:
                echecs += 1
            time.sleep(0.15)   # ménager le serveur de l'Assemblée
        if jpg.exists():
            avec.add(uid)
    print(f"Photos : {len(avec)} disponibles, {nouvelles} nouvelles, {echecs} échecs.")
    return avec


def ecrire(uids):
    """Vignettes WebP dans site/data/photos/<PA…>.webp."""
    if not uids:
        return
    out = config.SITE_DATA / "photos"
    out.mkdir(parents=True, exist_ok=True)
    for uid in uids:
        with Image.open(CACHE / f"{uid.removeprefix('PA')}.jpg") as im:
            im = im.convert("RGB")
            im.thumbnail((TAILLE, TAILLE), Image.LANCZOS)
            im.save(out / f"{uid}.webp", "WEBP", quality=72, method=6)
