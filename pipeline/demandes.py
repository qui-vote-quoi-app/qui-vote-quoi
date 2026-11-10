"""Traitement automatique des demandes publiques (formulaires GitHub « Demander un retrait » et « Signaler une erreur »).

Principe : dans le doute, on retire. Un contenu rédigé par IA (synthèse du débat, résumé du texte)
ou une photo est dépublié dès la demande, sans examen, et ne revient jamais automatiquement.
Les chiffres de vote, eux, viennent tels quels de l'Assemblée : la réponse renvoie vers la source officielle.

Lit l'issue dans GITHUB_EVENT_PATH, modifie data/, répond sur l'issue et écrit dans GITHUB_OUTPUT :
  publier=true|false  (republier le site)
Le texte de l'issue n'est jamais exécuté ni passé à un shell."""
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone

import requests

from . import config, resume, telegram

SITE = os.environ.get("SITE_URL", "https://qui-vote-quoi-app.github.io/qui-vote-quoi")
DEPOT = os.environ.get("GITHUB_REPOSITORY", "qui-vote-quoi-app/qui-vote-quoi")
LIMITE_24H = 3   # au-delà, les demandes d'une même personne attendent un examen humain


def champs(corps):
    """Formulaire GitHub rendu en Markdown : « ### Libellé » puis la valeur."""
    res, cle = {}, None
    for ligne in (corps or "").splitlines():
        m = re.match(r"^###\s+(.*)", ligne)
        if m:
            cle = m.group(1).strip()
            res[cle] = ""
        elif cle is not None:
            res[cle] += ligne + "\n"
    return {k: ("" if v.strip() == "_No response_" else v.strip()) for k, v in res.items()}


def valeur(f, *debuts):
    for k, v in f.items():
        if any(k.lower().startswith(d.lower()) for d in debuts):
            return v
    return ""


def norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def commenter(num, texte, fermer=False, labels=()):
    gh("issue", "comment", str(num), "--repo", DEPOT, "--body", texte)
    for l in labels:
        try:
            gh("issue", "edit", str(num), "--repo", DEPOT, "--add-label", l)
        except subprocess.CalledProcessError:
            pass
    if fermer:
        gh("issue", "close", str(num), "--repo", DEPOT)


def demandes_recentes(auteur):
    depuis = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sortie = gh("issue", "list", "--repo", DEPOT, "--author", auteur, "--state", "all", "--search", f"created:>{depuis}",
                "--json", "number", "--limit", "50")
    return len(json.loads(sortie or "[]"))


def site_json(chemin):
    r = requests.get(f"{SITE}/data/{chemin}", timeout=60)
    r.raise_for_status()
    return r.json()


def scrutin(num):
    return site_json(f"scrutins/{num // 100}.json").get(str(num))


def numero(texte):
    m = re.search(r"(?:#s|n°\s*|scrutins?/|^|\s)(\d{3,5})\b", texte or "")
    return int(m.group(1)) if m else None


def trouver_depute(texte):
    m = re.search(r"PA\d{3,7}", texte or "")
    deps = site_json("deputes.json")
    if m:
        return next((d for d in deps if d["id"] == m.group(0)), None)
    q = norm(texte)
    if not q:
        return None
    trouves = [d for d in deps if norm(d["prenom"] + " " + d["nom"]) in q]
    if not trouves:
        trouves = [d for d in deps if q == norm(d["nom"])]
    return trouves[0] if len(trouves) == 1 else None


def ajouter_ligne(fichier, ligne):
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with open(fichier, "a", encoding="utf-8") as f:
        f.write(ligne.rstrip("\n") + "\n")


def retirer_synthese(num, motif):
    uid = f"VTANR5L{config.LEGISLATURE}V{num}"
    ajouter_ligne(config.RETRAITS, f"{uid}\t{date.today().isoformat()}\t{motif}")
    f = config.SYNTHESES / f"{uid}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        d["statut"] = "retiree"
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def traiter(evenement):
    issue = evenement["issue"]
    num, auteur = issue["number"], issue["user"]["login"]
    labels = {l["name"] for l in issue.get("labels", [])}
    if "traité" in labels or issue.get("state") != "open":
        return False
    f = champs(issue.get("body"))
    quoi = valeur(f, "Que faut-il retirer", "Type d'erreur")
    motif = re.sub(r"\s+", " ", valeur(f, "Motif", "Ce qui est inexact"))[:200].replace("\t", " ")
    ref = f"issue #{num}"

    if "retrait" not in labels and "erreur" not in labels:
        return False
    if demandes_recentes(auteur) > LIMITE_24H:
        commenter(num, "Merci. Plusieurs demandes ont été reçues de votre part aujourd'hui : celle-ci sera examinée "
                       "par l'éditeur.", labels=["à examiner"])
        telegram.message(f"⚠️ Demande #{num} mise en attente (limite quotidienne) : {issue['html_url']}")
        return False

    q = quoi.lower()
    if "synthèse" in q or "résumé" in q:
        n = numero(valeur(f, "Numéro du scrutin") or issue.get("title", ""))
        s = scrutin(n) if n else None
        if not s:
            commenter(num, "Merci. Le numéro du scrutin n'a pas été reconnu : pouvez-vous l'indiquer (par exemple "
                           "9759, visible en haut de la page du vote) en modifiant votre demande ?")
            return False
        if "synthèse" in q:
            retirer_synthese(n, f"{ref} : {motif}")
            quoi_txt = "La synthèse du débat"
        else:
            if not s.get("dossier"):
                commenter(num, "Ce vote n'a pas de résumé de texte : rien à retirer.", fermer=True, labels=["traité"])
                return False
            ajouter_ligne(resume.RETIRES, f"{s['dossier']}\t# {date.today().isoformat()} {ref} : {motif}")
            quoi_txt = "Le résumé du texte (il concerne tous les votes de ce texte)"
        commenter(num, f"Merci. {quoi_txt} du scrutin n° {n} est **retiré** du site par précaution ; "
                       "la publication prend quelques minutes. Il ne sera pas republié automatiquement.\n\n"
                       f"Page du vote : {SITE}/#s{n}", fermer=True, labels=["traité"])
        telegram.message(f"🧹 Retrait automatique ({quoi_txt.lower()}, scrutin {n}) suite à la demande #{num} : "
                         f"{issue['html_url']}")
        return True

    if "photo" in q:
        d = trouver_depute(" ".join([valeur(f, "Député"), valeur(f, "Ce qui est inexact"), issue.get("title", "")]))
        if not d:
            commenter(num, "Merci. Le député n'a pas été reconnu : indiquez son prénom et son nom, ou collez le lien "
                           "de sa page sur ce site, en modifiant votre demande.")
            return False
        ajouter_ligne(config.DATA / "photos_retirees.txt", f"{d['id']}  # {date.today().isoformat()} {ref}")
        commenter(num, f"Merci. La photo de {d['prenom']} {d['nom']} est **retirée** du site ; la publication prend "
                       "quelques minutes.", fermer=True, labels=["traité"])
        telegram.message(f"🧹 Photo retirée ({d['prenom']} {d['nom']}) suite à la demande #{num}")
        return True

    if "résultat" in q or "position" in q:
        n = numero(valeur(f, "Numéro du scrutin") or issue.get("title", ""))
        lien = f"{config.AN}/dyn/17/scrutins/{n}" if n else f"{config.AN}/dyn/17/scrutins"
        commenter(num, "Merci pour ce signalement. Les résultats et les positions de vote sont repris **tels quels** "
                       "des données officielles de l'Assemblée nationale, resynchronisées chaque matin. Vous pouvez "
                       f"comparer avec la page officielle du scrutin : {lien}\n\n"
                       "Si un député estime que son vote a été mal enregistré, il peut faire une « mise au point » "
                       "auprès de l'Assemblée ; elle apparaîtra ici automatiquement. Si l'écart vient de ce site et non "
                       "de la source, l'éditeur en est prévenu.", fermer=True, labels=["traité"])
        telegram.message(f"ℹ️ Signalement #{num} (résultat ou position de vote), réponse automatique envoyée : "
                         f"{issue['html_url']}")
        return False

    commenter(num, "Merci pour ce signalement : il a été transmis à l'éditeur.", labels=["à examiner"])
    telegram.message(f"📬 Signalement à examiner #{num} : {issue['html_url']}")
    return False


def main():
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
        evenement = json.load(fh)
    try:
        publier = traiter(evenement)
    except Exception as e:  # noqa: BLE001
        telegram.message(f"🔥 Traitement automatique de la demande impossible : {telegram.esc(e)}")
        raise
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"publier={'true' if publier else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())
