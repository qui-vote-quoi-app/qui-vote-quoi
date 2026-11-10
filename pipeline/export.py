"""Export des fichiers JSON statiques lus par le site.

Fichiers produits (dans site/data/) :
- meta.json              date de mise à jour, sources
- index.json             liste compacte de tous les scrutins (barre latérale, historiques, filtres)
- scrutins/<n>.json      détail des scrutins par paquets de 100 (97.json = n° 9700 à 9799)
- deputes.json           députés (index stable)
- votes_deputes/<n>.json historique de vote des députés, par paquets de 50 députés
- groupes.json           groupes politiques
- votes_groupes/<PO>.json historique de vote d'un groupe
- places.json            carte de l'hémicycle
- communes.json          commune -> circonscriptions (recherche « Trouver mon député »)
- photos/<PA>.webp       vignettes des photos officielles (voir photos.py)
Moins de fichiers = publication GitHub Pages plus rapide."""
import copy
import shutil
from collections import defaultdict
from datetime import datetime, timezone

import os

from . import config, image, presentation
from .sources import ecrire_json

CATS = ["ensemble", "motion", "censure", "declaration", "article", "amendement", "procedure", "autre"]
POS = {"pour": 0, "contre": 1, "abst": 2, "nv": 3}
POS_MAJ = {"pour": 0, "contre": 1, "abstention": 2}
DEPUTES_PAR_PAQUET = 50


def _delta(paires):
    """[(num, a, b…), …] triés par num -> liste plate où num est codé en écart au précédent."""
    plat, prec = [], 0
    for p in sorted(paires):
        plat.append(p[0] - prec)
        plat.extend(p[1:])
        prec = p[0]
    return plat


def exporter(scrutins, deputes, groupes, syntheses, retraits, sources_dates, avec_photo=()):
    out = config.SITE_DATA
    if out.exists():
        shutil.rmtree(out)
    for d in ("scrutins", "votes_deputes", "votes_groupes"):
        (out / d).mkdir(parents=True)

    # Députés : index stable (ordre des identifiants) pour compacter les votes.
    uids = sorted(deputes)
    index = {uid: i for i, uid in enumerate(uids)}
    ecrire_json(out / "deputes.json", [
        {"id": uid, **{k: deputes[uid].get(k) for k in
                       ("civ", "prenom", "nom", "dept", "num_dept", "circo", "place", "actif", "groupe", "debut", "fin")},
         **({"photo": 1} if uid in avec_photo else {})}
        for uid in uids], compact=True)
    ecrire_json(out / "groupes.json", groupes, compact=True)
    shutil.copy(config.PLACES, out / "places.json")
    communes = config.DATA / "communes.json"
    if communes.exists():
        shutil.copy(communes, out / "communes.json")

    themes = sorted({s["theme"] for s in scrutins.values() if s.get("theme")})
    i_theme = {t: i for i, t in enumerate(themes)}
    liste_index = []
    paquets = defaultdict(dict)
    hist_dep = defaultdict(list)    # index député -> [(num, pos)]
    hist_grp = defaultdict(list)    # PO -> [(num, pos_maj, pour, contre, abst, nv, membres)]

    for s in scrutins.values():
        syn = syntheses.get(s["uid"]) or {}
        statut = syn.get("statut")
        if s["uid"] in retraits:
            statut = "retiree"
        avec_syn = s["categorie"]["cle"] in config.CATEGORIES_AVEC_SYNTHESE
        liste_index.append([
            s["num"], s["date"], CATS.index(s["categorie"]["cle"]) if s["categorie"]["cle"] in CATS else 7,
            s["categorie"]["niveau"], 1 if s["sort"] == "adopté" else 0,
            i_theme.get(s.get("theme"), -1), (statut or "") if avec_syn else "", s["titre"],
        ])

        detail = {k: s.get(k) for k in ("uid", "num", "date", "type", "type_libelle", "majorite", "sort",
                                        "sort_libelle", "titre", "dossier", "dossier_libelle", "demandeur",
                                        "votants", "exprimes", "requis", "pour", "contre", "abst", "nv", "theme")}
        detail["categorie"] = s["categorie"]
        detail["bref"] = presentation.en_bref(s)
        detail["groupes"] = []
        for g in s["groupes"]:
            votes = {}
            for pos, lst in g["votes"].items():
                plat = []
                for pa, place in lst:
                    if pa not in index:
                        continue
                    plat.extend([index[pa], place])
                    hist_dep[index[pa]].append((s["num"], POS[pos]))
                votes[pos] = plat
            d = g["decompte"]
            if g["po"]:
                hist_grp[g["po"]].append((s["num"], POS_MAJ.get(g["position"], 3), d["pour"], d["contre"],
                                          d["abst"], d["nv"], g["membres"]))
            detail["groupes"].append({"po": g["po"], "membres": g["membres"], "position": g["position"],
                                      "decompte": d, "votes": votes})
        detail["mises_au_point"] = [[index[pa], pos] for pa, pos in s["mises_au_point"] if pa in index]
        detail["synthese"] = None
        detail["synthese_statut"] = (statut or None) if avec_syn else None
        if statut == "publiee":
            detail["synthese"] = copy.deepcopy({k: syn.get(k) for k in (
                "contexte", "pour", "contre", "genere_le", "modele", "seance_jour")})
            for camp in ("pour", "contre"):
                for a in detail["synthese"][camp]:
                    a["dep"] = index.get(a["acteur"])
        paquets[s["num"] // 100][str(s["num"])] = detail

    for p, contenu in paquets.items():
        ecrire_json(out / "scrutins" / f"{p}.json", contenu, compact=True)

    liste_index.sort(key=lambda r: -r[0])
    ecrire_json(out / "index.json", {"cats": CATS, "themes": themes, "s": liste_index}, compact=True)

    paquets_dep = defaultdict(dict)
    for i, votes in hist_dep.items():
        paquets_dep[i // DEPUTES_PAR_PAQUET][str(i)] = _delta(votes)
    for p, contenu in paquets_dep.items():
        ecrire_json(out / "votes_deputes" / f"{p}.json", contenu, compact=True)
    for po, lignes in hist_grp.items():
        ecrire_json(out / "votes_groupes" / f"{po}.json", _delta(lignes), compact=True)

    # Aperçu pour la page « Recevoir les alertes » : le dernier vote important, tel qu'il part sur Telegram.
    apercu = None
    majeurs = [s for s in scrutins.values() if s["categorie"]["niveau"] == 1]
    if majeurs:
        v = max(majeurs, key=lambda s: s["num"])
        try:
            image.dessiner(v, out / "apercu.png")
            apercu = {"num": v["num"], "titre": v["titre"], "adopte": v["sort"] == "adopté", "pour": v["pour"],
                      "contre": v["contre"], "abst": v["abst"], "bref": presentation.en_bref(v)}
        except Exception as e:  # noqa: BLE001 — l'aperçu est accessoire
            print(f"Aperçu non généré : {e}")
    ecrire_json(out / "meta.json", {
        "nb_scrutins": len(scrutins),
        "dernier": max((s["num"] for s in scrutins.values()), default=0),
        "deputes_par_paquet": DEPUTES_PAR_PAQUET,
        "maj_site": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "sources": sources_dates,
        "canal": os.environ.get("TELEGRAM_CANAL", "").strip(),
        "apercu": apercu,
    })
