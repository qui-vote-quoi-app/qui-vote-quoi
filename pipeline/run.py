"""Point d'entrée du pipeline quotidien.

  python -m pipeline.run                      # passage quotidien complet
  python -m pipeline.run --mode syntheses     # ne traite que les synthèses en attente
  python -m pipeline.run --retrait 9759 --raison "..."   # dépublie une synthèse
  python -m pipeline.run --fixtures tests/fixtures --sans-ia   # test hors ligne
"""
import argparse
import os
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

from . import logos
from . import config, debats, donnees, export, image, synthese, telegram, verification, photos, communes, circos, presentation, resume, canal
from .sources import ZipDistant, charger_json, ecrire_json, entete, telecharger

SITE_URL = os.environ.get("SITE_URL", "https://qui-vote-quoi-app.github.io/qui-vote-quoi").rstrip("/")


# ------------------------------------------------------------------ utilitaires

def maintenant():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def charger_syntheses():
    out = {}
    for f in sorted(config.SYNTHESES.glob("*.json")):
        s = charger_json(f, None)
        if s:
            out[s["uid"]] = s
    return out


def sauver_synthese(s):
    ecrire_json(config.SYNTHESES / f"{s['uid']}.json", s)


def charger_retraits():
    if not config.RETRAITS.exists():
        return set()
    return {l.split("\t")[0].strip() for l in config.RETRAITS.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


class ZipFixtures:
    """Remplace ZipDistant pour les tests : lit des XML dans un dossier local."""

    def __init__(self, dossier):
        self.dossier = Path(dossier)
        self.entrees = {f"xml/compteRendu/{p.name}": p for p in self.dossier.glob("CRSA*.xml")}

    def lire(self, nom):
        return self.entrees[nom].read_bytes()

    def lire_debut(self, nom, octets=4000):
        return self.entrees[nom].read_bytes()[:octets]


class Rapport:
    def __init__(self):
        self.nouveaux, self.publiees, self.refusees, self.abandonnees = [], [], [], []
        self.en_attente, self.erreurs, self.infos = [], [], []
        self.ia_indisponible = []


# ------------------------------------------------------------------ étapes

def charger_sources(args, etat):
    """Télécharge (ou lit en local) les dumps scrutins et acteurs."""
    if args.fixtures:
        import json, zipfile, io
        fx = Path(args.fixtures)
        tmp = config.CACHE / "fixtures"
        tmp.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp / "scrutins.zip", "w") as z:
            for p in fx.glob("scrutin_*.json"):
                z.write(p, f"json/{p.name.replace('scrutin_', '')}")
        with zipfile.ZipFile(tmp / "acteurs.zip", "w") as z:
            for p in fx.glob("acteur_*.json"):
                z.write(p, f"json/acteur/{p.name.replace('acteur_', '')}")
            for p in fx.glob("organe_*.json"):
                z.write(p, f"json/organe/{p.name.replace('organe_', '')}")
        with zipfile.ZipFile(tmp / "dossiers.zip", "w") as z:
            for p in fx.glob("dossier_*.json"):
                z.write(p, f"json/dossierParlementaire/{p.name.replace('dossier_', '')}")
            for p in fx.glob("document_*.json"):
                z.write(p, f"json/document/{p.name.replace('document_', '')}")
        return ({"scrutins": tmp / "scrutins.zip", "acteurs": tmp / "acteurs.zip", "dossiers": tmp / "dossiers.zip"},
                {"scrutins": "fixtures", "acteurs": "fixtures"})

    dates = {}
    chemins = {}
    for cle, url in [("scrutins", config.URL_SCRUTINS), ("acteurs", config.URL_ACTEURS),
                     ("dossiers", config.URL_DOSSIERS)]:
        info = entete(url)
        dates[cle] = info["modifie"]
        dest = config.CACHE / f"{cle}.zip"
        if not dest.exists() or etat.get("etags", {}).get(url) != info["etag"]:
            telecharger(url, dest)
        etat.setdefault("etags", {})[url] = info["etag"]
        chemins[cle] = dest
    dates.pop("dossiers", None)
    return chemins, dates


def detecter_nouveaux(scrutins, etat, syntheses, rapport):
    dernier = etat.get("dernier_num")
    numeros = sorted(s["num"] for s in scrutins.values())
    if not numeros:
        return
    if dernier is None:
        # Première exécution : pas d'avalanche de notifications.
        # On ne prépare des synthèses que pour les votes des 7 derniers jours.
        rapport.infos.append(f"Initialisation : {len(numeros)} scrutins chargés.")
        limite = date.today().toordinal() - 7
        candidats = [s for s in scrutins.values() if avec_synthese(s)
                     and date.fromisoformat(s["date"]).toordinal() >= limite]
    else:
        nouveaux = [s for s in scrutins.values() if s["num"] > dernier]
        nouveaux.sort(key=lambda s: s["num"])
        rapport.nouveaux = nouveaux
        candidats = [s for s in nouveaux if avec_synthese(s)]
    programmer(candidats, syntheses)
    etat["dernier_num"] = numeros[-1]


def avec_synthese(s):
    return s["categorie"]["cle"] in config.CATEGORIES_AVEC_SYNTHESE


def programmer(candidats, syntheses):
    n = 0
    for s in candidats:
        if s["uid"] not in syntheses:
            syntheses[s["uid"]] = {"uid": s["uid"], "num": s["num"], "statut": "en_attente",
                                   "cree_le": maintenant(), "tentatives": 0, "erreurs": []}
            sauver_synthese(syntheses[s["uid"]])
            n += 1
    return n


def rattrapage(scrutins, syntheses, jours, rapport):
    """Programme une synthèse pour chaque vote sur l'ensemble des N derniers jours."""
    limite = date.today().toordinal() - jours
    candidats = sorted((s for s in scrutins.values() if avec_synthese(s)
                        and date.fromisoformat(s["date"]).toordinal() >= limite), key=lambda s: -s["num"])
    n = programmer(candidats, syntheses)
    rapport.infos.append(f"Rattrapage sur {jours} jours : {len(candidats)} vote(s) sur l'ensemble, "
                         f"{n} synthèse(s) ajoutée(s) à la file.")


def traiter_syntheses(scrutins, syntheses, etat, args, rapport):
    attente = [s for s in syntheses.values() if s["statut"] == "en_attente" and s["uid"] in scrutins]
    if not attente:
        return
    zcr = ZipFixtures(args.fixtures) if args.fixtures else ZipDistant(config.URL_COMPTES_RENDUS)
    index = etat.setdefault("cr_index", {})
    for nom in zcr.entrees:
        if nom.endswith(".xml") and nom not in index:
            index[nom] = debats.seance_du_fichier(zcr.lire_debut(nom))

    # Les votes les plus récents d'abord ; au-delà du plafond, le reste attend le passage suivant.
    attente.sort(key=lambda x: -x["num"])
    a_traiter, reportees = attente[:config.SYNTHESES_MAX_PAR_PASSAGE], attente[config.SYNTHESES_MAX_PAR_PASSAGE:]
    if reportees:
        rapport.infos.append(f"{len(reportees)} synthèse(s) reportée(s) au prochain passage (plafond par passage).")
    appels, debut, ia_hs, pannes = 0, time.monotonic(), False, 0
    for syn in a_traiter:
        if time.monotonic() - debut > config.BUDGET_SYNTHESES_MINUTES * 60:
            rapport.infos.append("Temps alloué aux synthèses écoulé : la suite est reportée au prochain passage.")
            break
        s = scrutins[syn["uid"]]
        # Délai compté depuis la mise en file (et pas depuis le vote), pour que le rattrapage
        # de votes anciens ne soit pas abandonné à la première difficulté.
        cree = date.fromisoformat((syn.get("cree_le") or s["date"])[:10])
        age = date.today().toordinal() - max(cree, date.fromisoformat(s["date"])).toordinal()
        fichiers = [n for n, seance in index.items() if seance == s["seance"]]
        meta, passages = None, None
        for f in fichiers:
            meta, passages = debats.extraire(zcr.lire(f), s)
            if passages is not None:
                syn["cr"] = meta["uid"]
                syn["seance_jour"] = meta["jour"]
                break
        if passages is None:
            if age > config.CR_DELAI_MAX_JOURS:
                syn["statut"] = "abandonnee"
                syn["erreurs"] = ["Compte rendu introuvable ou vote non localisé après "
                                  f"{config.CR_DELAI_MAX_JOURS} jours."]
                rapport.abandonnees.append(s)
            else:
                rapport.en_attente.append(s)
            sauver_synthese(syn)
            continue
        if not passages:
            syn["statut"] = "abandonnee"
            syn["erreurs"] = ["Aucune intervention de fond avant ce vote."]
            rapport.abandonnees.append(s)
            sauver_synthese(syn)
            continue
        if args.sans_ia:
            rapport.infos.append(f"[sans IA] scrutin {s['num']} : {len(passages)} passages prêts "
                                 f"({sum(len(p['texte']) for p in passages)} caractères).")
            rapport.en_attente.append(s)
            continue

        if ia_hs:  # IA en panne (trois échecs d'affilée) : inutile d'insister pendant ce passage
            rapport.ia_indisponible.append(s)
            continue
        if appels and not args.fixtures:
            time.sleep(config.PAUSE_ENTRE_SYNTHESES)
        appels += 1
        erreurs, publiable, panne = None, None, None
        for _ in range(2):  # une tentative + une relance avec les erreurs de vérification
            syn["tentatives"] = syn.get("tentatives", 0) + 1
            try:
                brut, modele = synthese.appeler_ia(synthese.construire_prompt(s, passages, erreurs))
            except synthese.IAIndisponible as e:
                panne = str(e)  # service saturé ou quota : on réessaiera au prochain passage
                pannes += 1
                ia_hs = pannes >= 3  # trois pannes d'affilée : inutile d'insister pendant ce passage
                break
            pannes = 0
            try:
                publiable, erreurs = verification.verifier(synthese.lire_reponse(brut), passages)
            except ValueError as e:
                publiable, erreurs = None, [f"Réponse illisible : {e}"]
            if publiable:
                syn.update(publiable)
                syn.update({"statut": "publiee", "genere_le": maintenant(), "modele": modele, "erreurs": []})
                rapport.publiees.append(s)
                break
        syn["derniere_tentative"] = maintenant()
        if panne and not publiable:
            syn["erreurs"] = [f"IA indisponible : {panne}"]
            if age > config.CR_DELAI_MAX_JOURS:
                syn["statut"] = "abandonnee"
                rapport.abandonnees.append(s)
            else:
                rapport.ia_indisponible.append(s)
        elif not publiable:
            syn["statut"] = "refusee"
            syn["erreurs"] = erreurs
            rapport.refusees.append((s, erreurs))
        sauver_synthese(syn)


def retirer(num, raison, syntheses, rapport):
    uid = f"VTANR5L{config.LEGISLATURE}V{num}"
    config.RETRAITS.parent.mkdir(parents=True, exist_ok=True)
    with open(config.RETRAITS, "a", encoding="utf-8") as f:
        f.write(f"{uid}\t{date.today().isoformat()}\t{(raison or '').replace(chr(9), ' ')}\n")
    if uid in syntheses:
        syntheses[uid]["statut"] = "retiree"
        sauver_synthese(syntheses[uid])
    rapport.infos.append(f"Synthèse du scrutin {num} retirée. Motif : {raison or 'non précisé'}")


# ------------------------------------------------------------------ notification

def maj(t):
    return (t or "")[:1].upper() + (t or "")[1:]


def lien(s):
    return f"{SITE_URL}/#s{s['num']}"


def notifier(rapport, scrutins, mode):
    E = telegram.esc
    lignes = []
    if rapport.nouveaux:
        majeurs = [s for s in rapport.nouveaux if s["categorie"]["niveau"] == 1]  # ensemble, motions…
        lignes.append(f"🗳 <b>{len(rapport.nouveaux)} nouveaux scrutins</b> dont {len(majeurs)} vote(s) majeur(s)")
        for s in majeurs[:8]:
            res = "✅ adopté" if s["sort"] == "adopté" else "❌ rejeté"
            lignes.append(f"• <a href=\"{lien(s)}\">n° {s['num']}</a> {E(maj(s['titre'])[:110])} — {res} "
                          f"({s['pour']} pour, {s['contre']} contre, {s['abst']} abst.)")
    if rapport.publiees:
        lignes.append(f"\n📝 <b>{len(rapport.publiees)} synthèse(s) publiée(s)</b>")
        lignes += [f"• <a href=\"{lien(s)}\">n° {s['num']}</a>" for s in rapport.publiees]
    if rapport.en_attente:
        lignes.append(f"\n⏳ {len(rapport.en_attente)} synthèse(s) en attente du compte rendu")
    if rapport.ia_indisponible:
        lignes.append(f"\n🔁 IA momentanément indisponible pour {len(rapport.ia_indisponible)} synthèse(s) : "
                      "nouvel essai automatique au prochain passage")
    if rapport.refusees:
        lignes.append(f"\n⚠️ <b>{len(rapport.refusees)} synthèse(s) bloquée(s) par la vérification</b> (non publiées)")
        for s, err in rapport.refusees:
            lignes.append(f"• n° {s['num']} : {E('; '.join(err[:2]))[:300]}")
    if rapport.abandonnees:
        lignes.append(f"\n🚫 {len(rapport.abandonnees)} synthèse(s) abandonnée(s) : "
                      + ", ".join(str(s["num"]) for s in rapport.abandonnees))
    for i in rapport.infos:
        lignes.append(f"ℹ️ {E(i)}")
    for e in rapport.erreurs:
        lignes.append(f"🔥 <b>Erreur</b> : {E(e)[:500]}")
    if not lignes:
        return
    entete_ = f"<b>Qui vote quoi ?</b> · {date.today().strftime('%d/%m/%Y')}"
    if mode == "syntheses":
        entete_ += " (passage de l'après-midi)"

    # Image : vote majeur le plus récent du jour, à défaut le dernier scrutin nouveau.
    vedette = next((s for s in reversed(rapport.nouveaux) if s["categorie"]["niveau"] == 1), None) \
        or (rapport.publiees[-1] if rapport.publiees else None) \
        or (rapport.nouveaux[-1] if rapport.nouveaux else None)
    if vedette:
        try:
            chemin = image.dessiner(vedette, config.CACHE / "hemicycle.png")
            res = "adopté" if vedette["sort"] == "adopté" else "rejeté"
            telegram.photo(chemin, f"<b>{E(maj(vedette['titre'])[:300])}</b>\nScrutin n° {vedette['num']} — {res}\n"
                                   f"{lien(vedette)}")
        except Exception as e:
            lignes.append(f"🔥 Image non générée : {E(e)}")
    telegram.message(entete_ + "\n\n" + "\n".join(lignes))


# ------------------------------------------------------------------ main

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="quotidien", choices=["quotidien", "syntheses", "publier"])
    p.add_argument("--retrait", type=int)
    p.add_argument("--raison", default="")
    p.add_argument("--fixtures")
    p.add_argument("--sans-ia", action="store_true")
    p.add_argument("--rattrapage", type=int, default=0, help="programme les synthèses des N derniers jours")
    p.add_argument("--secours", action="store_true",
                   help="passage de secours : ne fait rien si la mise à jour quotidienne a déjà réussi aujourd'hui")
    args = p.parse_args(argv)

    etat = charger_json(config.ETAT, {})
    if args.secours and str(etat.get("dernier_quotidien", ""))[:10] == maintenant()[:10]:
        print("Mise à jour quotidienne déjà faite aujourd'hui : passage de secours inutile.")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("deployer=false\n")
        return 0
    syntheses = charger_syntheses()
    rapport = Rapport()
    deployer = False
    try:
        if args.mode == "syntheses" and not args.retrait and not args.rattrapage and \
                not any(s["statut"] == "en_attente" for s in syntheses.values()) and not etat.get("resumes_restants"):
            print("Aucune synthèse ni aucun résumé en attente.")
        else:
            chemins, dates = charger_sources(args, etat)
            scrutins = donnees.lire_scrutins(chemins["scrutins"])
            deputes, groupes = donnees.lire_acteurs(chemins["acteurs"])
            commissions, titres, textes = donnees.lire_dossiers(chemins["dossiers"])
            stats = donnees.attribuer_themes(scrutins, commissions, titres, donnees.lire_organes(chemins["acteurs"]))
            print(f"Thèmes : {stats}")
            if args.retrait:
                retirer(args.retrait, args.raison, syntheses, rapport)
            if args.mode == "quotidien" and not args.retrait:
                detecter_nouveaux(scrutins, etat, syntheses, rapport)
            if args.rattrapage:
                rattrapage(scrutins, syntheses, args.rattrapage, rapport)
            if args.mode != "publier":  # « publier » : simple republication après un retrait, sans IA
                traiter_syntheses(scrutins, syntheses, etat, args, rapport)
                etat["resumes_restants"] = resume.traiter(scrutins, textes, deputes, rapport, args,
                                                             budget_s=(45 if args.mode == "syntheses" else 20) * 60) or 0
            if args.mode == "quotidien" and not args.fixtures:
                communes.assurer()
                circos.assurer()
            if not args.fixtures:
                logos.assurer()
            avec_photo = photos.preparer(deputes, telecharger=args.mode == "quotidien" and not args.fixtures)
            export.exporter(scrutins, deputes, groupes, syntheses, charger_retraits(), dates, avec_photo)
            photos.ecrire(avec_photo)
            deployer = True
            if args.mode == "quotidien" and not args.retrait:
                etat["dernier_quotidien"] = maintenant()
    except Exception:
        rapport.erreurs.append(traceback.format_exc(limit=3))
        print(traceback.format_exc(), file=sys.stderr)

    etat["derniere_execution"] = maintenant()
    ecrire_json(config.ETAT, etat)
    try:
        notifier(rapport, None, args.mode)
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
    try:
        canal.publier(rapport, locals().get("groupes") or {}, etat)
        ecrire_json(config.ETAT, etat)
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"deployer={'true' if deployer else 'false'}\n")
    return 1 if rapport.erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
