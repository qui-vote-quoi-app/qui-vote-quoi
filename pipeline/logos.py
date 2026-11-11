"""Logos des groupes politiques de l'Assemblée (logos de groupe, pas de parti), au format carré.

Sources : Wikimedia Commons (licences libres) ou Wikipédia en français (logos « marque déposée »,
reproduits uniquement pour identifier le groupe). Chaque logo est téléchargé une fois, posé sur un
carré blanc de 400 px et enregistré dans data/logos/<SIGLE>.png. Les non-inscrits, qui n'ont pas de
logo, reçoivent un carré « NI » dessiné ici. Les crédits sont affichés dans les mentions légales."""
import shutil
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .sources import telecharger

VERSION = "2"   # à incrémenter pour forcer un nouveau téléchargement
COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/{}?width=600"
FRWIKI = "https://fr.wikipedia.org/wiki/Special:FilePath/{}?width=600"
# sigle -> (adresse modèle, fichier, licence, auteur ou titulaire)
LOGOS = {
    "RN": (COMMONS, "Groupe RN 2024.png", "CC BY-SA 4.0", "Groupe Rassemblement National"),
    "EPR": (COMMONS, "Groupe EPR.png", "CC BY 4.0", "Groupe Ensemble pour la République"),
    "LFI-NFP": (FRWIKI, "LFI-NFP.png", "marque déposée", "Groupe La France insoumise - NFP"),
    "SOC": (FRWIKI, "Logo Groupe socialiste AN 2023.svg", "marque déposée", "Groupe Socialistes et apparentés"),
    "DR": (COMMONS, "La Droite Républicaine logo 2024.png", "CC BY-SA 4.0", "Groupe La Droite Républicaine"),
    "ECOS": (COMMONS, "Logo-Groupe écologiste et Social-AN.webp", "CC BY 3.0", "Groupe Écologiste et Social"),
    "DEM": (COMMONS, "DemsFrance.png", "CC BY 4.0", "Groupe Les Démocrates"),
    "HOR": (COMMONS, "Horizons Group.png", "CC BY-SA 3.0", "Groupe Horizons"),
    "LIOT": (COMMONS, "LIOT Group.png", "CC BY-SA 3.0", "Groupe LIOT"),
    "GDR": (COMMONS, "Logo GDR.svg", "CC BY-SA 4.0", "Groupe de la Gauche démocrate et républicaine"),
    "UDR": (COMMONS, "UDR group logo.png", "domaine public", "Groupe Union des droites pour la République"),
}
DOSSIER = config.DATA / "logos"
BRUT = config.CACHE / "logos"
COTE, MARGE = 400, 36
POLICE = Path(__file__).parent / "polices" / "BarlowCondensed-Bold.ttf"


def _carre(source: Path, dest: Path):
    im = Image.open(source)
    im = im.convert("RGBA")
    # Rogner les bords vides (transparents ou blancs) pour centrer le logo.
    fond = Image.new("RGBA", im.size, (255, 255, 255, 255))
    plat = Image.alpha_composite(fond, im).convert("RGB")
    masque = Image.eval(plat.convert("L"), lambda v: 255 if v < 245 else 0)
    boite = masque.getbbox()
    if boite:
        plat = plat.crop(boite)
    plat.thumbnail((COTE - 2 * MARGE, COTE - 2 * MARGE), Image.LANCZOS)
    carre = Image.new("RGB", (COTE, COTE), (255, 255, 255))
    carre.paste(plat, ((COTE - plat.width) // 2, (COTE - plat.height) // 2))
    dest.parent.mkdir(parents=True, exist_ok=True)
    carre.save(dest, optimize=True)


def _non_inscrits(dest: Path):
    carre = Image.new("RGB", (COTE, COTE), (255, 255, 255))
    d = ImageDraw.Draw(carre)
    gris = (110, 114, 106)
    f1, f2 = ImageFont.truetype(str(POLICE), 190), ImageFont.truetype(str(POLICE), 54)
    b1, b2 = d.textbbox((0, 0), "NI", font=f1), d.textbbox((0, 0), "NON-INSCRITS", font=f2)
    h1, h2, ecart, trait = b1[3] - b1[1], b2[3] - b2[1], 22, 6
    y = (COTE - (h1 + ecart + trait + ecart + h2)) / 2
    d.text(((COTE - (b1[2] - b1[0])) / 2 - b1[0], y - b1[1]), "NI", font=f1, fill=gris)
    y += h1 + ecart
    d.rectangle([110, y, 290, y + trait], fill=gris)
    y += trait + ecart
    d.text(((COTE - (b2[2] - b2[0])) / 2 - b2[0], y - b2[1]), "NON-INSCRITS", font=f2, fill=gris)
    dest.parent.mkdir(parents=True, exist_ok=True)
    carre.save(dest, optimize=True)


def assurer():
    """Prépare les logos manquants (sans bloquer le passage en cas d'échec)."""
    marque = DOSSIER / ".version"
    if not marque.exists() or marque.read_text().strip() != VERSION:
        shutil.rmtree(DOSSIER, ignore_errors=True)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    marque.write_text(VERSION)
    if not (DOSSIER / "NI.png").exists():
        _non_inscrits(DOSSIER / "NI.png")
    for sigle, (modele, fichier, _l, _a) in LOGOS.items():
        dest = DOSSIER / f"{sigle}.png"
        if dest.exists():
            continue
        brut = BRUT / f"{sigle}.img"
        try:
            telecharger(modele.format(urllib.parse.quote(fichier.replace(" ", "_"))), brut, essais=2)
            _carre(brut, dest)
            print(f"Logo {sigle} prêt.")
        except Exception as e:  # noqa: BLE001
            print(f"Logo {sigle} indisponible : {e}")
            dest.unlink(missing_ok=True)


def exporter(groupes, out):
    """Copie les logos disponibles et ajoute au groupe le champ "logo" et ses crédits."""
    (out / "logos").mkdir(parents=True, exist_ok=True)
    for g in groupes.values():
        sigle = g.get("sigle")
        src = DOSSIER / f"{sigle}.png"
        if not src.exists() or (sigle not in LOGOS and sigle != "NI"):
            continue
        shutil.copy(src, out / "logos" / src.name)
        g["logo"] = f"logos/{src.name}"
        if sigle in LOGOS:
            modele, fichier, licence, auteur = LOGOS[sigle]
            lieu = "Wikimedia Commons" if modele == COMMONS else "Wikipédia"
            g["logo_credit"] = f"{auteur}, {licence}, via {lieu} ({fichier})"
