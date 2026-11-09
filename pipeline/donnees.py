"""Lecture des dumps « Scrutins » et « Acteurs et organes » de l'Assemblée nationale."""
import json
import re
import zipfile

from . import config

POSITIONS = {"pours": "pour", "contres": "contre", "abstentions": "abst", "nonVotants": "nv",
             "nonVotantsVolontaires": "nv"}


def liste(x):
    """Les dumps JSON (convertis depuis XML) donnent tantôt un objet, tantôt une
    liste, tantôt null, parfois des listes contenant des null. On normalise."""
    if x is None:
        return []
    if isinstance(x, list):
        out = []
        for e in x:
            out.extend(liste(e))
        return out
    return [x]


def texte(x):
    if isinstance(x, dict):
        return x.get("#text")
    return x


def entier(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------- Catégories

REGLES = [
    (r"motion de censure", "censure", "Motion de censure", 1),
    (r"déclaration du gouvernement", "declaration", "Déclaration du Gouvernement", 1),
    (r"^la motion (de rejet|de renvoi|référendaire)|^la question préalable",
     "motion", "Motion de procédure", 1),
    (r"^l['’]ensemble|^la (première|seconde) partie du projet de loi de finances"
     r"|^la proposition de résolution|^le projet de loi|^la proposition de loi",
     "ensemble", "Vote sur l'ensemble", 1),
    (r"prolonger la séance|suspension|^la demande", "procedure", "Procédure", 3),
    (r"^l['’]article|^les articles|^l['’]annexe", "article", "Article", 2),
    (r"amendement", "amendement", "Amendement", 3),
]


def categorie(titre, code_type):
    t = (titre or "").strip().lower()
    cat = ("autre", "Autre", 3)
    for motif, cle, libelle, niveau in REGLES:
        if re.search(motif, t):
            cat = (cle, libelle, niveau)
            break
    cle, libelle, niveau = cat
    if code_type == "SPS":  # scrutin solennel : toujours majeur
        niveau = 1
    return {"cle": cle, "libelle": libelle, "niveau": niveau}


# ---------------------------------------------------------------- Scrutins

def lire_scrutin(brut: dict) -> dict:
    s = brut["scrutin"]
    sv = s.get("syntheseVote") or {}
    dec = sv.get("decompte") or {}
    groupes = []
    organe = (s.get("ventilationVotes") or {}).get("organe") or {}
    for g in liste((organe.get("groupes") or {}).get("groupe")):
        vote = g.get("vote") or {}
        dv = vote.get("decompteVoix") or {}
        dn = vote.get("decompteNominatif") or {}
        votes = {"pour": [], "contre": [], "abst": [], "nv": []}
        for cle, pos in POSITIONS.items():
            for bloc in liste(dn.get(cle)):
                if not isinstance(bloc, dict):
                    continue
                for v in liste(bloc.get("votant")):
                    if isinstance(v, dict) and v.get("acteurRef"):
                        votes[pos].append([v["acteurRef"], entier(v.get("numPlace"))])
        groupes.append({
            "po": g.get("organeRef"),
            "membres": entier(g.get("nombreMembresGroupe")),
            "position": vote.get("positionMajoritaire"),
            "decompte": {"pour": entier(dv.get("pour")), "contre": entier(dv.get("contre")),
                         "abst": entier(dv.get("abstentions")),
                         "nv": entier(dv.get("nonVotants")) + entier(dv.get("nonVotantsVolontaires"))},
            "votes": votes,
        })
    mises_au_point = []
    for cle, pos in [("pours", "pour"), ("contres", "contre"), ("abstentions", "abst"),
                     ("nonVotants", "nv"), ("nonVotantsVolontaires", "nv")]:
        for bloc in liste((s.get("miseAuPoint") or {}).get(cle)):
            for v in liste(bloc.get("votant") if isinstance(bloc, dict) else None):
                if isinstance(v, dict) and v.get("acteurRef"):
                    mises_au_point.append([v["acteurRef"], pos])
    objet = s.get("objet") or {}
    dossier = objet.get("dossierLegislatif") or {}
    titre = (s.get("titre") or "").strip()
    tv = s.get("typeVote") or {}
    return {
        "uid": s["uid"],
        "num": entier(s.get("numero")),
        "date": s.get("dateScrutin"),
        "seance": s.get("seanceRef"),
        "type": tv.get("codeTypeVote"),
        "type_libelle": tv.get("libelleTypeVote"),
        "majorite": tv.get("typeMajorite"),
        "sort": (s.get("sort") or {}).get("code"),
        "sort_libelle": (s.get("sort") or {}).get("libelle"),
        "titre": titre,
        "dossier": dossier.get("dossierRef"),
        "dossier_libelle": dossier.get("libelle"),
        "demandeur": (s.get("demandeur") or {}).get("texte"),
        "votants": entier(sv.get("nombreVotants")),
        "exprimes": entier(sv.get("suffragesExprimes")),
        "requis": entier(sv.get("nbrSuffragesRequis")),
        "pour": entier(dec.get("pour")),
        "contre": entier(dec.get("contre")),
        "abst": entier(dec.get("abstentions")),
        "nv": entier(dec.get("nonVotants")) + entier(dec.get("nonVotantsVolontaires")),
        "categorie": categorie(titre, tv.get("codeTypeVote")),
        "groupes": groupes,
        "mises_au_point": mises_au_point,
    }


def lire_scrutins(chemin_zip):
    out = {}
    with zipfile.ZipFile(chemin_zip) as z:
        for nom in z.namelist():
            if nom.endswith(".json"):
                s = lire_scrutin(json.loads(z.read(nom)))
                out[s["uid"]] = s
    return out


# ---------------------------------------------------------------- Acteurs et organes

def lire_acteurs(chemin_zip):
    """Retourne (deputes, groupes) pour la législature courante.
    Seules les informations liées au mandat sont conservées (minimisation RGPD)."""
    deputes, groupes = {}, {}
    with zipfile.ZipFile(chemin_zip) as z:
        for nom in z.namelist():
            if "/organe/" in nom:
                o = json.loads(z.read(nom))["organe"]
                if o.get("codeType") == "GP" and o.get("legislature") == config.LEGISLATURE:
                    vm = o.get("viMoDe") or {}
                    groupes[o["uid"]] = {
                        "sigle": o.get("libelleAbrev") or o.get("libelleAbrege"),
                        "libelle": o.get("libelle"),
                        "couleur": o.get("couleurAssociee") or "#8b8f99",
                        "debut": vm.get("dateDebut"), "fin": vm.get("dateFin"),
                        "ordre": entier(o.get("preseance")),
                    }
        for nom in z.namelist():
            if "/acteur/" not in nom:
                continue
            a = json.loads(z.read(nom))["acteur"]
            mandats = liste((a.get("mandats") or {}).get("mandat"))
            an = [m for m in mandats if m.get("typeOrgane") == "ASSEMBLEE"
                  and m.get("legislature") == config.LEGISLATURE]
            if not an:
                continue
            an.sort(key=lambda m: m.get("dateDebut") or "")
            dernier = an[-1]
            lieu = ((dernier.get("election") or {}).get("lieu")) or {}
            gps = [m for m in mandats if m.get("typeOrgane") == "GP"
                   and m.get("legislature") == config.LEGISLATURE]
            gps.sort(key=lambda m: m.get("dateDebut") or "")
            gp_actuel = next((m for m in reversed(gps) if not m.get("dateFin")), gps[-1] if gps else None)
            ident = (a.get("etatCivil") or {}).get("ident") or {}
            uid = texte(a.get("uid"))
            deputes[uid] = {
                "civ": ident.get("civ"),
                "prenom": ident.get("prenom"),
                "nom": ident.get("nom"),
                "dept": lieu.get("departement"),
                "num_dept": lieu.get("numDepartement"),
                "circo": entier(lieu.get("numCirco")),
                "place": entier(((dernier.get("mandature") or {}).get("placeHemicycle"))),
                "actif": not dernier.get("dateFin"),
                "debut": dernier.get("dateDebut"),
                "fin": dernier.get("dateFin"),
                "groupe": ((gp_actuel or {}).get("organes") or {}).get("organeRef"),
            }
    return deputes, groupes
