# 🤖 Robot de surveillance — Précommandes Pokémon « 30th Celebration » (ETB & UPC)

Ce robot vérifie **automatiquement toutes les ~5 min**, 24h/24, une liste de boutiques et t'envoie
une **alerte Telegram** dès qu'un **ETB** ou un **UPC** « 30 ans » (anglais) apparaît ou revient en stock.
Il tourne **gratuitement** sur GitHub (même quand ton PC est éteint).

Il détecte le produit **quel que soit le libellé** : « 30th Celebration », « 30th Anniversary »,
« 30ᵉ / 30ème Anniversaire », « trentième », « 30 Jahre / Jubiläum »… et même si le mot « Pokémon »
n'est pas écrit. **Priorité : ne jamais rater le lancement** (quitte à recevoir parfois une alerte en trop).

> ⚠️ Le robot **prévient**, il n'achète pas à ta place. Dès l'alerte, tu vas commander toi-même.

---

## 🗺️ Mise en route (≈ 10 min, aucune compétence technique)

### Étape 1 — Créer ton bot Telegram (sur ton téléphone)
1. Dans Telegram, cherche **@BotFather** (coche bleue) et ouvre-le.
2. Envoie `/newbot`. Donne un nom (ex. *Alerte Pokémon*) puis un identifiant finissant par `bot`
   (ex. `alerte_precommande_pkm_bot`).
3. BotFather te répond avec un **jeton (token)** du genre `8123456789:AAH...`. **Garde-le** (c'est un mot de passe).
4. Ouvre une conversation avec **ton** nouveau bot et envoie-lui `/start` (obligatoire pour qu'il puisse t'écrire).
5. Récupère ton **numéro de discussion (chat id)** : cherche **@userinfobot**, ouvre-le, envoie `/start` —
   il te renvoie un numéro (ex. `123456789`). C'est ton `TELEGRAM_CHAT_ID`.

### Étape 2 — Créer le dépôt GitHub (sur ordinateur)
1. Va sur **github.com** → crée un compte gratuit (si tu n'en as pas).
2. En haut à droite : **+** → **New repository**.
   - Name : `pokemon-precommande-watcher`
   - Coche **Public** *(important : les minutes de robot sont illimitées en public ; tes mots de passe,
     eux, restent chiffrés à part — jamais dans le code)*.
   - Clique **Create repository**.
3. Sur la page du dépôt vide : **uploading an existing file** → glisse-dépose **tout le contenu**
   de ce dossier (`monitor.py`, `sites.py`, `notify.py`, `state.json`, `requirements.txt`,
   le dossier `.github`, etc.) → **Commit changes**.

### Étape 3 — Coller tes 2 secrets Telegram
1. Dans le dépôt : **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Crée :
   - `TELEGRAM_TOKEN` → colle le jeton de BotFather.
   - `TELEGRAM_CHAT_ID` → colle ton numéro (@userinfobot).

### Étape 4 — Autoriser et tester
1. Onglet **Actions** → si demandé, clique **I understand my workflows, enable them**.
2. Choisis **« Surveillance précommandes Pokémon »** → **Run workflow** (bouton à droite) pour un test immédiat.
3. Au premier lancement, tu reçois un **message de démarrage** sur Telegram + la liste des ETB/UPC
   éventuellement **déjà en stock**. ✅ Si tu le reçois, tout marche : le robot tourne désormais tout seul.

**Test « pur » de la notification** (facultatif) : ajoute un secret `TEST_ALERT` = `1`, relance le workflow →
tu reçois un message de test. **Supprime ensuite ce secret** pour reprendre la surveillance normale.

---

## ➕ Ajouter / retirer une boutique
Ouvre `sites.py` sur GitHub (crayon ✏️ pour éditer). Chaque boutique = une ligne. Copie une ligne existante,
change le nom et l'adresse, **Commit**. C'est tout. (Explications des champs en haut du fichier.)

Si un jour tu obtiens le **lien exact d'une page de précommande**, envoie-le-moi : on peut viser cette page
en priorité pour gagner encore quelques secondes.

## ✉️ Ajouter l'email plus tard (phase 2)
Le robot est déjà prêt pour l'email. Quand tu veux l'activer, ajoute ces secrets (ex. avec un compte Gmail
+ un « mot de passe d'application ») : `EMAIL_HOST` (`smtp.gmail.com`), `EMAIL_PORT` (`587`),
`EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO`. Rien d'autre à changer.

---

## Ce que le robot fait / ne fait pas
- ✅ Détecte un **nouveau** ETB/UPC ou un **retour en stock**, avant même une mise en avant sur le site
  (lecture de la liste de produits cachée des boutiques Shopify).
- ✅ Tolérant aux orthographes et aux langues ; exclut le **japonais** (tu veux l'anglais) et indique la
  **langue probable** dans l'alerte.
- ❌ N'achète pas pour toi (règles + protections anti-robot des sites).
- ❌ Ne voit pas le **stock en magasin physique** → voir `GUIDE-MAGASINS-PHYSIQUES.md`.
- ⏱️ Réactivité ~5 min (limite du cloud gratuit). Pour 1–2 min, il faudrait le faire tourner sur ton PC.

## Fréquence & fiabilité
GitHub lance le robot via une planification « toutes les 5 min » ; en période chargée, GitHub peut
retarder de quelques minutes (normal et gratuit). La liste des exécutions est visible dans l'onglet **Actions**.
Le robot écrit un petit « battement de cœur » quotidien (`heartbeat.txt`) pour rester actif ; ainsi GitHub
ne met **pas** la surveillance en pause avant le lancement. (Si un jour l'onglet Actions affiche quand même
le workflow en pause, un simple clic **Enable workflow** le relance.)
