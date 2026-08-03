# -*- coding: utf-8 -*-
"""
Robot de surveillance des précommandes Pokémon « 30th Celebration » (ETB & UPC).

Fonctionnement (toutes les 5 min via GitHub Actions) :
  1. Interroge chaque boutique de sites.py
     - Shopify  -> lit /products.json (liste complète, même produits pas encore mis en avant)
     - Autres   -> lit les pages "search_urls" et cherche les mots-clés
  2. Détecte tout NOUVEAU produit cible, ou tout RETOUR EN STOCK d'un produit cible
  3. Envoie une alerte Telegram (+ email si configuré) avec nom, prix, langue probable et lien

La "mémoire" est dans state.json (produits déjà vus / déjà en stock), commité par l'Action.
Le tout premier lancement enregistre l'état actuel et envoie UN récap, sans spammer ensuite.

Test manuel : définir la variable TEST_ALERT=1 -> envoie un message de test puis s'arrête.
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from sites import SITES
from notify import send_telegram, notify

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8",
}
TIMEOUT = 25


# ─────────────────────────── Détection (LARGE, tolérante aux variantes d'écriture) ───────────────────────────

def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _prep(text):
    """minuscule + apostrophes normalisées + version sans accents."""
    t = (text or "").lower().replace("’", "'").replace("’", "'")
    return t, _strip_accents(t)


# Signale le SET 30 ANS quelle que soit la façon dont il est écrit
# (30th Celebration / 30th Anniversary / 30e-30ème anniversaire / trentième / 30 Jahre / Jubiläum ...)
def _is_anniversary(t, ta):
    # DOIT référencer le « 30 » -> l'ancien set 2021 « Celebrations » (sans 30) est EXCLU.
    if "30th" in ta or "trenti" in ta:                       # 30th / trentième
        return True
    if "30 ans" in ta or "30ans" in ta or "30 jahre" in ta or "30. geburtstag" in ta:
        return True
    if "30" in ta and ("annivers" in ta or "jubil" in ta):   # 30ᵉ / 30° Anniversaire, 30. Jubiläum...
        return True
    if "30" in ta and "celebrat" in ta:                      # « 30 ... Celebration »
        return True
    return False


def _is_japanese(ta):
    return ("japanese" in ta or "japon" in ta or "japan" in ta or "japanisch" in ta
            or re.search(r"\bjp\b", ta) is not None)


def classify(text):
    """
    Retourne :
      "target_etb" / "target_upc"  -> produit CIBLE (30 ans + ETB/UPC)       => alerte forte
      "set_other"                  -> autre produit Pokémon du set 30 ans      => note groupée
      None                         -> pas concerné
    On exclut le japonais (le client veut l'anglais ; la langue est indiquée dans l'alerte).
    « Elite Trainer Box » et « Ultra Premium Collection » sont des noms propres à Pokémon :
    on les accepte même si le mot « pokémon » manque du titre. Les tokens courts ETB/UPC
    (UPC = aussi un code-barres) et les produits « 30 ans » génériques exigent, eux, le mot
    « Pokémon » (pour écarter Jurassic Park / Street Sharks « 30th Anniversary », etc.).
    """
    t, ta = _prep(text)
    if _is_japanese(ta):
        return None
    if "pokemon day" in ta:      # exclut l'ancien « Pokémon Day 30th Anniversary Collection Box »
        return None
    if not _is_anniversary(t, ta):
        return None
    # CIBLES ETB/UPC : noms propres à Pokémon -> on N'EXIGE PAS le mot « pokémon »
    # (priorité = ne JAMAIS rater le lancement, quitte à quelques fausses alertes).
    if "ultra premium" in ta or "ultra-premium" in ta or re.search(r"\bupc\b", ta):
        return "target_upc"
    if ("elite trainer" in ta or "top-trainer" in ta or "top trainer" in ta or "toptrainer" in ta
            or "dresseur d'elite" in ta or "coffret dresseur" in ta or re.search(r"\betb\b", ta)):
        return "target_etb"
    # Produit « 30 ans » générique (booster, blister...) -> exiger « pokémon »
    # uniquement ici, pour ne pas être noyé sous les Street Sharks / Jurassic Park « 30th ».
    if "pokemon" in ta:
        return "set_other"
    return None


def _html_hit(t, ta):
    """
    Tripwire pour les sites NON-Shopify (surveillés par page de recherche).
    On exige l'anniversaire ET un vrai signe de produit ETB/UPC — sinon une page de recherche
    qui ne fait que RÉAFFICHER le terme cherché (« 30th celebration ») déclencherait à tort.
    """
    if _is_japanese(ta):
        return False
    tn = re.sub(r"[-_/]+", " ", ta)      # « 30th-celebration-etb » (URL/slug) -> « 30th celebration etb »
    if not _is_anniversary(tn, tn):
        return False
    has_type = ("elite trainer" in tn or "ultra premium" in tn or "top trainer" in tn
                or ("dresseur" in tn and "elite" in tn)
                or re.search(r"\betb\b", tn) is not None or re.search(r"\bupc\b", tn) is not None)
    if not has_type:
        return False
    # page « aucun résultat » -> pas un vrai hit
    if ("aucun resultat" in ta or "no result" in ta or "0 result" in ta
            or "no products" in ta or "did not match" in ta or "keine ergebnisse" in ta):
        return False
    return True


def guess_language(text):
    _, ta = _prep(text)
    if re.search(r"\ben\b", ta) or "english" in ta or "anglais" in ta or "englisch" in ta or "-en-" in ta or "(en)" in ta:
        return "EN"
    if re.search(r"\bfr\b", ta) or "french" in ta or "francais" in ta or "(fr)" in ta:
        return "FR"
    if re.search(r"\bde\b", ta) or "deutsch" in ta or "allemand" in ta or "german" in ta or "(de)" in ta:
        return "DE"
    return "?"


# ─────────────────────────── État (mémoire) ───────────────────────────

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault("initialized", False)
    s.setdefault("seen", {})   # "site::id" -> {"title","available","lang","url"}
    s.setdefault("html", {})   # "site::url" -> bool (mot-clé présent au dernier passage)
    s.setdefault("hb", {})     # "midi"/"minuit" -> date du dernier message de veille envoyé
    return s


def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


# ─────────────────────────── Récupération des boutiques ───────────────────────────

def fetch_shopify(base):
    """Renvoie la liste des produits Shopify, ou None si ce n'est pas du Shopify."""
    products = []
    for page in range(1, 8):  # jusqu'à ~1750 produits
        url = f"{base}/products.json?limit=250&page={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        except Exception as e:
            print(f"    [shopify] {base} injoignable : {e}")
            return None
        if r.status_code != 200:
            return None
        ct = r.headers.get("Content-Type", "")
        if "json" not in ct and not r.text.strip().startswith("{"):
            return None
        try:
            batch = r.json().get("products", [])
        except Exception:
            return None
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 250:
            break
    return products


def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"    [html] {url} -> HTTP {r.status_code}")
            return None
        return r.text
    except Exception as e:
        print(f"    [html] {url} injoignable : {e}")
        return None


# ─────────────────────────── Traitement d'un site ───────────────────────────

def process_shopify(site, products, state, alerts, other_by_site, first_run):
    base = site["base"]
    for p in products:
        blob = " ".join(str(p.get(k, "")) for k in ("title", "handle", "product_type", "tags", "vendor"))
        kind = classify(blob)
        if not kind:
            continue
        pid = str(p.get("id"))
        handle = p.get("handle", "")
        url = f"{base}/products/{handle}"
        variants = p.get("variants", []) or []
        available = any(v.get("available") for v in variants)
        price = ""
        if variants:
            price = variants[0].get("price", "") or ""
        title = p.get("title", "").strip()
        lang = guess_language(blob)
        key = f"{site['name']}::{pid}"

        if kind == "set_other":
            # produit du set mais pas ETB/UPC -> juste signaler l'apparition, groupé
            if key not in state["seen"]:
                if not first_run:
                    other_by_site.setdefault(site["name"], []).append(title)
                state["seen"][key] = {"title": title, "available": available, "lang": lang, "url": url, "cat": kind}
            else:
                state["seen"][key]["available"] = available
            continue

        # produit CIBLE (ETB / UPC)
        label = "UPC" if kind == "target_upc" else "ETB"
        if key not in state["seen"]:
            if not first_run:
                alerts.append({"kind": "NOUVEAU", "label": label, "site": site["name"],
                               "title": title, "price": price, "currency": site.get("currency", ""),
                               "lang": lang, "available": available, "url": url})
            state["seen"][key] = {"title": title, "available": available, "lang": lang, "url": url, "cat": kind}
        else:
            was = state["seen"][key].get("available", False)
            if available and not was and not first_run:
                alerts.append({"kind": "EN STOCK", "label": label, "site": site["name"],
                               "title": title, "price": price, "currency": site.get("currency", ""),
                               "lang": lang, "available": available, "url": url})
            state["seen"][key]["available"] = available
            state["seen"][key]["title"] = title


def process_html(site, state, alerts, first_run):
    for url in site.get("search_urls", [site["base"]]):
        html = fetch_html(url)
        if html is None:
            continue
        # tripwire : un vrai produit ETB/UPC « 30 ans » apparaît-il sur la page ?
        t, ta = _prep(html)
        present = _html_hit(t, ta)
        key = f"{site['name']}::{url}"
        was = state["html"].get(key, False)
        if present and not was and not first_run:
            alerts.append({"kind": "À VÉRIFIER", "label": "PAGE", "site": site["name"],
                           "title": "Un produit '30 ans' est apparu sur la page surveillée",
                           "price": "", "currency": "", "lang": "?", "available": True, "url": url})
        state["html"][key] = present


# ─────────────────────────── Mise en forme des messages ───────────────────────────

def format_alert(a):
    icon = {"NOUVEAU": "🚨", "EN STOCK": "🟢", "À VÉRIFIER": "👀"}.get(a["kind"], "🔔")
    price = f"\nPrix : {a['price']} {a['currency']}".rstrip() if a.get("price") else ""
    lang = f"\nLangue probable : {a['lang']}" if a.get("lang") and a["lang"] != "?" else "\nLangue : à vérifier"
    return (f"{icon} {a['kind']} — {a['label']} 30 ans\n"
            f"Boutique : {a['site']}\n"
            f"Produit : {a['title']}"
            f"{price}{lang}\n"
            f"➡️ {a['url']}")


# ─────────────────────────── Message de veille (midi & minuit, heure suisse) ───────────────────────────

# Dates de sortie officielles (version anglaise)
RELEASES = [("ETB", date(2026, 9, 16)), ("UPC (Day & Night)", date(2026, 11, 6))]


def _countdown(today):
    lines = []
    for label, d in RELEASES:
        j = (d - today).days
        if j > 0:
            lines.append(f"• {label} : J-{j}  (sortie {d.strftime('%d.%m.%Y')})")
        elif j == 0:
            lines.append(f"• {label} : 🎉 C'EST AUJOURD'HUI ! ({d.strftime('%d.%m.%Y')})")
        else:
            lines.append(f"• {label} : déjà sortie le {d.strftime('%d.%m.%Y')}")
    return "\n".join(lines)


def daily_heartbeat(state, first_run):
    if first_run:
        return
    now = datetime.now(ZoneInfo("Europe/Zurich"))   # gère l'heure d'été/hiver automatiquement
    today = now.strftime("%Y-%m-%d")
    slot = "midi" if now.hour == 12 else ("minuit" if now.hour == 0 else None)
    if not slot:
        return
    hb = state.setdefault("hb", {})
    if hb.get(slot) == today:          # déjà envoyé pour ce créneau aujourd'hui
        return
    msg = (f"✅ Robot toujours en veille ({slot}) — {len(SITES)} boutiques surveillées, "
           "rien manqué. Tu seras prévenu dès qu'un ETB/UPC apparaît ou revient en stock.")
    if slot == "midi":                 # compte à rebours dans le message de midi
        msg += "\n\n⏳ Compte à rebours jusqu'à la sortie :\n" + _countdown(now.date())
    send_telegram(msg)
    hb[slot] = today


# ─────────────────────────── Programme principal ───────────────────────────

def main():
    if os.environ.get("TEST_ALERT"):
        send_telegram("✅ Test du robot Pokémon : si tu lis ce message, les alertes Telegram fonctionnent !")
        print("Message de test envoyé.")
        return

    state = load_state()
    first_run = not state["initialized"]
    alerts = []
    other_by_site = {}

    for site in SITES:
        print(f"→ {site['name']} ({site['type']})")
        try:
            products = None
            if site["type"] in ("shopify", "auto"):
                products = fetch_shopify(site["base"])
            if products is not None:
                process_shopify(site, products, state, alerts, other_by_site, first_run)
            elif site["type"] in ("html", "auto"):
                process_html(site, state, alerts, first_run)
            else:
                print(f"    [!] Shopify indisponible et pas de repli HTML pour {site['name']}")
        except Exception as e:
            print(f"    [!] erreur sur {site['name']} : {e}")

    # Envoi
    if first_run:
        total = len(state["seen"])
        dispo = [v for v in state["seen"].values()
                 if str(v.get("cat", "")).startswith("target") and v.get("available")]
        msg = ("🤖 Robot de surveillance Pokémon '30 ans' : DÉMARRÉ.\n"
               f"{len(SITES)} boutiques surveillées, vérification toutes les ~5 min.\n"
               f"Produits '30 ans' déjà mémorisés : {total}.\n")
        if dispo:
            msg += ("\n⚠️ ETB/UPC DÉJÀ EN STOCK maintenant (à saisir sans attendre) :\n"
                    + "\n".join(f"• {v['title']} — {v['url']}" for v in dispo[:15]))
        else:
            msg += "\nAucun ETB/UPC en stock à cet instant. Tu seras alerté dès qu'il y en a un."
        send_telegram(msg)
        state["initialized"] = True
        print(f"Premier lancement : {total} produits mémorisés ({len(dispo)} ETB/UPC en stock).")
    else:
        for a in alerts:
            notify(f"Pokémon 30 ans — {a['kind']} {a['label']} ({a['site']})", format_alert(a))
        # note groupée pour les autres produits du set (boosters, blisters...)
        for site_name, titles in other_by_site.items():
            notify(
                f"Pokémon 30 ans — nouveautés chez {site_name}",
                "👀 D'autres produits '30 ans' viennent d'apparaître chez "
                f"{site_name} ({len(titles)}) — va vérifier s'il y a l'ETB/UPC :\n- "
                + "\n- ".join(titles[:20]),
            )
        print(f"{len(alerts)} alerte(s) cible + {len(other_by_site)} site(s) avec autres nouveautés.")

    daily_heartbeat(state, first_run)
    save_state(state)
    print("Terminé.")


if __name__ == "__main__":
    sys.exit(main())
