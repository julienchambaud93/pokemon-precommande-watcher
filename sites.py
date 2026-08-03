# -*- coding: utf-8 -*-
"""
Liste des boutiques surveillées.

Pour AJOUTER une boutique : copie une ligne existante et adapte-la.
Pour EN RETIRER une : mets un # devant, ou supprime la ligne.

Champs :
  name         : nom affiché dans les alertes
  base         : adresse du site (sans / à la fin)
  type         : "shopify"  -> lecture propre de la liste de produits (le plus fiable)
                 "auto"     -> essaie Shopify, sinon lit les pages "search_urls"
                 "html"     -> lit directement les pages "search_urls" (sites non-Shopify)
  search_urls  : (pour "html"/"auto") pages à scruter si Shopify indisponible
  currency     : monnaie affichée dans l'alerte (indicatif)
  best_effort  : True = gros site qui peut bloquer les robots (surveillance non garantie)
"""

SITES = [
    # ─────────── Tes boutiques ───────────
    {"name": "Pokecard Store",  "base": "https://pokecard.store",      "type": "shopify", "currency": "CHF"},
    {"name": "Zaibatsu",        "base": "https://zaibatsu.ch",         "type": "shopify", "currency": "CHF"},
    {"name": "Collecting Cloud","base": "https://collecting.cloud",    "type": "shopify", "currency": "CHF"},
    {"name": "Tamori Cards",    "base": "https://tamoricards.ch",      "type": "shopify", "currency": "CHF"},
    {"name": "Poke Swiss",      "base": "https://poke-swiss.ch",       "type": "shopify", "currency": "CHF"},

    {"name": "Coffre à Dom",    "base": "https://www.coffreadom.ch",   "type": "auto",    "currency": "CHF",
     "search_urls": ["https://www.coffreadom.ch/?s=30th+celebration&post_type=product",
                     "https://www.coffreadom.ch/boutique/"]},
    {"name": "GoodGames Bern",  "base": "https://www.goodgamesbern.ch","type": "auto",    "currency": "CHF",
     "search_urls": ["https://www.goodgamesbern.ch/?s=30th+celebration"]},
    {"name": "The Mana Shop",   "base": "https://themanashop.ch",      "type": "auto",    "currency": "CHF",
     "search_urls": ["https://themanashop.ch/search?q=30th+celebration"]},
    {"name": "Miixy's Cards",   "base": "https://miixyscards.ch",      "type": "auto",    "currency": "CHF",
     "search_urls": ["https://miixyscards.ch/recherche?controller=search&s=30th%20celebration"]},

    # ─────────── Boutiques recommandées (spécialisées) ───────────
    {"name": "Swiss Pokéshop",  "base": "https://swiss-pokeshop.ch",   "type": "shopify", "currency": "CHF"},
    {"name": "LaschoCards",     "base": "https://laschocards.ch",      "type": "shopify", "currency": "CHF"},
    {"name": "Pokécado",        "base": "https://www.pokecado.ch",     "type": "shopify", "currency": "CHF"},
    {"name": "AmazinGames",     "base": "https://amazingames.ch",      "type": "shopify", "currency": "CHF"},
    {"name": "Outpost Brussels","base": "https://outpostbrussels.be",  "type": "shopify", "currency": "EUR"},
    {"name": "World of Games",  "base": "https://www.wog.ch",          "type": "html",    "currency": "CHF",
     "search_urls": ["https://www.wog.ch/en/index.cfm/promotion/type/Games/title/2558-Pokemon-30th-Anniversary"]},
    {"name": "Philibert",       "base": "https://www.philibertnet.com","type": "html",    "currency": "EUR",
     "search_urls": ["https://www.philibertnet.com/en/recherche?controller=search&s=30th%20celebration"]},
    # The Uncommon Shop = WooCommerce (texte lisible) -> surveillance fiable par recherche
    {"name": "The Uncommon Shop","base": "https://theuncommonshop.ch", "type": "html",    "currency": "CHF",
     "search_urls": ["https://theuncommonshop.ch/?s=30th+celebration&post_type=product"]},
    # Draft Arena = site JavaScript -> best-effort via son sitemap (les pages 30 ans existent déjà,
    # capte surtout de NOUVELLES références ; leur propre Telegram reste le vrai filet de sécurité)
    {"name": "Draft Arena",     "base": "https://www.draftarena.ch",   "type": "html",    "currency": "CHF", "best_effort": True,
     "search_urls": ["https://www.draftarena.ch/sitemap.xml"]},

    # ─────────── Gros généralistes (best-effort : peuvent bloquer les robots) ───────────
    {"name": "Coop",     "base": "https://www.coop.ch",   "type": "html", "currency": "CHF", "best_effort": True,
     "search_urls": ["https://www.coop.ch/fr/search/?text=30th%20celebration"]},
    {"name": "Manor",    "base": "https://www.manor.ch",  "type": "html", "currency": "CHF", "best_effort": True,
     "search_urls": ["https://www.manor.ch/fr/search?q=30th+celebration"]},
    {"name": "Galaxus",  "base": "https://www.galaxus.ch","type": "html", "currency": "CHF", "best_effort": True,
     "search_urls": ["https://www.galaxus.ch/fr/search?q=30th%20celebration"]},
    {"name": "Migros",   "base": "https://www.migros.ch", "type": "html", "currency": "CHF", "best_effort": True,
     "search_urls": ["https://www.migros.ch/fr/search?query=30th%20celebration"]},
    {"name": "Smyths Toys CH", "base": "https://www.smythstoys.com", "type": "html", "currency": "CHF", "best_effort": True,
     "search_urls": ["https://www.smythstoys.com/ch/fr-ch/search/?text=30th+celebration"]},
]
