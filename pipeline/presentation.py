"""« En bref » : phrase de présentation de chaque scrutin, écrite par script (aucune IA).

Elle explique en langage courant ce que signifie le vote, à partir de son intitulé officiel :
type de vote, étape de la procédure et conséquence prévue par le règlement. Elle ne dit jamais
ce que contient le texte : pour cela, le site renvoie au dossier officiel et, pour les votes sur
l'ensemble, à la synthèse du débat."""
import re

ETAPES = [
    (r"\(lecture définitive\)", "en lecture définitive : après désaccord persistant avec le Sénat, "
                                "l'Assemblée nationale a le dernier mot"),
    (r"commission mixte paritaire", "sur la version de compromis élaborée par sept députés et sept sénateurs "
                                    "(commission mixte paritaire)"),
    (r"\(nouvelle lecture\)", "en nouvelle lecture, après l'échec d'un compromis avec le Sénat"),
    (r"\(deuxième lecture\)", "en deuxième lecture"),
    (r"\(troisième lecture\)", "en troisième lecture"),
    (r"\(première lecture\)", "en première lecture"),
]


def _etape(t):
    for motif, texte in ETAPES:
        if re.search(motif, t):
            return texte
    return ""


def _texte(t):
    if "proposition de résolution" in t:
        return "la proposition de résolution"
    if "proposition de loi organique" in t or "projet de loi organique" in t:
        return "le texte (loi organique)"
    if "projet de loi constitutionnelle" in t or "proposition de loi constitutionnelle" in t:
        return "la révision de la Constitution"
    if "proposition de loi" in t:
        return "la proposition de loi (texte déposé par des parlementaires)"
    if "projet de loi" in t:
        return "le projet de loi (texte déposé par le Gouvernement)"
    return "le texte"


def en_bref(s):
    t = (s.get("titre") or "").lower().replace("’", "'")
    cle = s["categorie"]["cle"]
    etape = _etape(t)
    sol = " C'est un scrutin solennel, annoncé à l'avance pour permettre à tous les députés d'y participer." \
        if s.get("type") == "SPS" else ""

    if cle == "censure":
        return ("Les députés signataires demandent le renversement du Gouvernement. Seuls les votes pour sont comptés : "
                "si la motion réunit la majorité absolue des députés (289 voix quand l'Assemblée est au complet), "
                "le Gouvernement doit démissionner.")
    if cle == "declaration":
        return "Vote des députés sur une déclaration présentée par le Gouvernement." + sol
    if cle == "motion":
        if "rejet préalable" in t:
            return ("Motion de rejet préalable : si elle est adoptée, le texte est rejeté avant même l'examen de ses "
                    "articles. Voter pour la motion, c'est donc s'opposer au texte.")
        if "renvoi en commission" in t:
            return ("Motion de renvoi en commission : si elle est adoptée, la discussion s'arrête et le texte retourne "
                    "en commission pour y être réexaminé.")
        if "référendaire" in t:
            return ("Motion référendaire : elle propose de soumettre le texte au référendum. Elle doit aussi être "
                    "adoptée par le Sénat.")
        return "Motion de procédure : vote sur la suite donnée à l'examen du texte."
    if cle == "ensemble":
        if "partie du projet de loi de finances" in t:
            return ("Vote sur la partie « recettes » du budget de l'État" + (f", {etape}" if etape else "") +
                    ". Si elle est rejetée, c'est tout le projet de budget qui est rejeté par l'Assemblée, "
                    "et le texte est transmis au Sénat.")
        if "proposition de résolution" in t:
            return ("Vote sur une proposition de résolution : l'Assemblée exprime un avis ou une demande, "
                    "sans valeur de loi." + sol)
        return (f"Vote final de l'Assemblée sur l'ensemble de {_texte(t)}" + (f", {etape}" if etape else "") +
                ", après l'examen de tous ses articles." + sol)
    if cle == "article":
        return ("Vote sur un article du texte, pas sur le texte entier. S'il est rejeté, l'article est supprimé "
                "du texte en discussion.")
    if cle == "amendement":
        return ("Vote sur un amendement, c'est-à-dire une modification proposée au texte. S'il est adopté, "
                "la modification est intégrée au texte en discussion.")
    if cle == "procedure":
        return "Vote sur l'organisation des débats (déroulement de la séance), pas sur le fond d'un texte."
    return "Scrutin public de l'Assemblée nationale." + sol
