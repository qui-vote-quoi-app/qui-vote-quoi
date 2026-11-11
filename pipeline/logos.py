"""Logos des groupes politiques, tirés de Wikimedia Commons (licences libres ou domaine public).

Téléchargés une seule fois dans data/logos/<SIGLE>.png (vignette 320 px fournie par Commons),
puis copiés dans le site. Un groupe sans logo garde son carré de couleur.
Les crédits (auteur, licence, fichier source) sont affichés dans les mentions légales."""
import shutil
import urllib.parse

from . import config
from .sources import telecharger

COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/{}?width=320"
# sigle -> (fichier Commons, licence, auteur indiqué sur Commons)
LOGOS = {
    "RN": ("Groupe RN 2024.png", "CC BY-SA 4.0", "Rassemblement National"),
    "EPR": ("Groupe EPR.png", "CC BY 4.0", "Ensemble pour la République"),
    "LFI-NFP": ("Groupe La France insoumise Logo.jpg", "CC0", "auteur inconnu"),
    "SOC": ("Le Parti socialiste wordmark.svg", "domaine public", "Parti socialiste"),
    "DR": ("La Droite Républicaine logo 2024.png", "CC BY-SA 4.0", "La Droite Républicaine"),
    "ECOS": ("Ecologiste 2024.png", "CC BY 4.0", "Groupe écologiste et social"),
    "DEM": ("DemsFrance.png", "CC BY 4.0", "Groupe Les Démocrates"),
    "HOR": ("Logo Horizons.svg", "domaine public", "Horizons"),
    "LIOT": ("LIOT Group.png", "CC BY-SA 3.0", "Groupe LIOT"),
    "GDR": ("Logo GDR.svg", "CC BY-SA 4.0", "Groupe de la Gauche démocrate et républicaine"),
    "UDR": ("UDR logo.svg", "domaine public", "Union des droites pour la République"),
}
DOSSIER = config.DATA / "logos"


def assurer():
    """Télécharge les logos manquants (sans bloquer le passage en cas d'échec)."""
    for sigle, (fichier, _l, _a) in LOGOS.items():
        dest = DOSSIER / f"{sigle}.png"
        if dest.exists():
            continue
        try:
            telecharger(COMMONS.format(urllib.parse.quote(fichier.replace(" ", "_"))), dest, essais=2)
            print(f"Logo {sigle} téléchargé.")
        except Exception as e:  # noqa: BLE001
            print(f"Logo {sigle} indisponible : {e}")
            dest.unlink(missing_ok=True)


def exporter(groupes, out):
    """Copie les logos disponibles et ajoute au groupe le champ "logo" et ses crédits."""
    (out / "logos").mkdir(parents=True, exist_ok=True)
    for g in groupes.values():
        src = DOSSIER / f"{g.get('sigle')}.png"
        if g.get("sigle") in LOGOS and src.exists():
            shutil.copy(src, out / "logos" / src.name)
            fichier, licence, auteur = LOGOS[g["sigle"]]
            g["logo"] = f"logos/{src.name}"
            g["logo_credit"] = f"{auteur}, {licence}, via Wikimedia Commons ({fichier})"
