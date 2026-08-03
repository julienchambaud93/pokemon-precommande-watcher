# -*- coding: utf-8 -*-
"""
Envoi des alertes : Telegram (actif) + Email (optionnel, phase 2).

Les identifiants ne sont JAMAIS écrits dans le code : ils viennent des "secrets"
GitHub (variables d'environnement). Si un secret manque, le canal est simplement ignoré.

Secrets utilisés :
  TELEGRAM_TOKEN     (obligatoire pour Telegram)
  TELEGRAM_CHAT_ID   (obligatoire pour Telegram)
  EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS, EMAIL_TO   (optionnels, pour l'email)
"""
import os
import smtplib
from email.mime.text import MIMEText

import requests


def _chunks(text, size=3900):
    for i in range(0, len(text), size):
        yield text[i:i + size]


def send_telegram(text):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[telegram] secrets manquants -> envoi ignoré")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for chunk in _chunks(text):
        try:
            r = requests.post(
                url,
                data={"chat_id": chat, "text": chunk, "disable_web_page_preview": "true"},
                timeout=20,
            )
            if not r.ok:
                ok = False
                print(f"[telegram] erreur {r.status_code} : {r.text[:300]}")
        except Exception as e:
            ok = False
            print(f"[telegram] exception : {e}")
    return ok


def send_email(subject, text):
    host = os.environ.get("EMAIL_HOST")
    port = os.environ.get("EMAIL_PORT")
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    to = os.environ.get("EMAIL_TO") or user
    if not (host and port and user and password):
        # Email non configuré (phase 2) -> on ignore silencieusement.
        return False
    try:
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to
        with smtplib.SMTP(host, int(port), timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to], msg.as_string())
        print("[email] envoyé")
        return True
    except Exception as e:
        print(f"[email] erreur : {e}")
        return False


def notify(subject, text):
    """Envoie sur tous les canaux configurés."""
    send_telegram(text)
    send_email(subject, text)
