"""Garde-fous automatiques avant publication d'une synthèse.

Principe : la publication échoue « fermée ». Une seule anomalie bloque tout."""
import re
import unicodedata

from . import config

GUILLEMETS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"',
                            " ": " ", " ": " ", "–": "-", "—": "-", "…": "..."})


def normaliser(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(GUILLEMETS)
    return re.sub(r"\s+", " ", s).strip()


def verifier(reponse, passages_):
    """Retourne (synthese_publiable | None, erreurs)."""
    erreurs = []
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

    def controle_redaction(t, ou):
        if civilite.search(t):
            erreurs.append(f"{ou} : contient une formule désignant une personne.")
        for n in noms:
            if re.search(rf"\b{re.escape(n)}\b", t):
                erreurs.append(f"{ou} : contient le nom « {n} ».")

    controle_redaction(contexte, "Contexte")

    sortie = {"contexte": contexte, "pour": [], "contre": []}
    for camp in ("pour", "contre"):
        args = reponse.get(camp) or []
        if not isinstance(args, list):
            erreurs.append(f"« {camp} » n'est pas une liste.")
            continue
        if len(args) > config.ARGUMENTS_MAX_PAR_CAMP:
            erreurs.append(f"Trop d'arguments « {camp} » ({len(args)}).")
        for k, a in enumerate(args, 1):
            ou = f"Argument {camp} n°{k}"
            if not isinstance(a, dict):
                erreurs.append(f"{ou} : format invalide.")
                continue
            resume = normaliser(a.get("resume", ""))
            citation_brute = a.get("citation", "") or ""
            citation = normaliser(citation_brute)
            pid = (a.get("passage") or "").strip()
            if not resume or len(resume) > 300:
                erreurs.append(f"{ou} : résumé vide ou trop long.")
            controle_redaction(resume, ou)
            if pid not in par_id:
                erreurs.append(f"{ou} : passage « {pid} » inexistant.")
                continue
            if not (30 <= len(citation) <= 400):
                erreurs.append(f"{ou} : citation de longueur anormale ({len(citation)} caractères).")
            p = par_id[pid]
            if citation not in normaliser(p["texte"]):
                erreurs.append(f"{ou} : la citation ne figure pas mot pour mot dans {pid}.")
                continue
            # L'orateur est déterminé par le script, jamais par l'IA.
            sortie[camp].append({
                "resume": resume,
                "citation": citation,
                "acteur": p["acteur"],
                "nom": p["nom"],
                "qualite": p["qualite"],
                "syceron": p["syceron"],
            })
    if not sortie["pour"] and not sortie["contre"] and not erreurs:
        erreurs.append("Aucun argument retenu.")
    return (None if erreurs else sortie), erreurs
