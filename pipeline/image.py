"""Carte image d'un scrutin (Telegram, aperçu du site), à l'identité du site :
bandeau velours, titre en Barlow Condensed, hémicycle aux couleurs officielles, barre pour / contre / abstention.
Polices embarquées (licence SIL Open Font) : pipeline/polices/."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .sources import charger_json

COULEURS = {"pour": (32, 107, 167), "contre": (227, 64, 81), "abst": (159, 168, 173),
            "nv": (221, 221, 221), "vide": (232, 234, 228)}
VELOURS, ENCRE, GRIS, PAPIER = (125, 26, 44), (20, 21, 19), (95, 98, 91), (255, 255, 255)
POLICES = Path(__file__).parent / "polices"
LARGEUR, HAUTEUR = 1200, 1000
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]


def _police(nom, taille, graisse=None):
    try:
        f = ImageFont.truetype(str(POLICES / nom), taille)
        if graisse:
            try:
                f.set_variation_by_axes([graisse])
            except Exception:  # noqa: BLE001
                pass
        return f
    except OSError:
        return ImageFont.load_default(size=taille)


def _titre(taille):
    return _police("BarlowCondensed-Bold.ttf", taille)


def _texte(taille, graisse=400):
    return _police("SourceSans3-VF.ttf", taille, graisse)


def _couper(texte, police, largeur, dessin, max_lignes):
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
    if len(lignes) > max_lignes:
        lignes = lignes[:max_lignes]
        lignes[-1] = lignes[-1].rstrip(" ,;:") + "…"
    return lignes


def _date(iso):
    a, m, j = (int(x) for x in iso.split("-"))
    return f"{j}{'er' if j == 1 else ''} {MOIS[m - 1]} {a}"


def dessiner(scrutin, destination: Path, titre=None):
    """`titre` : titre court à afficher (sinon l'intitulé officiel du scrutin)."""
    places = charger_json(config.PLACES, {})["places"]
    position_par_place = {}
    for g in scrutin["groupes"]:
        for pos, liste_ in g["votes"].items():
            for _pa, place in liste_:
                position_par_place[str(place)] = pos

    img = Image.new("RGB", (LARGEUR, HAUTEUR), PAPIER)
    d = ImageDraw.Draw(img)

    # Bandeau
    d.rectangle([0, 0, LARGEUR, 84], fill=VELOURS)
    d.text((48, 18), "QUI VOTE QUOI ?", font=_titre(44), fill=PAPIER)
    info = f"{_date(scrutin['date'])}  ·  scrutin n° {scrutin['num']}"
    f_info = _texte(24, 600)
    d.text((LARGEUR - 48 - d.textlength(info, font=f_info), 30), info, font=f_info, fill=(240, 220, 225))

    # Titre
    titre = titre or (scrutin["titre"][:1].upper() + scrutin["titre"][1:])
    f_t = _titre(54)
    y = 112
    for ligne in _couper(titre, f_t, LARGEUR - 96, d, 3):
        d.text((48, y), ligne, font=f_t, fill=ENCRE)
        y += 58
    haut_hemi = max(y + 18, 250)

    # Hémicycle (carte officielle des sièges : 237 x 132 unités)
    echelle = 4.4
    x0 = (LARGEUR - 237 * echelle) / 2
    r = 1.95 * echelle
    for num, (x, yy) in places.items():
        pos = position_par_place.get(num, "vide")
        cx, cy = x0 + x * echelle, haut_hemi + yy * echelle
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COULEURS[pos])

    # Résultat au centre de l'hémicycle
    adopte = scrutin["sort"] == "adopté"
    mot = "ADOPTÉ" if adopte else "REJETÉ"
    f_res = _titre(76)
    lw = d.textlength(mot, font=f_res) + 56
    cx, cy = LARGEUR / 2, haut_hemi + 132 * echelle - 58
    d.rectangle([cx - lw / 2, cy - 46, cx + lw / 2, cy + 46], fill=COULEURS["pour"] if adopte else COULEURS["contre"])
    d.text((cx - lw / 2 + 28, cy - 44), mot, font=f_res, fill=PAPIER)

    # Barre pour / contre / abstention
    yb = HAUTEUR - 150
    total = max(1, scrutin["pour"] + scrutin["contre"] + scrutin["abst"])
    x = 48
    largeur_barre = LARGEUR - 96
    for cle in ("pour", "contre", "abst"):
        w = largeur_barre * scrutin[cle] / total
        if w > 0:
            d.rectangle([x, yb, x + w, yb + 22], fill=COULEURS[cle])
        x += w
    x, yl = 48, yb + 40
    f_n, f_l = _titre(40), _texte(26, 500)
    for cle, libelle in [("pour", "pour"), ("contre", "contre"), ("abst", "abstention" + ("s" if scrutin["abst"] > 1 else ""))]:
        d.rectangle([x, yl + 12, x + 22, yl + 34], fill=COULEURS[cle])
        n = str(scrutin[cle])
        d.text((x + 34, yl), n, font=f_n, fill=ENCRE)
        x2 = x + 34 + d.textlength(n, font=f_n) + 10
        d.text((x2, yl + 10), libelle, font=f_l, fill=GRIS)
        x = x2 + d.textlength(libelle, font=f_l) + 48

    # Pied
    d.line([48, HAUTEUR - 52, LARGEUR - 48, HAUTEUR - 52], fill=(201, 204, 196), width=2)
    d.text((48, HAUTEUR - 42), "Source : Assemblée nationale (open data)  ·  qui-vote-quoi-app.github.io",
           font=_texte(22), fill=GRIS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, optimize=True)
    return destination
