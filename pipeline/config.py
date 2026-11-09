"""Configuration centrale de « Qui vote quoi ? »."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
SITE_DATA = SITE / "data"
CACHE = ROOT / ".cache"
SYNTHESES = DATA / "syntheses"
ETAT = DATA / "etat.json"
RETRAITS = DATA / "retraits.txt"
PLACES = DATA / "places_hemicycle.json"

LEGISLATURE = "17"
BASE = f"https://data.assemblee-nationale.fr/static/openData/repository/{LEGISLATURE}"
URL_SCRUTINS = f"{BASE}/loi/scrutins/Scrutins.json.zip"
URL_ACTEURS = (
    f"{BASE}/amo/tous_acteurs_mandats_organes_xi_legislature/"
    "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip"
)
URL_COMPTES_RENDUS = f"{BASE}/vp/syceronbrut/syseron.xml.zip"

AN = "https://www.assemblee-nationale.fr"

# Synthèses
CR_DELAI_MAX_JOURS = 7          # au-delà, on abandonne et on alerte
SEGMENT_MAX_CARACTERES = 60000  # contexte maximal envoyé à l'IA
ARGUMENTS_MAX_PAR_CAMP = 4

# Fournisseur d'IA : "gemini" (gratuit), "mistral" ou "anthropic"
IA_FOURNISSEUR = os.environ.get("IA_FOURNISSEUR", "gemini")
IA_MODELE = os.environ.get("IA_MODELE", "")
MODELES_PAR_DEFAUT = {
    "gemini": "gemini-flash-latest",
    "mistral": "mistral-small-latest",
    "anthropic": "claude-sonnet-5-5",
}

USER_AGENT = "qui-vote-quoi/1.0 (+https://github.com/qui-vote-quoi-app/qui-vote-quoi)"
