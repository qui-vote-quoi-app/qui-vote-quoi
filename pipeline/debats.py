"""Extraction du passage de débat lié à un scrutin, dans le compte rendu officiel (XML syceron).

Tout ici est fait par script : localisation du vote, découpage, nettoyage.
L'IA ne reçoit qu'un texte réduit et ne voit jamais les noms des orateurs."""
import re
import xml.etree.ElementTree as ET

from . import config

NS = "{http://schemas.assemblee-nationale.fr/referentiel}"
PRESIDENCE = re.compile(r"^(M\. le président|Mme la présidente|M\. le président de séance)\b", re.I)


def _tag(el):
    return el.tag.replace(NS, "")


def _enfant(el, nom):
    return el.find(NS + nom)


def texte_propre(el_texte):
    """Texte d'un élément <texte> : les <br/> deviennent des retours à la ligne,
    les didascalies en italique (applaudissements, exclamations…) sont retirées."""
    if el_texte is None:
        return ""
    morceaux = []

    def parcourir(e):
        if e.text and _tag(e) != "italique":
            morceaux.append(e.text)
        for c in e:
            t = _tag(c)
            if t == "br":
                morceaux.append("\n")
            elif t != "italique":
                parcourir(c)
            if c.tail:
                morceaux.append(c.tail)

    parcourir(el_texte)
    t = "".join(morceaux).replace(" ", " ").replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return t.strip()


def metadonnees(racine):
    md = _enfant(racine, "metadonnees")
    get = (lambda n: (md.findtext(NS + n) or "").strip()) if md is not None else (lambda n: "")
    return {
        "uid": (racine.findtext(NS + "uid") or "").strip(),
        "seance": (racine.findtext(NS + "seanceRef") or "").strip(),
        "jour": get("dateSeanceJour"),
        "num_jour": get("numSeanceJour"),
        "etat": get("etat"),
        "session": get("session"),
    }


def aplatir(racine):
    """Liste des <point> et <paragraphe> dans l'ordre du document."""
    contenu = _enfant(racine, "contenu")
    out = []

    def parcourir(e):
        for c in e:
            t = _tag(c)
            if t in ("point", "paragraphe"):
                out.append(c)
            if t == "point":
                parcourir(c)

    if contenu is not None:
        parcourir(contenu)
    return out


def _titre_point(p):
    return texte_propre(_enfant(p, "texte")) if _tag(p) == "point" else ""


def trouver_resultat(noeuds, scrutin):
    """Repère l'annonce « Voici le résultat du scrutin » dont les chiffres
    correspondent exactement au scrutin officiel."""
    attendus = [scrutin["votants"], scrutin["exprimes"], scrutin["pour"], scrutin["contre"]]
    for i, n in enumerate(noeuds):
        if _tag(n) != "paragraphe":
            continue
        t = texte_propre(_enfant(n, "texte"))
        if "résultat du scrutin" not in t:
            continue
        nombres = [int(x) for x in re.findall(r"\d+", t)]
        if len(nombres) >= 5:
            votants, exprimes, _majorite, pour, contre = nombres[:5]
            if [votants, exprimes, pour, contre] == attendus:
                return i
    return None


def segment(noeuds, i_resultat):
    """Paragraphes de débat qui précèdent le vote :
    - si le vote est précédé d'un point « Explications de vote », on prend ce point ;
    - sinon, on remonte jusqu'au début du point qui contient le vote."""
    i_point = next((k for k in range(i_resultat, -1, -1) if _tag(noeuds[k]) == "point"), None)
    if i_point is None:
        return []
    debut, fin = i_point, i_resultat
    if re.match(r"^(Vote|Scrutin)", _titre_point(noeuds[i_point])):
        i_expl = next((k for k in range(i_point - 1, -1, -1)
                       if _tag(noeuds[k]) == "point" and "Explications de vote" in _titre_point(noeuds[k])),
                      None)
        if i_expl is not None:
            debut, fin = i_expl, i_point
    return [n for n in noeuds[debut + 1:fin] if _tag(n) == "paragraphe"]


def passages(paragraphes):
    """Interventions de fond, fusionnées par orateur consécutif.
    Exclut la présidence, les interruptions et les paragraphes sans orateur."""
    out = []
    for p in paragraphes:
        acteur = p.get("id_acteur")
        code = p.get("code_grammaire") or ""
        orateur = p.find(f"{NS}orateurs/{NS}orateur")
        nom = (orateur.findtext(NS + "nom") if orateur is not None else "") or ""
        qualite = (orateur.findtext(NS + "qualite") if orateur is not None else "") or ""
        if not acteur or code.startswith("INTERRUPTION") or p.get("roledebat") == "president" \
                or PRESIDENCE.match(nom.strip()):
            continue
        t = texte_propre(_enfant(p, "texte"))
        if not t:
            continue
        nom = re.sub(r"\s*\([^)]*\)\s*$", "", nom).strip()
        if out and out[-1]["acteur"] == acteur:
            out[-1]["texte"] += "\n" + t
            out[-1]["syceron"].append(p.get("id_syceron"))
        else:
            out.append({"acteur": acteur, "nom": nom, "qualite": qualite.strip(),
                        "syceron": [p.get("id_syceron")], "texte": t})
    # Limite de taille : on garde les interventions les plus proches du vote.
    total, garde = 0, []
    for p in reversed(out):
        total += len(p["texte"])
        if total > config.SEGMENT_MAX_CARACTERES:
            break
        garde.append(p)
    garde.reverse()
    for k, p in enumerate(garde, 1):
        p["id"] = f"P{k}"
    return garde


def extraire(xml_bytes, scrutin):
    racine = ET.fromstring(xml_bytes)
    noeuds = aplatir(racine)
    i = trouver_resultat(noeuds, scrutin)
    if i is None:
        return metadonnees(racine), None
    return metadonnees(racine), passages(segment(noeuds, i))


def seance_du_fichier(debut_xml: bytes):
    m = re.search(rb"<seanceRef>([^<]+)</seanceRef>", debut_xml)
    return m.group(1).decode() if m else None
