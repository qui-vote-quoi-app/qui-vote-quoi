"""Notifications Telegram (récapitulatif quotidien, image, alertes)."""
import html
import json
import os

import requests


def actif():
    return bool(os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def _url(methode):
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/{methode}"


def canal():
    """Canal public (ex. @quivotequoi) : le bot y publie, Telegram gère seul les abonnés."""
    return os.environ.get("TELEGRAM_CANAL", "").strip()


def _envoyer(methode, data, files=None):
    r = requests.post(_url(methode), timeout=120, data=data, files=files)
    r.raise_for_status()
    return r.json().get("result")


def _clavier(boutons):
    """boutons : [[(libellé, url), …], …] -> clavier de boutons-liens sous le message."""
    return json.dumps({"inline_keyboard": [[{"text": l, "url": u} for l, u in ligne] for ligne in boutons]})


def message(texte_html, chat=None, silencieux=False, boutons=None):
    """Envoie un message (découpé si besoin). Renvoie l'identifiant du dernier message envoyé."""
    if not actif():
        print("[telegram désactivé]\n" + texte_html)
        return None
    res = None
    for i in range(0, len(texte_html), 3900):
        res = _envoyer("sendMessage", {
            "chat_id": chat or os.environ["TELEGRAM_CHAT_ID"], "text": texte_html[i:i + 3900],
            "parse_mode": "HTML", "disable_web_page_preview": "true",
            "disable_notification": "true" if silencieux else "false",
            **({"reply_markup": _clavier(boutons)} if boutons and i + 3900 >= len(texte_html) else {})})
    return (res or {}).get("message_id")


def photo(chemin, legende_html, chat=None, silencieux=False, boutons=None):
    if not actif():
        print(f"[telegram désactivé] image {chemin}\n{legende_html}")
        return None
    with open(chemin, "rb") as f:
        res = _envoyer("sendPhoto", {"chat_id": chat or os.environ["TELEGRAM_CHAT_ID"], "caption": legende_html[:1024],
                                     "parse_mode": "HTML", "disable_notification": "true" if silencieux else "false",
                                     **({"reply_markup": _clavier(boutons)} if boutons else {})},
                       files={"photo": f})
    return (res or {}).get("message_id")


def modifier_legende(chat, message_id, legende_html, boutons=None):
    if actif():
        _envoyer("editMessageCaption", {"chat_id": chat, "message_id": message_id, "caption": legende_html[:1024],
                                        "parse_mode": "HTML", **({"reply_markup": _clavier(boutons)} if boutons else {})})


def epingler(chat, message_id):
    if actif():
        _envoyer("pinChatMessage", {"chat_id": chat, "message_id": message_id, "disable_notification": "true"})


def esc(t):
    return html.escape(str(t or ""), quote=False)
