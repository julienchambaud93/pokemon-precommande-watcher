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
import email as emaillib
import imaplib
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from email.header import decode_header
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
TIMEOUT = 15   # délai max par site (un site lent ne doit pas ralentir tout le cycle)
SITE_SAFETY = {s["name"]: s.get("safety") for s in SITES}   # nom -> note de sûreté /10


def _shop_domain(base):
    return re.sub(r"^https?://(www\.)?", "", base or "").split("/")[0].lower()


# Domaines des boutiques (pour repérer un mail venant d'une boutique) + mots-clés de précommande.
SHOP_DOMAINS = sorted({_shop_domain(s["base"]) for s in SITES if s.get("base")})
MAIL_KEYWORDS = ("precommande", "précommande", "preorder", "pre-order", "pre order", "delta reign",
                 "delta rain", "30th", "30 ans", "celebration", "célébration", "anniversa", "restock",
                 "back in stock", "de retour", "en stock", "disponible", "vorbestell", "coming soon",
                 "bientôt disponible", "expédiée", "confirmation de commande", "order confirm",
                 "votre commande", "pokémon", "pokemon")
MAIL_EXCLUDE = ("github.com", "ci_activity", "workflow run", "run failed", "jobs have failed", "google play")


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


def _is_delta(ta):
    # Nouveau set anglais « Delta Reign » (ME06, sortie 06.11.2026). On tolère la faute « Delta Rain ».
    return "delta reign" in ta or "delta rain" in ta


def _set_tag(text):
    """Étiquette courte du set pour l'affichage des alertes."""
    t, ta = _prep(text)
    if _is_delta(ta):
        return "Delta Reign"
    if _is_anniversary(t, ta):
        return "30 ans"
    return "Pokémon"


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
    if not (_is_anniversary(t, ta) or _is_delta(ta)):   # set « 30 ans » OU nouveau set « Delta Reign »
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


# Motif « produit 30 ans » pour les sites NON-Shopify : anniversaire ET type ETB/UPC COLLÉS dans le
# MÊME texte (sans balise < > entre eux) = un vrai titre de produit. Évite les faux positifs (terme de
# recherche réaffiché, liens de langue, entrées de menu éparpillées sur la page).
_ANNIV = r"(?:30th|30 ?e |30 ?eme |30 ?ans|30 ?jahre|30 ?anniversa|jubil|trenti|delta reign|delta rain)"
_TYP = r"(?:elite trainer|ultra premium|top ?trainer|dresseur[^<>]{0,6}elite|\betb\b|\bupc\b)"
_HTML_PAT = re.compile(_ANNIV + r"[^<>]{0,45}" + _TYP + r"|" + _TYP + r"[^<>]{0,45}" + _ANNIV)


def _html_hits(html):
    """Ensemble des libellés « 30 ans + ETB/UPC » réellement présents sur la page (vide si aucun)."""
    _, ta = _prep(html)
    tn = re.sub(r"[-_/]+", " ", ta)
    return set(re.sub(r"\s+", " ", m.group(0)).strip() for m in _HTML_PAT.finditer(tn))


# Lecture "manuelle" du stock sur les sites NON-Shopify : on ouvre chaque fiche produit 30 ans
# et on lit si c'est en rupture ou achetable. La rupture est prioritaire (badge plus explicite).
_STOCK_OUT = ("sold out", "sold-out", "soldout", "out of stock", "rupture", "epuise", "epuisee",
              "indisponible", "non disponible", "plus disponible", "ausverkauft", "vergriffen",
              "nicht verfugbar", "nicht mehr verfugbar", "coming soon", "bientot disponible",
              "notify me", "benachrichtige", "me prevenir")
_STOCK_IN = ("add to cart", "ajouter au panier", "in den warenkorb", "aggiungi al carrello",
             "add-to-cart", "addtocart", "buy now", "acheter", "kaufen", "precommander",
             "pre-order", "preorder", "vorbestellen", "in stock", "en stock", "disponible")


def _stock_state(html):
    """"out" (rupture / pas encore ouvert), "in" (achetable) ou "unknown".

    On lit EN PRIORITÉ le balisage standard schema.org (itemprop availability) : c'est le vrai
    statut, présent côté serveur même sur les sites JavaScript type Odoo (ex. Draft Arena) où le
    texte « Ajouter au panier » est statique et trompeur. À défaut, on retombe sur les mots-clés.
    """
    hl = html.lower()
    # (0) WooCommerce
    if "product-type-variable" in hl:
        # Produit à VARIANTES (ex. langue EN/DE) : le « instock » du parent ne garantit PAS qu'une
        # variante soit achetable. On lit les variantes SI elles sont embarquées dans la page ;
        # sinon (chargées en AJAX) on ne conclut rien ici -> on laisse schema/mots-clés décider plus bas.
        if re.search(r'"is_in_stock":\s*true', hl):
            return "in"                      # au moins une variante réellement en stock
        if re.search(r'"is_in_stock":\s*(true|false)', hl):
            return "out"                     # variantes présentes, aucune en stock
        # sinon : variantes non lisibles (AJAX) -> pas de décision ici
    else:
        # Produit SIMPLE : la classe du conteneur principal <div id="product-XXX" class="... instock|outofstock">
        # est fiable (1er match = produit principal ; les produits liés viennent après).
        m = re.search(r'id="product-\d+"[^>]*class="([^"]*)"', hl)
        if m and "product" in m.group(1):
            if "outofstock" in m.group(1):
                return "out"
            if "instock" in m.group(1):
                return "in"
    _, ta = _prep(html)
    # ACHETABLE (signaux FORTS du produit principal) — en priorité pour ne pas rater le passage en dispo :
    #   - schema.org/InStock (standard : Odoo, PrestaShop, WooCommerce avec schema)
    #   - delivery-available (classe Shopware du produit principal ; opposée de delivery-soldout)
    if "schema.org/instock" in ta or "delivery-available" in ta:
        return "in"
    # RUPTURE (fiable) : schema OutOfStock/SoldOut, classe Shopware delivery-soldout, ou mots explicites.
    # On IGNORE « LimitedAvailability » et les boutons « add to cart » de cross-sell (faux positifs Shopware).
    if any(s in ta for s in ("schema.org/outofstock", "schema.org/soldout", "schema.org/discontinued")):
        return "out"
    if "delivery-soldout" in ta:
        return "out"
    if any(tok in ta for tok in _STOCK_OUT):
        return "out"
    return "unknown"


def _extract_product_urls(base, html):
    """URLs de fiches produit dont l'adresse contient « 30 ans + ETB/UPC » (liens href ou <loc> de sitemap)."""
    urls = set()
    for m in re.finditer(r'(?:href=["\']|<loc>)\s*([^"\'<>\s]+)', html):
        u = m.group(1)
        if _HTML_PAT.search(re.sub(r"[-_/]+", " ", u.lower())):
            if u.startswith("http"):
                full = u
            elif u.startswith("//"):
                full = "https:" + u
            else:
                full = base.rstrip("/") + "/" + u.lstrip("/")
            urls.add(full.split("?")[0].split("#")[0])
    return urls


def _label_from_url(u):
    slug = re.sub(r"[-_]+", " ", u.rstrip("/").split("/")[-1])
    slug = re.sub(r"\b\d{2,}\b", "", slug).strip()
    return slug[:80] or u


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
    s.setdefault("seen", {})           # "site::id" -> {"title","available","lang","url"}
    s.setdefault("html", {})           # "site::url" -> bool (mot-clé présent au dernier passage)
    s.setdefault("hb", {})             # "midi"/"minuit" -> date du dernier message de veille envoyé
    s.setdefault("seeded_sites", [])   # boutiques déjà "amorcées" en silence (évite le flot à l'ajout)
    s.setdefault("stock", {})          # (sites non-Shopify) url fiche produit -> "in"/"out" lu sur la page
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

def process_shopify(site, products, state, alerts, other_by_site, seed):
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
            # produit du set mais pas ETB/UPC -> juste signaler l'apparition, groupé (avec lien)
            if key not in state["seen"]:
                if not seed:
                    other_by_site.setdefault(site["name"], []).append((title, url))
                state["seen"][key] = {"title": title, "available": available, "lang": lang, "url": url, "cat": kind}
            else:
                state["seen"][key]["available"] = available
            continue

        # produit CIBLE (ETB / UPC)
        label = "UPC" if kind == "target_upc" else "ETB"
        if key not in state["seen"]:
            if not seed:
                alerts.append({"kind": "NOUVEAU", "label": label, "site": site["name"],
                               "title": title, "price": price, "currency": site.get("currency", ""),
                               "lang": lang, "available": available, "url": url,
                               "safety": site.get("safety"), "set": _set_tag(blob)})
            state["seen"][key] = {"title": title, "available": available, "lang": lang, "url": url, "cat": kind}
        else:
            was = state["seen"][key].get("available", False)
            if available and not was and not seed:
                alerts.append({"kind": "EN STOCK", "label": label, "site": site["name"],
                               "title": title, "price": price, "currency": site.get("currency", ""),
                               "lang": lang, "available": available, "url": url,
                               "safety": site.get("safety"), "set": _set_tag(blob)})
            state["seen"][key]["available"] = available
            state["seen"][key]["title"] = title


def process_html(site, state, alerts, seed):
    got = False           # True si au moins une page a pu être lue (sinon on ne "valide" pas le site)
    product_urls = set()  # fiches produit 30 ans repérées, dont on ira lire le stock
    for url in site.get("search_urls", [site["base"]]):
        html = fetch_html(url)
        if html is None:
            continue
        got = True
        # (1) APPARITION : nouveau libellé « 30 ans + ETB/UPC » sur la page (proximité)
        hits = _html_hits(html)
        key = f"{site['name']}::{url}"
        prev = state["html"].get(key)
        prev_set = set(prev) if isinstance(prev, list) else set()
        nouveaux = sorted(h for h in hits if h not in prev_set)
        if nouveaux and not seed and isinstance(prev, list):
            alerts.append({"kind": "À VÉRIFIER", "label": "PAGE", "site": site["name"],
                           "title": "Produit(s) APPARU(S) — peut déjà être en rupture, à vérifier : "
                                    + ", ".join(nouveaux[:5]),
                           "price": "", "currency": "", "lang": "?", "available": True, "url": url,
                           "safety": site.get("safety"), "set": _set_tag(" ".join(nouveaux))})
        state["html"][key] = sorted(prev_set | hits)
        # (2) collecte des URLs de fiches produit 30 ans
        product_urls |= _extract_product_urls(site["base"], html)

    # (3) STOCK : on ouvre chaque fiche et on alerte sur rupture -> achetable
    for purl in sorted(product_urls)[:8]:
        phtml = fetch_html(purl)
        if phtml is None:
            continue
        st = _stock_state(phtml)
        if st == "unknown":
            continue
        skey = f"{site['name']}::{purl}"
        prevst = state["stock"].get(skey)
        # alerte uniquement sur une VRAIE transition (déjà connu non-achetable) -> achetable
        if prevst is not None and prevst != "in" and st == "in" and not seed:
            alerts.append({"kind": "EN STOCK", "label": "ETB/UPC", "site": site["name"],
                           "title": _label_from_url(purl), "price": "", "currency": site.get("currency", ""),
                           "lang": "?", "available": True, "url": purl,
                           "safety": site.get("safety"), "set": _set_tag(purl)})
        state["stock"][skey] = st
    return got


# ─────────────────────────── Mise en forme des messages ───────────────────────────

def format_alert(a):
    icon = {"NOUVEAU": "🚨", "EN STOCK": "🟢", "À VÉRIFIER": "👀"}.get(a["kind"], "🔔")
    price = f"\nPrix : {a['price']} {a['currency']}".rstrip() if a.get("price") else ""
    lang = f"\nLangue probable : {a['lang']}" if a.get("lang") and a["lang"] != "?" else "\nLangue : à vérifier"
    safety = f" (🛡️ sûreté {a['safety']}/10)" if a.get("safety") is not None else ""
    stag = a.get("set") or ""
    entete = f"{icon} {a['kind']} — {a['label']} {stag}".rstrip()
    return (f"{entete}\n"
            f"Boutique : {a['site']}{safety}\n"
            f"Produit : {a['title']}"
            f"{price}{lang}\n"
            f"➡️ {a['url']}")


# ─────────────────────────── Message de veille (midi & minuit, heure suisse) ───────────────────────────

# Dates de sortie officielles (version anglaise)
RELEASES = [
    ("ETB 30 ans", date(2026, 9, 16)),
    ("UPC 30 ans (Day & Night)", date(2026, 11, 6)),
    ("Delta Reign (nouveau set)", date(2026, 11, 6)),
]


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


def daily_heartbeat(state, first_run, lus_ok=0, lus_ko=None):
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
    lus_ko = lus_ko or []
    msg = (f"✅ Robot toujours en veille ({slot}) — {len(SITES)} boutiques surveillées, "
           "rien manqué. Tu seras prévenu dès qu'un ETB/UPC apparaît ou revient en stock.")
    # auto-contrôle : combien de boutiques ont pu être lues à ce passage
    msg += f"\n\n📡 Lecture : {lus_ok}/{len(SITES)} boutiques OK ce cycle."
    if lus_ko:
        apercu = ", ".join(lus_ko[:8]) + ("…" if len(lus_ko) > 8 else "")
        msg += f"\n⚠️ Non lues ({len(lus_ko)}) : {apercu}\n(souvent temporaire — à signaler si toujours là demain)"
    if slot == "midi":                 # compte à rebours dans le message de midi
        msg += "\n\n⏳ Compte à rebours jusqu'à la sortie :\n" + _countdown(now.date())
    send_telegram(msg)
    hb[slot] = today


# ─────────────────────────── Mode RAPPORT (compte-rendu immédiat sur Telegram) ───────────────────────────

def run_report():
    header = [
        "📋 COMPTE-RENDU IMMÉDIAT — ETB / UPC (30 ans & Delta Reign) détectés maintenant",
        "🟢 = commandable   🔴 = rupture (souvent : précommande pas encore ouverte, ou déjà partie)",
        "",
    ]
    blocks = []
    for site in SITES:
        if site["type"] not in ("shopify", "auto"):
            continue
        try:
            products = fetch_shopify(site["base"])
        except Exception:
            products = None
        if not products:
            continue
        targets, others = [], 0
        for p in products:
            blob = " ".join(str(p.get(k, "")) for k in ("title", "handle", "product_type", "tags", "vendor"))
            kind = classify(blob)
            if not kind:
                continue
            if kind == "set_other":
                others += 1
                continue
            variants = p.get("variants") or []
            available = any(v.get("available") for v in variants)
            price = variants[0].get("price", "") if variants else ""
            lab = "UPC" if kind == "target_upc" else "ETB"
            dot = "🟢" if available else "🔴"
            url = f"{site['base']}/products/{p.get('handle', '')}"
            targets.append(f"  {dot} [{lab}] {p.get('title', '').strip()} — {price} {site.get('currency', '')}\n     {url}")
        if targets or others:
            head = f"🏬 {site['name']} — 🛡️ sûreté {site.get('safety', '?')}/10"
            body = "\n".join(targets) if targets else "  (aucun ETB/UPC listé)"
            extra = f"\n  (+{others} autre(s) produit 30 ans)" if others else ""
            blocks.append(head + "\n" + body + extra)
    if not blocks:
        blocks = ["Aucun ETB/UPC « 30 ans » détecté sur les boutiques lisibles pour l'instant."]
    footer = [
        "",
        "ℹ️ Les sites non lisibles à distance (Coop, Manor, Draft Arena, Amazing Toys, WooCommerce…) "
        "sont surveillés « par page » — non listés ici.",
        "🗓️ ETB 30 ans : 16.09.2026 · UPC 30 ans & Delta Reign : 06.11.2026.",
    ]
    send_telegram("\n".join(header + blocks + footer))
    print(f"Rapport envoyé ({len(blocks)} boutique(s) avec produits).")


# ─────────────────────────── Surveillance des mails de boutiques ───────────────────────────

def _dec(h):
    """Décode un en-tête MIME (From/Subject) en texte lisible."""
    if not h:
        return ""
    out = []
    for part, enc in decode_header(h):
        if isinstance(part, bytes):
            try:
                out.append(part.decode(enc or "utf-8", "ignore"))
            except Exception:
                out.append(part.decode("utf-8", "ignore"))
        else:
            out.append(part)
    return "".join(out)


def _mail_pertinent(sender, subject):
    hay = (sender + " " + subject).lower()
    if any(x in hay for x in MAIL_EXCLUDE):
        return False
    return any(d in hay for d in SHOP_DOMAINS) or any(k in hay for k in MAIL_KEYWORDS)


def check_mail(state, report=False):
    """Lit le Gmail (mails de boutiques redirigés depuis Hotmail) via IMAP.
    - normal : ping Telegram sur chaque NOUVEAU mail de boutique.
    - report=True : scan large (90 j, boîte + spam) et renvoie un récap à la demande."""
    user = os.environ.get("GMAIL_IMAP_USER")
    pw = os.environ.get("GMAIL_IMAP_PASS")
    if not (user and pw):
        if report:
            send_telegram("📭 Check mail impossible : l'accès à la boîte n'est pas encore configuré "
                          "(secrets GMAIL_IMAP_USER / GMAIL_IMAP_PASS manquants).")
        print("[mail] secrets IMAP absents -> lecture des mails ignorée")
        return
    seen = state.setdefault("mails_seen", [])
    seen_set = set(seen)
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        M.login(user, pw)
    except Exception as e:
        print("[mail] connexion IMAP échouée:", e)
        if report:
            send_telegram(f"📭 Check mail : connexion à Gmail échouée ({e}). "
                          "Vérifie le mot de passe d'application et que l'IMAP est activé.")
        return
    jours = 90 if report else 4
    since = (datetime.now() - timedelta(days=jours)).strftime("%d-%b-%Y")
    trouves = []
    for fol in ("INBOX", '"[Gmail]/Spam"'):
        try:
            if M.select(fol, readonly=True)[0] != "OK":
                continue
            typ, data = M.search(None, "(SINCE %s)" % since)
        except Exception:
            continue
        if typ != "OK" or not data or not data[0]:
            continue
        for num in data[0].split()[-200:]:
            try:
                typ, md = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT MESSAGE-ID DATE)])")
            except Exception:
                continue
            if typ != "OK" or not md or not md[0]:
                continue
            msg = emaillib.message_from_bytes(md[0][1])
            sender = _dec(msg.get("From"))
            subject = _dec(msg.get("Subject"))
            msgid = (msg.get("Message-ID") or (sender + "|" + subject))[:200]
            if not _mail_pertinent(sender, subject):
                continue
            if not report and msgid in seen_set:
                continue
            trouves.append({"date": _dec(msg.get("Date")), "de": sender, "objet": subject, "id": msgid})
    try:
        M.logout()
    except Exception:
        pass

    def _court(sender):
        return (sender.split("<")[0].strip().strip('"') or sender)[:60]

    if report:
        if trouves:
            m = f"📬 CHECK MAIL — {len(trouves)} mail(s) de boutique trouvé(s) (90 j, boîte + spam) :\n"
            for t in trouves[:15]:
                m += f"\n• {t['objet']}\n   de {_court(t['de'])} — {t['date']}"
            if len(trouves) > 15:
                m += f"\n\n… + {len(trouves) - 15} autres."
        else:
            m = "📭 CHECK MAIL : aucun mail de boutique détecté sur les 90 derniers jours (boîte + spam)."
        send_telegram(m)
    else:
        premier = not state.get("mail_initialized")   # 1er passage : on mémorise SANS pinguer (anti-spam)
        for t in trouves:
            if premier:
                continue
            send_telegram("📧 NOUVEAU MAIL boutique\n"
                          f"De : {_court(t['de'])}\n"
                          f"Objet : {t['objet']}\n"
                          f"({t['date']})\n"
                          "👉 Va vérifier ta boîte mail (précommande / expédition ?).")
        state["mail_initialized"] = True
    for t in trouves:
        if t["id"] not in seen_set:
            seen.append(t["id"]); seen_set.add(t["id"])
    if len(seen) > 800:
        state["mails_seen"] = seen[-800:]
    print(f"[mail] {len(trouves)} mail(s) de boutique {'(report)' if report else 'nouveau(x)'}")


# ─────────────────────────── Programme principal ───────────────────────────

def main():
    mode = os.environ.get("MODE", "").strip().lower()
    if os.environ.get("TEST_ALERT") or mode == "test":
        send_telegram("✅ Test du robot Pokémon : si tu lis ce message, les alertes Telegram fonctionnent !")
        print("Message de test envoyé.")
        return
    if mode == "rapport":
        run_report()
        return
    if mode == "checkmail":
        state = load_state()
        check_mail(state, report=True)
        save_state(state)
        return

    state = load_state()
    first_run = not state["initialized"]
    alerts = []
    other_by_site = {}
    lus_ok = 0        # nb de boutiques lues avec succès (auto-contrôle)
    lus_ko = []       # noms des boutiques injoignables ce passage

    for site in SITES:
        # amorçage silencieux : 1er démarrage global OU boutique tout juste ajoutée
        seed = first_run or (site["name"] not in state["seeded_sites"])
        print(f"→ {site['name']} ({site['type']}){' [amorçage silencieux]' if seed else ''}")
        processed = False
        try:
            products = None
            if site["type"] in ("shopify", "auto"):
                products = fetch_shopify(site["base"])
            if products is not None:
                process_shopify(site, products, state, alerts, other_by_site, seed)
                processed = True
            elif site["type"] in ("html", "auto"):
                processed = bool(process_html(site, state, alerts, seed))
            else:
                print(f"    [!] Shopify indisponible et pas de repli HTML pour {site['name']}")
        except Exception as e:
            print(f"    [!] erreur sur {site['name']} : {e}")
        # ne marquer « déjà vu » QUE si la lecture a réussi (sinon un site rate-limité re-déclencherait
        # tous ses produits en « NOUVEAU » au passage suivant) -> on ré-essaiera l'amorçage plus tard
        if processed and site["name"] not in state["seeded_sites"]:
            state["seeded_sites"].append(site["name"])
        if processed:
            lus_ok += 1
        else:
            lus_ko.append(site["name"])

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
        for site_name, items in other_by_site.items():
            note = SITE_SAFETY.get(site_name)
            note_txt = f" (🛡️ sûreté {note}/10)" if note is not None else ""
            lignes = "\n".join(f"• {t}\n➡️ {u}" for t, u in items[:15])
            notify(
                f"Pokémon 30 ans / Delta Reign — nouveautés chez {site_name}",
                f"👀 D'autres produits (30 ans / Delta Reign) viennent d'apparaître chez {site_name}{note_txt} "
                f"({len(items)}) — va vérifier s'il y a l'ETB/UPC :\n" + lignes,
            )
        print(f"{len(alerts)} alerte(s) cible + {len(other_by_site)} site(s) avec autres nouveautés.")

    daily_heartbeat(state, first_run, lus_ok, lus_ko)
    check_mail(state)      # ping Telegram sur les nouveaux mails de boutiques (redirigés vers Gmail)
    save_state(state)
    print("Terminé.")


if __name__ == "__main__":
    sys.exit(main())
