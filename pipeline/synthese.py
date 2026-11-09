"""Synthèse « Le débat en bref » : un seul appel d'IA par vote majeur.

L'IA reçoit les interventions numérotées (P1, P2…), SANS le nom des orateurs.
Elle renvoie, pour chaque argument, le numéro du passage et une citation exacte.
C'est ensuite le script (verification.py) qui contrôle tout et rattache
chaque citation à son orateur à partir du compte rendu officiel."""
import json
import os
import re

import requests

from . import config

CONSIGNES = """Tu aides un site d'information citoyenne, neutre et non partisan, à résumer un débat de l'Assemblée nationale.

On te donne l'objet d'un vote et des extraits du compte rendu officiel, numérotés P1, P2… Les orateurs ne sont pas nommés : c'est volontaire.

Ta tâche :
1. "contexte" : 2 à 3 phrases factuelles qui expliquent ce sur quoi porte le vote, sans aucun jugement. 600 caractères maximum.
2. "pour" : les principaux arguments avancés EN FAVEUR de l'adoption de l'objet du vote.
3. "contre" : les principaux arguments avancés CONTRE l'adoption de l'objet du vote.

Pour chaque argument :
- "resume" : l'argument reformulé en une phrase neutre, 250 caractères maximum, sans nommer personne ni aucun groupe politique ;
- "passage" : le numéro du passage d'où il vient (ex. "P3") ;
- "citation" : une phrase ou un morceau de phrase recopié MOT POUR MOT depuis ce passage, entre 40 et 300 caractères, sans rien modifier (ni ponctuation, ni majuscules).

Règles strictes :
- au maximum 4 arguments par camp ; s'il y en a plus, garde les plus représentatifs et varie les passages ;
- n'invente rien : chaque argument doit être réellement exprimé dans son passage ;
- aucun nom de personne, aucun adjectif de jugement (« excellent », « scandaleux »…) dans "contexte" et "resume" ;
- si un camp n'a exprimé aucun argument, renvoie une liste vide pour ce camp.

Réponds UNIQUEMENT avec un objet JSON de la forme :
{"contexte": "...", "pour": [{"resume": "...", "passage": "P1", "citation": "..."}], "contre": [...]}"""


def construire_prompt(scrutin, passages_, erreurs_precedentes=None):
    lignes = [f"OBJET DU VOTE : {scrutin['titre']}"]
    if scrutin.get("dossier_libelle"):
        lignes.append(f"TEXTE : {scrutin['dossier_libelle']}")
    lignes.append("")
    for p in passages_:
        lignes.append(f"[{p['id']}]\n{p['texte']}\n")
    if erreurs_precedentes:
        lignes.append("ATTENTION, ta réponse précédente a été refusée pour ces raisons, corrige-les :")
        lignes.extend(f"- {e}" for e in erreurs_precedentes)
    return "\n".join(lignes)


def _modele():
    return config.IA_MODELE or config.MODELES_PAR_DEFAUT[config.IA_FOURNISSEUR]


def appeler_ia(prompt: str) -> str:
    fournisseur = config.IA_FOURNISSEUR
    modele = _modele()
    if fournisseur == "gemini":
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "systemInstruction": {"parts": [{"text": CONSIGNES}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    if fournisseur == "mistral":
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}"},
            json={"model": modele, "temperature": 0.2, "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": CONSIGNES},
                               {"role": "user", "content": prompt}]},
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    if fournisseur == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
            json={"model": modele, "max_tokens": 2000, "temperature": 0.2, "system": CONSIGNES,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=180,
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"])
    raise ValueError(f"Fournisseur d'IA inconnu : {fournisseur}")


def lire_reponse(texte: str):
    texte = texte.strip()
    texte = re.sub(r"^```(?:json)?\s*|\s*```$", "", texte)
    debut, fin = texte.find("{"), texte.rfind("}")
    return json.loads(texte[debut:fin + 1])


def description_modele():
    return f"{config.IA_FOURNISSEUR}:{_modele()}"
