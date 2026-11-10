"""« Ce que prévoit le texte » : résumé neutre de chaque texte examiné, une fois par dossier législatif.

- Source : le DISPOSITIF (les articles) du texte déposé à l'Assemblée, lu sur assemblee-nationale.fr.
  L'exposé des motifs, qui est un plaidoyer des auteurs, n'est jamais transmis à l'IA.
- IA : un seul appel par texte, 2 à 4 phrases descriptives.
- Vérification automatique avant publication (longueur, aucun nom de député, aucun mot de jugement).
- Un même résumé sert à tous les votes du dossier (vote final, motions, articles…).
Fichiers : data/resumes/<dossier>.json ; retraits : data/resumes_retires.txt."""
import html as html_mod
import json
import re
import time
from datetime import datetime, timezone

import requests

from . import config, synthese

DOSSIER = config.DATA / "resumes"
RETIRES = config.DATA / "resumes_retires.txt"
URL_TEXTE = config.AN + "/dyn/docs/{uid}.raw"
MAX_PAR_PASSAGE = 15
DISPOSITIF_MAX = 14000
MOTS_MAX = 110
JUGEMENTS = ["injuste", "dangereu", "scandal", "excellent", "inacceptable", "indispensable", "salutaire", "néfaste",
             "absurde", "inutile", "courageu", "historique", "honteu", "remarquable", "regrettable", "bienvenu",
             "malheureusement", "heureusement", "audacieu", "ambitieu", "laxiste", "liberticide"]

CONSIGNES = """Tu aides un site d'information citoyenne, neutre et non partisan.
On te donne le titre d'un texte examiné par l'Assemblée nationale et ses ARTICLES (le dispositif).
Écris "resume" : 2 à 4 phrases, 90 mots au maximum, qui disent concrètement ce que le texte prévoit
(ce qu'il crée, modifie, supprime, pour qui), au présent, en commençant par « Le texte ».

Règles strictes :
- décris seulement ce que prévoient les articles ; n'ajoute ni contexte, ni motivation, ni conséquence supposée ;
- aucun jugement, aucun adjectif d'appréciation, aucun nom de personne ni de parti ;
- si le texte est très long (budget…), donne ses grandes lignes ;
- si les articles sont illisibles ou absents, renvoie "resume": "".

Réponds UNIQUEMENT avec un objet JSON : {"resume": "..."}"""


def retires():
    if not RETIRES.exists():
        return set()
    return {l.split("#")[0].strip() for l in RETIRES.read_text(encoding="utf-8").splitlines() if l.split("#")[0].strip()}


def charger():
    DOSSIER.mkdir(parents=True, exist_ok=True)
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in DOSSIER.glob("*.json")}


def _sauver(ref, r):
    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / f"{ref}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def texte_brut(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>", "\n", h)
    t = html_mod.unescape(re.sub(r"<[^>]+>", " ", h))
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def dispositif(texte):
    """Partie normative du texte : les articles, après l'exposé des motifs (jamais l'exposé lui-même)."""
    i = re.search(r"EXPOS[ÉE] DES MOTIFS", texte, re.I)
    reste = texte[i.end():] if i else texte
    titre = re.search(r"\n\s*(proposition de loi|projet de loi|proposition de résolution)[^\n]{0,40}\n", reste, re.I)
    debut = titre.end() if titre else 0
    art = re.search(r"\n\s*Article\s+(1\s*er|premier|unique|liminaire|1)\b", reste[debut:], re.I)
    if art:
        return reste[debut + art.start():].strip()
    return reste[debut:].strip() if titre else ""


def verifier(resume, noms):
    erreurs = []
    if not resume:
        return ["résumé vide"]
    if len(resume.split()) > MOTS_MAX:
        erreurs.append("trop long")
    bas = resume.lower()
    for mot in JUGEMENTS:
        if re.search(r"\b" + mot, bas):
            erreurs.append(f"mot de jugement : {mot}")
    for nom in noms:
        if len(nom) > 3 and re.search(r"\b" + re.escape(nom) + r"\b", resume):
            erreurs.append(f"nom de député : {nom}")
    if re.search(r"\b(M\.|Mme|Monsieur|Madame)\s", resume):
        erreurs.append("désigne une personne")
    return erreurs


def traiter(scrutins, textes, deputes, rapport, args, budget_s):
    """Rédige les résumés manquants des dossiers ayant au moins un vote majeur, les plus récents d'abord."""
    resumes = charger()
    exclus = retires()
    recents = {}
    for s in scrutins.values():
        ref = s.get("dossier")
        if ref and s["categorie"]["niveau"] == 1 and ref in textes:
            recents[ref] = max(recents.get(ref, 0), s["num"])
    a_faire = [ref for ref in sorted(recents, key=lambda r: -recents[r])
               if ref not in exclus and (ref not in resumes or resumes[ref].get("statut") == "en_attente")]
    if not a_faire or args.sans_ia or args.fixtures:
        if a_faire:
            rapport.infos.append(f"[sans IA] {len(a_faire)} résumé(s) de texte à rédiger.")
        return
    noms = {d["nom"] for d in deputes.values() if d.get("nom")}
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    debut, faits, bloques = time.monotonic(), 0, 0
    for ref in a_faire[:MAX_PAR_PASSAGE]:
        if time.monotonic() - debut > budget_s:
            break
        uid = textes[ref]
        t0 = time.monotonic()
        r = resumes.get(ref) or {"dossier": ref, "texte": uid, "tentatives": 0}
        try:
            page = session.get(URL_TEXTE.format(uid=uid), timeout=60)
            page.raise_for_status()
            disp = dispositif(texte_brut(page.text))
        except requests.RequestException as e:
            print(f"Résumé {ref} : texte inaccessible ({e.__class__.__name__})")
            rapport.infos.append(f"Résumé {ref} : texte inaccessible ({e.__class__.__name__}).")
            continue
        if len(disp) < 80:
            r.update({"statut": "abandonne", "erreurs": ["articles introuvables dans le texte"]})
            _sauver(ref, r)
            continue
        titre = next((s.get("dossier_libelle") or s["titre"] for s in scrutins.values() if s.get("dossier") == ref), "")
        prompt = (CONSIGNES + f"\n\nTITRE : {titre}\n\nARTICLES :\n{disp[:DISPOSITIF_MAX]}"
                  + ("\n\n[Texte tronqué : résume ses grandes lignes.]" if len(disp) > DISPOSITIF_MAX else ""))
        try:
            reponse, modele = synthese.appeler_ia(prompt)
            resume = (synthese.lire_reponse(reponse).get("resume") or "").strip()
        except synthese.IAIndisponible as e:
            print(f"Résumé {ref} : IA indisponible ({e})")
            rapport.infos.append("IA indisponible pour les résumés de textes : nouvel essai au prochain passage.")
            break
        except (ValueError, AttributeError):
            resume, modele = "", ""
        erreurs = verifier(resume, noms)
        r["tentatives"] = r.get("tentatives", 0) + 1
        if erreurs:
            bloques += 1
            r.update({"statut": "abandonne" if r["tentatives"] >= 2 else "en_attente", "erreurs": erreurs})
        else:
            faits += 1
            r.update({"statut": "publie", "resume": resume, "modele": modele, "erreurs": [],
                      "genere_le": datetime.now(timezone.utc).isoformat(timespec="minutes")})
        _sauver(ref, r)
        print(f"Résumé {ref} ({uid}, {len(disp)} car.) : {r['statut']} {erreurs or ''} en {time.monotonic() - t0:.0f} s")
        time.sleep(config.PAUSE_ENTRE_SYNTHESES)
    print(f"Résumés de textes : {faits} publiés, {bloques} bloqués, {len(a_faire)} à faire au départ.")
    if faits or bloques:
        rapport.infos.append(f"Résumés de textes : {faits} publié(s), {bloques} bloqué(s) par la vérification, "
                             f"{max(0, len(a_faire) - faits - bloques)} restant(s).")


def pour_export():
    """{dossier: {...}} des résumés publiés et non retirés."""
    exclus = retires()
    return {ref: {k: r.get(k) for k in ("resume", "modele", "genere_le", "texte")}
            for ref, r in charger().items() if r.get("statut") == "publie" and ref not in exclus}
