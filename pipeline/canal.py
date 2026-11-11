"""Canal Telegram public : uniquement les votes importants, pensé pour être lu en quelques secondes sur téléphone.

- Chaque matin (passage quotidien), UN récapitulatif avec notification : chaque vote important de la veille,
  son résultat et la position de chaque groupe en carrés de couleur.
- Pour les votes les plus marquants (vote final sur un texte, motion de censure, scrutin solennel), un message
  détaillé SANS notification : hémicycle, résumé du texte, décompte.
- Quand la synthèse du débat est prête (quelques jours plus tard), le message détaillé est complété
  discrètement (modification, pas de nouvelle notification).
- Un message d'accueil épinglé, publié une seule fois.
Aucune donnée d'abonné ne transite par le site : Telegram gère seul les membres du canal."""
import re
import time
import unicodedata
from datetime import date

from . import config, image, presentation, resume, telegram

E = telegram.esc
CARRE = {"pour": "🟦", "contre": "🟥", "abstention": "⬜"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]

ACCUEIL = """👋 <b>Bienvenue sur Qui vote quoi ?</b>

Chaque matin, les votes importants de l'Assemblée nationale de la veille : le résultat, ce que prévoit le texte et le vote de chaque groupe politique.

🟦 pour · 🟥 contre · ⬜ abstention

🔔 Un récapitulatif par jour de séance, avec notification. Les messages détaillés (hémicycle, résumé du texte) arrivent sans bruit.
🔕 Pour lire à votre rythme : touchez le nom du canal, puis « Couper le son ».
📄 Les résumés de textes et de débats sont rédigés par une IA à partir des documents officiels, sans relecture humaine. Seuls les textes officiels font foi.
#️⃣ Touchez un mot-clé (#Finances, #AffairesSociales…) pour retrouver les votes d'un thème.

🔎 Tout le détail, député.e par député.e : {site}
Site indépendant et non officiel, sans publicité ni collecte de données."""


def _site():
    import os
    return os.environ.get("SITE_URL", "https://qui-vote-quoi-app.github.io/qui-vote-quoi")


def lien(s):
    return f"{_site()}/#s{s['num']}"


def date_fr(iso):
    a, m, j = (int(x) for x in iso.split("-"))
    return f"{j}{'er' if j == 1 else ''} {MOIS[m - 1]}"


def hashtag(theme):
    if not theme:
        return ""
    t = unicodedata.normalize("NFD", theme)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return "#" + "".join(m.capitalize() for m in re.findall(r"[A-Za-z0-9]+", t) if m.lower() not in ("et", "de", "la", "des"))


def titre_court(s):
    """Titre lisible : l'intitulé du dossier (« Projet de loi de finances pour 2027 ») plutôt que l'intitulé
    officiel du scrutin, complété par la nature du vote quand ce n'est pas le vote final."""
    t = (s.get("titre") or "").lower()
    base = (s.get("dossier_libelle") or "").strip()
    base = base[:1].upper() + base[1:]
    cle = s["categorie"]["cle"]
    if cle == "censure":
        return "Motion de censure" + (f" · {base}" if base else "")
    if cle == "motion":
        nature = ("motion de rejet préalable" if "rejet préalable" in t else
                  "motion de renvoi en commission" if "renvoi en commission" in t else "motion de procédure")
        return f"{base} : {nature}" if base else nature[:1].upper() + nature[1:]
    if base:
        precision = []
        if "première partie" in t:
            precision.append("première partie (recettes)")
        if "commission mixte paritaire" in t:
            precision.append("texte de compromis avec le Sénat")
        elif "lecture définitive" in t:
            precision.append("lecture définitive")
        elif "nouvelle lecture" in t:
            precision.append("nouvelle lecture")
        return base + (f" : {', '.join(precision)}" if precision else "")
    titre = s.get("titre") or ""
    titre = re.sub(r"^l[’']ensemble (du|de la|des) ", "", titre)
    titre = titre[:1].upper() + titre[1:]
    return titre if len(titre) <= 140 else titre[:137].rstrip() + "…"


def consequence(s):
    """Une ligne qui dit ce que le résultat change, quand c'est utile."""
    t = (s.get("titre") or "").lower()
    adopte = s["sort"] == "adopté"
    cle = s["categorie"]["cle"]
    if cle == "censure":
        return "Le Gouvernement doit démissionner." if adopte else "Le Gouvernement reste en place."
    if cle == "motion" and "rejet préalable" in t:
        return "Le texte est rejeté sans examen de ses articles." if adopte else "L'examen du texte continue."
    if cle == "motion" and "renvoi en commission" in t:
        return "Le texte retourne en commission." if adopte else "L'examen du texte continue."
    return ""


def positions(s, groupes):
    par = {"pour": [], "contre": [], "abstention": []}
    gs = sorted(s.get("groupes") or [], key=lambda g: (groupes.get(g.get("po")) or {}).get("ordre") or 99)
    for g in gs:
        sigle = (groupes.get(g.get("po")) or {}).get("sigle")
        if sigle and g.get("position") in par:
            par[g["position"]].append(E(sigle))
    return [f"{CARRE[k]} {' · '.join(v)}" for k, v in par.items() if v]


def marquant(s):
    return s["categorie"]["cle"] in ("ensemble", "censure") or s.get("type") == "SPS"


def bloc_recap(s, groupes):
    ok = s["sort"] == "adopté"
    lignes = [f"{'✅' if ok else '❌'} <b>{E(titre_court(s))}</b>",
              f"<b>{'Adopté' if ok else 'Rejeté'}</b> · {s['pour']} pour, {s['contre']} contre"
              + (f", {s['abst']} abst." if s["abst"] else "")]
    c = consequence(s)
    if c:
        lignes.append(f"<i>{E(c)}</i>")
    lignes += positions(s, groupes)
    lignes.append(f'<a href="{lien(s)}">Voir qui a voté quoi →</a>')
    return "\n".join(lignes)


def legende_detail(s, groupes, txt):
    """Légende de la carte image : titre et nombres sont déjà sur l'image, la légende dit le reste."""
    ok = s["sort"] == "adopté"
    if txt:
        explication = (f"<b>📄 Ce que prévoit le texte</b>\n<blockquote expandable>{E(txt[:520])}</blockquote>"
                       "<i>Résumé rédigé par IA à partir du texte officiel.</i>")
    else:
        explication = f"<blockquote>{E(presentation.en_bref(s)[:400])}</blockquote>"
    c = consequence(s)
    morceaux = [f"{'✅' if ok else '❌'} <b>{E(titre_court(s)[:150])}</b> · {'adopté' if ok else 'rejeté'}"
                + (f"\n<i>{E(c)}</i>" if c else ""),
                explication,
                "<b>Le vote des groupes</b>\n" + "\n".join(positions(s, groupes)),
                hashtag(s.get("theme"))]
    return "\n\n".join(m for m in morceaux if m)


def boutons_detail(s, debat=False):
    ligne = [("🔎 Qui a voté quoi", lien(s))]
    if s.get("dossier"):
        ligne.append(("📜 Texte officiel", f"{config.AN}/dyn/17/dossiers/{s['dossier']}"))
    return [ligne] + ([[("💬 Le débat en bref", lien(s))]] if debat else [])


def accueil(chat, etat):
    if etat.get("canal_accueil"):
        return
    mid = telegram.message(ACCUEIL.format(site=_site()), chat=chat, silencieux=True)
    if mid:
        try:
            telegram.epingler(chat, mid)
        except Exception as e:  # noqa: BLE001 — l'épinglage demande le droit correspondant
            print(f"Épinglage impossible : {e}")
        etat["canal_accueil"] = mid


def publier(rapport, groupes, etat):
    chat = telegram.canal()
    if not chat:
        return
    accueil(chat, etat)
    messages = etat.setdefault("canal_messages", {})
    resumes = resume.pour_export()

    # 1. Messages détaillés, sans notification, pour les votes les plus marquants.
    majeurs = sorted((s for s in rapport.nouveaux if s["categorie"]["niveau"] == 1), key=lambda s: s["num"])
    for s in [s for s in majeurs if marquant(s)][:8]:
        txt = (resumes.get(s.get("dossier")) or {}).get("resume")
        legende = legende_detail(s, groupes, txt)
        chemin = image.dessiner(s, config.CACHE / f"canal_{s['num']}.png", titre=titre_court(s))
        mid = telegram.photo(chemin, legende, chat=chat, silencieux=True, boutons=boutons_detail(s))
        if mid:
            messages[str(s["num"])] = {"id": mid, "legende": legende, "dossier": s.get("dossier")}
        time.sleep(1)

    # 2. Récapitulatif avec notification (envoyé en dernier : c'est lui qu'on ouvre en premier).
    if majeurs:
        dates = sorted({s["date"] for s in majeurs})
        quand = date_fr(dates[0]) if len(dates) == 1 else f"du {date_fr(dates[0])} au {date_fr(dates[-1])}"
        n = len(majeurs)
        tete = (f"🏛 <b>À L'ASSEMBLÉE · {quand.upper()}</b>\n"
                f"{n} vote{'s' if n > 1 else ''} important{'s' if n > 1 else ''}\n━━━━━━━━━━━━━━━")
        blocs = [bloc_recap(s, groupes) for s in majeurs]
        tags = " ".join(sorted({hashtag(s.get("theme")) for s in majeurs if s.get("theme")}))
        morceaux, courant = [], tete
        for b in blocs:
            if len(courant) + len(b) + 2 > 3800:
                morceaux.append(courant)
                courant = ""
            courant += "\n\n" + b
        morceaux.append(courant + (f"\n\n{tags}" if tags else ""))
        for k, m in enumerate(morceaux):
            dernier = k == len(morceaux) - 1
            telegram.message(m.strip(), chat=chat, silencieux=not dernier,
                             boutons=[[("🌐 Tous les votes sur le site", _site())]] if dernier else None)

    # 3. Synthèse du débat prête : on complète discrètement le message détaillé.
    for s in rapport.publiees:
        m = messages.get(str(s["num"]))
        if m and not m.get("debat"):
            m["debat"] = True
            try:
                telegram.modifier_legende(chat, m["id"], m["legende"], boutons=boutons_detail(s, debat=True))
            except Exception as e:  # noqa: BLE001
                print(f"Mise à jour du message {m['id']} impossible : {e}")
    # Ne garder que les 200 derniers messages suivis.
    for k in sorted(messages, key=int)[:-200]:
        del messages[k]
    etat["canal_maj"] = date.today().isoformat()
