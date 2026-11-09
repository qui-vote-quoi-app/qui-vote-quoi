"""Notifications Telegram (récapitulatif quotidien, image, alertes)."""
import html
import os

import requests


def actif():
    return bool(os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def _url(methode):
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/{methode}"


def message(texte_html):
    if not actif():
        print("[telegram désactivé]\n" + texte_html)
        return
    for i in range(0, len(texte_html), 3900):
        requests.post(_url("sendMessage"), timeout=60, data={
            "chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texte_html[i:i + 3900],
            "parse_mode": "HTML", "disable_web_page_preview": "true"}).raise_for_status()


def photo(chemin, legende_html):
    if not actif():
        print(f"[telegram désactivé] image {chemin}\n{legende_html}")
        return
    with open(chemin, "rb") as f:
        requests.post(_url("sendPhoto"), timeout=120,
                      data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": legende_html[:1000],
                            "parse_mode": "HTML"},
                      files={"photo": f}).raise_for_status()


def esc(t):
    return html.escape(str(t or ""), quote=False)
