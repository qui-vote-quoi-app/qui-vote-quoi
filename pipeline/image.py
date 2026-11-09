"""Image PNG de l'hémicycle d'un scrutin, pour la notification Telegram."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .sources import charger_json

COULEURS = {"pour": (32, 107, 167), "contre": (227, 64, 81), "abst": (159, 168, 173),
            "nv": (221, 221, 221), "vide": (238, 239, 235)}
ECHELLE = 5


def _police(taille, gras=False):
    noms = ["DejaVuSans-Bold.ttf" if gras else "DejaVuSans.ttf"]
    for dossier in ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF"]:
        for n in noms:
            p = Path(dossier) / n
            if p.exists():
                return ImageFont.truetype(str(p), taille)
    return ImageFont.load_default(size=taille)


def _couper(texte, police, largeur, dessin):
    mots, lignes, ligne = texte.split(), [], ""
    for m in mots:
        essai = (ligne + " " + m).strip()
        if dessin.textlength(essai, font=police) <= largeur:
            ligne = essai
        else:
            lignes.append(ligne)
            ligne = m
    if ligne:
        lignes.append(ligne)
    return lignes[:3]


def dessiner(scrutin, destination: Path):
    places = charger_json(config.PLACES, {})["places"]
    position_par_place = {}
    for g in scrutin["groupes"]:
        for pos, liste_ in g["votes"].items():
            for _pa, place in liste_:
                position_par_place[str(place)] = pos

    largeur, marge_haut, marge_bas = 237 * ECHELLE, 150, 120
    hauteur = 132 * ECHELLE + marge_haut + marge_bas
    img = Image.new("RGB", (largeur, hauteur), (255, 255, 255))
    d = ImageDraw.Draw(img)

    titre = scrutin["titre"][:1].upper() + scrutin["titre"][1:]
    f_titre = _police(26, gras=True)
    y = 24
    for ligne in _couper(titre, f_titre, largeur - 60, d):
        d.text((30, y), ligne, font=f_titre, fill=(20, 21, 19))
        y += 34
    d.text((30, y + 4), f"Scrutin n° {scrutin['num']} · {'/'.join(reversed(scrutin['date'].split('-')))}", font=_police(18), fill=(95, 98, 91))

    r = 1.95 * ECHELLE
    for num, (x, yy) in places.items():
        pos = position_par_place.get(num, "vide")
        cx, cy = x * ECHELLE, yy * ECHELLE + marge_haut
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COULEURS[pos])

    adopte = scrutin["sort"] == "adopté"
    cx = 118.3 * ECHELLE
    cy = 132 * ECHELLE + marge_haut - 70
    texte = "ADOPTÉ" if adopte else "REJETÉ"
    f_res = _police(52, gras=True)
    d.text((cx - d.textlength(texte, font=f_res) / 2, cy - 40), texte, font=f_res,
           fill=COULEURS["pour"] if adopte else COULEURS["contre"])

    y = hauteur - marge_bas + 30
    x = 30
    f = _police(24, gras=True)
    for cle, libelle in [("pour", "Pour"), ("contre", "Contre"), ("abst", "Abstention")]:
        d.ellipse([x, y + 4, x + 20, y + 24], fill=COULEURS[cle])
        t = f"{libelle} {scrutin[cle]}"
        d.text((x + 30, y), t, font=f, fill=(20, 21, 19))
        x += 60 + d.textlength(t, font=f)
    d.text((30, hauteur - 34), "Source : Assemblée nationale (open data) · Qui vote quoi ?",
           font=_police(16), fill=(95, 98, 91))
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, optimize=True)
    return destination
