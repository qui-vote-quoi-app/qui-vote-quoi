"""Export des fichiers JSON statiques lus par le site."""
import copy
import shutil
from collections import defaultdict
from datetime import datetime, timezone

from . import config
from .sources import charger_json, ecrire_json


def exporter(scrutins, deputes, groupes, syntheses, retraits, sources_dates):
    out = config.SITE_DATA
    if out.exists():
        shutil.rmtree(out)
    (out / "mois").mkdir(parents=True)
    (out / "scrutins").mkdir(parents=True)

    # Députés : index stable (ordre des identifiants) pour compacter les votes.
    uids = sorted(deputes)
    index = {uid: i for i, uid in enumerate(uids)}
    ecrire_json(out / "deputes.json", [
        {"id": uid, **{k: deputes[uid][k] for k in
                       ("civ", "prenom", "nom", "dept", "num_dept", "circo", "place", "actif", "groupe")}}
        for uid in uids], compact=True)
    ecrire_json(out / "groupes.json", groupes, compact=True)
    shutil.copy(config.PLACES, out / "places.json")

    par_mois = defaultdict(list)
    for s in scrutins.values():
        syn = syntheses.get(s["uid"]) or {}
        statut = syn.get("statut")
        if s["uid"] in retraits:
            statut = "retiree"
        resume = {k: s[k] for k in ("num", "date", "titre", "sort", "pour", "contre", "abst", "votants")}
        resume["cat"] = s["categorie"]["cle"]
        resume["niv"] = s["categorie"]["niveau"]
        resume["syn"] = statut if s["categorie"]["cle"] in config.CATEGORIES_AVEC_SYNTHESE else None
        par_mois[s["date"][:7]].append(resume)

        detail = {k: s[k] for k in ("uid", "num", "date", "type", "type_libelle", "majorite", "sort",
                                    "sort_libelle", "titre", "dossier", "dossier_libelle", "demandeur",
                                    "votants", "exprimes", "requis", "pour", "contre", "abst", "nv")}
        detail["categorie"] = s["categorie"]
        detail["groupes"] = []
        inconnus = set()
        for g in s["groupes"]:
            votes = {}
            for pos, lst in g["votes"].items():
                plat = []
                for pa, place in lst:
                    if pa not in index:
                        inconnus.add(pa)
                        continue
                    plat.extend([index[pa], place])
                votes[pos] = plat
            detail["groupes"].append({"po": g["po"], "membres": g["membres"], "position": g["position"],
                                      "decompte": g["decompte"], "votes": votes})
        detail["mises_au_point"] = [[index[pa], pos] for pa, pos in s["mises_au_point"] if pa in index]
        detail["synthese"] = None
        detail["synthese_statut"] = resume["syn"]
        if statut == "publiee":
            detail["synthese"] = copy.deepcopy({k: syn.get(k) for k in (
                "contexte", "pour", "contre", "genere_le", "modele", "seance_jour")})
            for camp in ("pour", "contre"):
                for a in detail["synthese"][camp]:
                    a["dep"] = index.get(a["acteur"])
        ecrire_json(out / "scrutins" / f"{s['num']}.json", detail, compact=True)

    mois = sorted(par_mois, reverse=True)
    for m in mois:
        par_mois[m].sort(key=lambda r: -r["num"])
        ecrire_json(out / "mois" / f"{m}.json", par_mois[m], compact=True)

    ecrire_json(out / "meta.json", {
        "mois": mois,
        "nb_scrutins": len(scrutins),
        "dernier": max((s["num"] for s in scrutins.values()), default=0),
        "maj_site": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "sources": sources_dates,
    })
