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
  safety       : note de sûreté /10 (1 = arnaque probable, 10 = sûr) — affichée dans chaque alerte
  best_effort  : True = gros site / JS qui peut bloquer les robots (surveillance non garantie)
"""

SITES = [
    # ─────────── Tes 9 boutiques d'origine ───────────
    {"name": "Pokecard Store",  "base": "https://pokecard.store",      "type": "shopify", "currency": "CHF", "safety": 8},
    {"name": "Zaibatsu",        "base": "https://zaibatsu.ch",         "type": "shopify", "currency": "CHF", "safety": 5},
    {"name": "Collecting Cloud","base": "https://collecting.cloud",    "type": "shopify", "currency": "CHF", "safety": 7},
    {"name": "Tamori Cards",    "base": "https://tamoricards.ch",      "type": "shopify", "currency": "CHF", "safety": 8},
    {"name": "Poke Swiss",      "base": "https://poke-swiss.ch",       "type": "shopify", "currency": "CHF", "safety": 5},
    {"name": "Coffre à Dom",    "base": "https://www.coffreadom.ch",   "type": "auto",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://www.coffreadom.ch/?s=30th+celebration&post_type=product",
                     "https://www.coffreadom.ch/boutique/"]},
    {"name": "GoodGames Bern",  "base": "https://www.goodgamesbern.ch","type": "auto",    "currency": "CHF", "safety": 9,
     "search_urls": ["https://www.goodgamesbern.ch/?s=30th+celebration"]},
    {"name": "The Mana Shop",   "base": "https://themanashop.ch",      "type": "auto",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://themanashop.ch/search?q=30th+celebration"]},
    {"name": "Miixy's Cards",   "base": "https://miixyscards.ch",      "type": "auto",    "currency": "CHF", "safety": 7,
     "search_urls": ["https://miixyscards.ch/recherche?controller=search&s=30th%20celebration"]},

    # ─────────── Boutiques spécialisées recommandées ───────────
    {"name": "Swiss Pokéshop",  "base": "https://swiss-pokeshop.ch",   "type": "shopify", "currency": "CHF", "safety": 8},
    {"name": "LaschoCards",     "base": "https://laschocards.ch",      "type": "shopify", "currency": "CHF", "safety": 8},
    {"name": "Pokécado",        "base": "https://www.pokecado.ch",     "type": "shopify", "currency": "CHF", "safety": 7},
    {"name": "AmazinGames",     "base": "https://amazingames.ch",      "type": "shopify", "currency": "CHF", "safety": 7},
    {"name": "Outpost Brussels","base": "https://outpostbrussels.be",  "type": "shopify", "currency": "EUR", "safety": 8},
    {"name": "The Uncommon Shop","base": "https://theuncommonshop.ch", "type": "html",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://theuncommonshop.ch/?s=30th+celebration&post_type=product"]},
    {"name": "World of Games",  "base": "https://www.wog.ch",          "type": "html",    "currency": "CHF", "safety": 9,
     "search_urls": ["https://www.wog.ch/en/index.cfm/promotion/type/Games/title/2558-Pokemon-30th-Anniversary"]},
    {"name": "Philibert",       "base": "https://www.philibertnet.com","type": "html",    "currency": "EUR", "safety": 9,
     "search_urls": ["https://www.philibertnet.com/en/recherche?controller=search&s=30th%20celebration"]},
    {"name": "Draft Arena",     "base": "https://www.draftarena.ch",   "type": "html",    "currency": "CHF", "safety": 8, "best_effort": True,
     "search_urls": ["https://www.draftarena.ch/sitemap.xml"]},

    # ─────────── Nouvelles boutiques (ta 2e liste) ───────────
    {"name": "SkySpell",        "base": "https://skyspell.ch",         "type": "auto",    "currency": "CHF", "safety": 7,
     "search_urls": ["https://skyspell.ch/search?q=30th%20celebration"]},
    {"name": "Softridge",       "base": "https://www.softridge.ch",    "type": "auto",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://www.softridge.ch/en/tcg/pokemon", "https://www.softridge.ch/en/search?q=30th%20celebration"]},
    {"name": "Amazing Toys",    "base": "https://amazingtoys.ch",      "type": "html",    "currency": "CHF", "safety": 9,
     "search_urls": ["https://amazingtoys.ch/search?search=30th%20celebration", "https://amazingtoys.ch/Pre-Order/?immediately-available=1"]},
    {"name": "PikaStore",       "base": "https://www.pikastore.ch",    "type": "auto",    "currency": "CHF", "safety": 6,
     "search_urls": ["https://www.pikastore.ch/search?q=30th%20celebration"]},
    {"name": "MaRo Shop",       "base": "https://www.maro-shop.ch",    "type": "auto",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://www.maro-shop.ch/search?q=30th%20celebration"]},
    {"name": "Detsuki",         "base": "https://detsuki.ch",          "type": "auto",    "currency": "CHF", "safety": 7,
     "search_urls": ["https://detsuki.ch/search?q=30th%20celebration"]},
    {"name": "Brack",           "base": "https://www.brack.ch",        "type": "html",    "currency": "CHF", "safety": 10, "best_effort": True,
     "search_urls": ["https://www.brack.ch/search?query=pokemon%2030th%20celebration"]},
    {"name": "Pikaversum",      "base": "https://pikaversum.ch",       "type": "auto",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://pikaversum.ch/search?q=30th%20celebration"]},
    {"name": "Kabooom",         "base": "https://shop.kabooom.ch",     "type": "auto",    "currency": "CHF", "safety": 9,
     "search_urls": ["https://shop.kabooom.ch/search?q=30th%20celebration"]},
    {"name": "PokeFaust",       "base": "https://pokefaust.com",       "type": "auto",    "currency": "CHF", "safety": 7,
     "search_urls": ["https://pokefaust.com/search?q=30th%20celebration"]},
    {"name": "TCG Treasure",    "base": "https://tcg-treasure.com",    "type": "html",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://tcg-treasure.com/?s=30th+celebration&post_type=product"]},
    {"name": "Naxoria",         "base": "https://naxoria.ch",          "type": "html",    "currency": "CHF", "safety": 6,
     "search_urls": ["https://naxoria.ch/?s=30th+celebration&post_type=product"]},
    {"name": "Zadoys",          "base": "https://zadoys.ch",           "type": "auto",    "currency": "CHF", "safety": 8,
     "search_urls": ["https://zadoys.ch/search?q=30th%20celebration"]},
    {"name": "Carab",           "base": "https://carab.ch",            "type": "auto",    "currency": "CHF", "safety": 9,
     "search_urls": ["https://carab.ch/search?q=30th%20celebration"]},
    {"name": "Toytans",         "base": "https://toytans.ch",          "type": "html",    "currency": "CHF", "safety": 9,
     "search_urls": ["https://toytans.ch/recherche?controller=search&s=30th%20celebration"]},
    {"name": "Pokereaves",      "base": "https://www.pokereaves.ch",   "type": "auto",    "currency": "CHF", "safety": 5,
     "search_urls": ["https://www.pokereaves.ch/search?q=30th%20celebration"]},
    {"name": "Pokemania",       "base": "https://www.pokemania.ch",    "type": "auto",    "currency": "CHF", "safety": 4,
     "search_urls": ["https://www.pokemania.ch/search?q=30th%20celebration"]},
    {"name": "Trainer-Zentrale","base": "https://trainer-zentrale.ch", "type": "auto",    "currency": "CHF", "safety": 6,
     "search_urls": ["https://trainer-zentrale.ch/search?q=30th%20celebration"]},
    {"name": "Collectors Deal", "base": "https://collectorsdeal.ch",   "type": "auto",    "currency": "CHF", "safety": 6,
     "search_urls": ["https://collectorsdeal.ch/search?q=30th%20celebration"]},

    # ─────────── Gros généralistes (best-effort : peuvent bloquer les robots) ───────────
    {"name": "Coop",     "base": "https://www.coop.ch",   "type": "html", "currency": "CHF", "safety": 10, "best_effort": True,
     "search_urls": ["https://www.coop.ch/fr/search/?text=30th%20celebration"]},
    {"name": "Manor",    "base": "https://www.manor.ch",  "type": "html", "currency": "CHF", "safety": 10, "best_effort": True,
     "search_urls": ["https://www.manor.ch/fr/search?q=30th+celebration"]},
    {"name": "Galaxus",  "base": "https://www.galaxus.ch","type": "html", "currency": "CHF", "safety": 9, "best_effort": True,
     "search_urls": ["https://www.galaxus.ch/fr/search?q=30th%20celebration"]},
    {"name": "Migros",   "base": "https://www.migros.ch", "type": "html", "currency": "CHF", "safety": 10, "best_effort": True,
     "search_urls": ["https://www.migros.ch/fr/search?query=30th%20celebration"]},
    {"name": "Smyths Toys CH", "base": "https://www.smythstoys.com", "type": "html", "currency": "CHF", "safety": 9, "best_effort": True,
     "search_urls": ["https://www.smythstoys.com/ch/fr-ch/search/?text=30th+celebration"]},
]
