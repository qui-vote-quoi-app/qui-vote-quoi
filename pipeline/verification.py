"""Garde-fous automatiques avant publication d'une synthèse.

Principe : rien de non vérifié n'est publié.
- Un argument dont la citation n'est pas retrouvée mot pour mot (ou dont le résumé désigne quelqu'un)
  est écarté : il n'est jamais publié.
- La synthèse entière est bloquée si le contexte est fautif, si la réponse est mal formée, ou si un camp
  perd TOUS ses arguments (sinon le site afficherait à tort qu'aucun orateur n'a défendu cette position)."""
import re
import unicodedata

from . import config

GUILLEMETS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"',
                            " ": " ", " ": " ", "–": "-", "—": "-", "…": "..."})


def normaliser(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(GUILLEMETS)
    return re.sub(r"\s+", " ", s).strip()


def verifier(reponse, passages_):
    """Retourne (synthese_publiable | None, erreurs). Les arguments écartés sont listés dans
    sortie["ecartes"] sans bloquer la publication."""
    erreurs, ecartes = [], []
    par_id = {p["id"]: p for p in passages_}
    if not isinstance(reponse, dict):
        return None, ["La réponse n'est pas un objet JSON."]

    contexte = normaliser(reponse.get("contexte", ""))
    if not contexte:
        erreurs.append("Le contexte est vide.")
    if len(contexte) > 700:
        erreurs.append("Le contexte dépasse 700 caractères.")

    # Noms interdits dans les textes rédigés par l'IA : noms des orateurs du passage,
    # et toute formule de civilité suivie d'un nom.
    noms = set()
    for p in passages_:
        for mot in re.findall(r"[A-ZÉÈÀÂÎÔÛÇ][\w'’-]{2,}", p["nom"]):
            if mot not in ("Mme", "M.", "Monsieur", "Madame"):
                noms.add(normaliser(mot))
    civilite = re.compile(r"\b(M\.|Mme|Monsieur|Madame)\s+[A-ZÉ]")

    def controle_redaction(t, ou, liste):
        if civilite.search(t):
            liste.append(f"{ou} : contient une formule désignant une personne.")
        for n in noms:
            if re.search(rf"\b{re.escape(n)}\b", t):
                liste.append(f"{ou} : contient le nom « {n} ».")

    controle_redaction(contexte, "Contexte", erreurs)

    sortie = {"contexte": contexte, "pour": [], "contre": []}
    for camp in ("pour", "contre"):
        args = reponse.get(camp) or []
        if not isinstance(args, list):
            erreurs.append(f"« {camp} » n'est pas une liste.")
            continue
        args = args[:config.ARGUMENTS_MAX_PAR_CAMP]
        for k, a in enumerate(args, 1):
            ou = f"Argument {camp} n°{k}"
            if not isinstance(a, dict):
                ecartes.append(f"{ou} : format invalide.")
                continue
            resume = normaliser(a.get("resume", ""))
            citation = normaliser(a.get("citation", "") or "")
            pid = (a.get("passage") or "").strip()
            probleme = []
            if not resume or len(resume) > 300:
                probleme.append(f"{ou} : résumé vide ou trop long.")
            controle_redaction(resume, ou, probleme)
            if pid not in par_id:
                probleme.append(f"{ou} : passage « {pid} » inexistant.")
            elif not (30 <= len(citation) <= 400):
                probleme.append(f"{ou} : citation de longueur anormale ({len(citation)} caractères).")
            elif citation not in normaliser(par_id[pid]["texte"]):
                probleme.append(f"{ou} : la citation ne figure pas mot pour mot dans {pid}.")
            if probleme:
                ecartes.extend(probleme)
                continue
            p = par_id[pid]
            # L'orateur est déterminé par le script, jamais par l'IA.
            sortie[camp].append({
                "resume": resume,
                "citation": citation,
                "acteur": p["acteur"],
                "nom": p["nom"],
                "qualite": p["qualite"],
                "syceron": p["syceron"],
            })
        if args and not sortie[camp]:
            erreurs.append(f"Aucun argument « {camp} » vérifiable sur {len(args)} proposé(s).")
    if not sortie["pour"] and not sortie["contre"] and not erreurs:
        erreurs.append("Aucun argument retenu.")
    if erreurs:
        return None, erreurs + ecartes
    sortie["ecartes"] = ecartes
    return sortie, []
