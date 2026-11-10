"""Lecture des dumps « Scrutins » et « Acteurs et organes » de l'Assemblée nationale."""
import json
import re
import unicodedata
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


# ---------------------------------------------------------------- Thèmes (commission saisie au fond)

def lire_organes(chemin_zip):
    """Libellé court des commissions, pour servir de « thème » aux votes."""
    out = {}
    with zipfile.ZipFile(chemin_zip) as z:
        for nom in z.namelist():
            if "/organe/" not in nom:
                continue
            o = json.loads(z.read(nom))["organe"]
            libelle = o.get("libelle") or ""
            if o.get("codeType") == "COMPER":
                court = o.get("libelleAbrege") or libelle
            elif "commission spéciale" in libelle.lower():
                court = "Commission spéciale"
            else:
                continue
            out[o["uid"]] = court
    return out


def normaliser_titre(t):
    t = unicodedata.normalize("NFKC", t or "").lower().replace("’", "'").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", t).strip().rstrip(".")


def _commission_fond(actes):
    """Première commission saisie au fond à l'Assemblée, en parcourant les actes dans l'ordre."""
    trouves = []

    def parcourir(a):
        for x in liste(a):
            if not isinstance(x, dict):
                continue
            code = x.get("codeActe") or ""
            if code.endswith("-COM-FOND") and x.get("organeRef"):
                trouves.append((code, x["organeRef"]))
            parcourir((x.get("actesLegislatifs") or {}).get("acteLegislatif"))

    parcourir((actes or {}).get("acteLegislatif"))
    an = [o for c, o in trouves if c.startswith("AN")]
    return (an or [o for _c, o in trouves] or [None])[0]


TYPES_TEXTES = ("Projet de loi", "Proposition de loi", "Proposition de résolution")


def lire_dossiers(chemin_zip):
    """Retourne (commission au fond par dossier, titres connus pour retrouver un dossier par intitulé,
    texte déposé à l'Assemblée par dossier — le premier, pour le résumé « Ce que prévoit le texte »)."""
    commissions, titres, deposes = {}, {}, {}
    with zipfile.ZipFile(chemin_zip) as z:
        for nom in z.namelist():
            if "/dossierParlementaire/" in nom:
                d = json.loads(z.read(nom))["dossierParlementaire"]
                c = _commission_fond(d.get("actesLegislatifs"))
                if c:
                    commissions[d["uid"]] = c
                t = normaliser_titre((d.get("titreDossier") or {}).get("titre"))
                if len(t) >= 25:
                    titres.setdefault(t, d["uid"])
            elif "/document/" in nom:
                doc = json.loads(z.read(nom))["document"]
                if not str(doc.get("denominationStructurelle") or "").startswith(TYPES_TEXTES):
                    continue
                m = re.fullmatch(r"(?:PION|PRJL)ANR5L\d+B(\d+)", str(doc.get("uid") or ""))
                if m and doc.get("dossierRef"):
                    prec = deposes.get(doc["dossierRef"])
                    if prec is None or int(m.group(1)) < prec[0]:
                        deposes[doc["dossierRef"]] = (int(m.group(1)), doc["uid"])
                t = normaliser_titre((doc.get("titres") or {}).get("titrePrincipal"))
                if doc.get("dossierRef") and len(t) >= 25:
                    titres.setdefault(t, doc["dossierRef"])
    # Seuls les titres de dossiers dont on connaît la commission servent à quelque chose.
    utiles = sorted(((t, ref) for t, ref in titres.items() if ref in commissions), key=lambda x: -len(x[0]))
    return commissions, utiles, {ref: uid for ref, (_n, uid) in deposes.items()}


def attribuer_themes(scrutins, commissions, titres, organes):
    """Ajoute s["theme"] (libellé court de la commission au fond) à chaque scrutin quand c'est possible.
    1) via le dossier indiqué dans le scrutin ; 2) sinon en retrouvant le titre du texte dans l'intitulé."""
    stats = {"direct": 0, "titre": 0, "aucun": 0}
    for s in scrutins.values():
        ref = s.get("dossier")
        if ref in commissions:
            stats["direct"] += 1
        else:
            ref = None
            intitule = normaliser_titre(s["titre"])
            for t, r in titres:
                if t in intitule:
                    ref = r
                    break
            stats["titre" if ref else "aucun"] += 1
            if ref and not s.get("dossier"):
                s["dossier"] = ref
        s["theme"] = organes.get(commissions.get(ref)) if ref else None
    return stats
