# CIDIL Maraîchage — cadre pour Claude

Lis ce fichier en entier avant toute intervention. Il est court exprès : chaque ligne compte.
Pour le *pourquoi* des choix passés : `docs/DECISIONS.md` (à lire avant de toucher à une règle métier).
Pour l'historique des dépannages : `docs/JOURNAL.md` (ajoute-y une ligne à chaque intervention).

## L'application en bref

Appli web (PWA installée sur téléphone) du chantier d'insertion maraîchage du CIDIL (Montbron, Charente) :
vente de légumes en demi-gros à des cantines, commerces, fermes, plus Boutique et Labo internes.
Tout est en **français** : textes de l'appli, commentaires, messages de commit.

- **Hébergement** : GitHub Pages, branche `main`, URL `https://elodie24000.github.io/logisitique-CIDIL/`.
  Un merge sur `main` = en ligne en 1–2 minutes. Pas d'étape de build.
- **Base de données** : Supabase (projet `ulvrwtwxzhlrplvbcsrd`), appelée en REST direct depuis la page
  (`sbGet / sbPost / sbPatch / sbDelete`). Clé publiable seulement dans le code ; les secrets n'y vont **jamais**.
- **E-mails** : Brevo. **Notifications push** : Web Push (clé VAPID publique dans `index.html`, privée dans les secrets / Vault).
- **Tâches planifiées** : `pg_cron` + fonction Edge `rappels-clients` pour tout ce qui doit partir à l'heure
  (GitHub Actions part avec des heures de retard). Les workflows GitHub restent pour le reste et en secours manuel.

## Les rôles (écran d'accueil → code PIN vérifié par Supabase `verifier_pin`)

| Rôle | Onglets | Qui |
|---|---|---|
| `encadrant` | Légumes, Commandes, Clients | Les deux encadrantes techniques, **Atika** et **Amélie** (même PIN ; « Qui êtes-vous ? » à la 1re connexion, prénom gardé par le téléphone et enregistré dans la colonne `qui` de `activity_log` et `push_subscriptions`) |
| `gestionnaire` | Récap, Clients, Tarifs, Commandes, Bilan | Élodie (propriétaire du projet) |
| `livreur` | Tournée (signature, souci, mode hors réseau) | Le livreur |
| `boutique`, `labo` | Commande interne + annonces de stock | Clients internes |
| `client` (sans PIN) | Écran « Commander mes légumes » (`?commande`) | Clients externes |

## Carte des fichiers

- `index.html` (~4 500 lignes) contient **toute** l'appli. Ne le lis jamais en entier : cherche le repère
  de section avec `grep -n "══════" index.html`, puis lis seulement la partie utile.
  - lignes 13–663 : CSS · 667–1310 : HTML (login, PIN, app, modales, page commande client)
  - à partir de 1311 : JavaScript, sections dans cet ordre :
    `SUPABASE` · `DATA` (rôles, jours de livraison, liste de secours des clients) · `GESTION DU STOCK` ·
    `JOURNAL D'ACTIVITÉ` · `AUTH` · `NAV` (`NAV_CONFIG`, `initPage`) · `SEMAINE` (`semaineCommandeActive`) ·
    `TARIFS` · `CATALOGUE` · `LÉGUMES` (`emojiLegume`, dessins des légumes) · `COMMANDES` (`openOrderModal`, `saveOrder`) ·
    `TOURNÉE (livreur)` · `SIGNATURE` · `AJUSTER LA COMMANDE` · `RÉCAP` · `CLIENTS` · `NOTIFICATIONS PUSH` ·
    `ANNONCES STOCK` · `PAGE COMMANDE CLIENT` (`initCommandeClient`, `envoyerCommandeClient`) ·
    `TOURNÉE SANS RÉSEAU` · `MISE À JOUR AUTOMATIQUE` · `L'APPLI SE MET À JOUR TOUTE SEULE` · `SOUCI DE LIVRAISON` ·
    `REPRENDRE LA DERNIÈRE COMMANDE` · `BILAN`
- `sw.js` : service worker (réseau d'abord, cache en secours, push). **Incrémente `CACHE = 'cidil-vNN'`
  à chaque modification de `index.html`.**
- `commande.html` : ancienne page, plus référencée nulle part. Ne pas la modifier.
- `supabase/functions/*` : fonctions Edge (copie du code déployé ; modifier ici **ne déploie rien**).
- `supabase/migrations/*` : SQL déjà appliqué en base.
- `scripts/*.py` + `.github/workflows/*` : e-mails/push planifiés, synchro des prix (SharePoint, RNM), vérification du site.

Tables Supabase utilisées par la page : `clients`, `catalogue`, `legumes` (légumes de la semaine + `kg_dispo`),
`commandes_clients`, `activity_log`, `annonces_stock`, `annonces_stock_reponses`, `push_subscriptions`, `signalements`.

**Déclarer un problème** (section `DÉCLARER UN PROBLÈME`) : encadré sur la page Légumes des encadrantes, sous
« Prévenir Boutique / Labo » (« Atika, décris le bug… », boutons Vocal / Envoyer / Annuler = effacer).
**Réservé à Atika et Amélie** (décision d'Élodie du 22/11) : rien pour livreur, Boutique, Labo, gestionnaire ;
la base (RLS) refuse tout signalement ou message dont le rôle n'est pas `encadrant` avec `qui` = Atika ou Amélie.
le message (dicté ou écrit) va dans `signalements` (qui, rôle, page, texte, contexte technique, statut
`nouveau` → `transmis`) ; la fonction Edge `signalement-recu` prévient Élodie par e-mail. Canal séparé des alertes équipe.

**Claude de dépannage** (circuit complet) : la fonction Edge `signalement-github` ouvre une fiche GitHub (repère
`<!-- signalement-app id=N -->`) et y recopie chaque réponse de l'équipe (table `signalement_messages`) ;
le workflow `.github/workflows/claude-signalement.yml` lance Claude (abonnement Pro d'Élodie, secret
`CLAUDE_CODE_OAUTH_TOKEN`) qui ne peut modifier que `index.html`, `sw.js`, `docs/JOURNAL.md`, sans terminal ;
`scripts/signalement_conversation.py` pose un tag `avant-signalement-…`, vérifie que le JS compile, publie sur
`main` (sinon branche `signalement-N` pour Élodie), écrit la réponse de Claude dans l'encadré (« Tes derniers
échanges ») et envoie le récap par e-mail à Élodie. Statuts : transmis → corrige | repondu | pour_elodie.

## Règles métier à ne JAMAIS changer sans l'accord explicite d'Élodie

- Clôture des commandes à **9h** : lundi pour mardi, mardi pour mercredi, mercredi pour jeudi
  (`joursDisponiblesPourClient`). Pas de délai pour Boutique/Labo ni pour les clients `sans_delai`.
- Jours de livraison externes : mardi et jeudi ; jours imposés par client via `clients.jours_livraison`
  (Le Patio = mardi, ferme charentaise = mercredi). Exception : ouvrir un jour de livraison pour **un** client
  est permis aux encadrantes (voir plus bas).
- Bascule de semaine : écran client = à la clôture du mercredi 9h ; écrans équipe = vendredi 14h.
- Prix, tarifs, stock (`kg_dispo`), destinataires des e-mails, contenu des bons de livraison.
- Droits des rôles, codes PIN, tri alphabétique des légumes (demandé par les encadrants).

## Qui demande quoi : ce que tu as le droit de faire

Chaque demande précise qui l'envoie. **En cas de doute sur l'auteur, applique les règles « encadrantes ».**

**Demande d'Atika ou d'Amélie, les encadrantes techniques** — elles ont **plein pouvoir** (décision d'Élodie du 27/11),
tu fais toi-même, sans attendre Élodie :
- un bug (bouton qui ne marche pas, blocage, écran vide, erreur affichée, donnée qui n'apparaît pas) ;
- tout ajustement d'affichage ou de texte (libellé, taille, faute, ordre d'un bouton) ;
- **améliorer l'interface du livreur** (Tournée, fiches, signature, informations affichées) ;
- **une case ou un encadré commentaire pour un client** (ex. étendre à un autre client l'encadré créé pour
  Intermarché : `clientAvecCommentaire`, la colonne `commandes_clients.commentaire` existe déjà) ;
- **ouvrir un nouveau jour de livraison pour un client** donné (sans toucher aux jours ni aux heures de clôture
  des autres clients) ;
- plus largement, une petite amélioration pratique de leurs écrans ou de celui du livreur, dans le même esprit.
Élodie reste informée de tout : le récap de chaque intervention lui est envoyé par e-mail.

Tu **ne fais pas**, et tu transmets à Élodie avec ton analyse (elle veut le savoir) :
- un incident sur les données : client ou commande supprimé(e) ou disparu(e), commande perdue, doublons de fiches ;
- toute suppression ou modification de données en base, tout changement de structure (tables, colonnes, RLS) ;
- les autres règles métier listées plus haut : heures de clôture, bascule de semaine, prix, tarifs, stock,
  bons de livraison, destinataires des e-mails, tri des légumes ;
- tout changement des e-mails, notifications, workflows ou fonctions Edge ;
- tout ce qui touche aux secrets, aux PIN ou aux droits ;
- une grosse nouveauté qui change la façon de travailler de toute l'équipe ou des clients.
Si une demande permise demande aussi un changement en base (nouvelle colonne, donnée à modifier), fais la partie
écran si elle tient seule, sinon transmets à Élodie en expliquant ce qui manque.
Si la demande ressemble à un bug mais que la cause est un choix voulu (voir `docs/DECISIONS.md`), ne le défais pas :
explique-le simplement et transmets.

**Demande d'Élodie** : droits complets, dans le respect de la procédure ci-dessous.

## Procédure obligatoire pour chaque intervention

1. Lis `docs/DECISIONS.md` si le problème touche une règle métier, et les dernières lignes de `docs/JOURNAL.md`.
2. Trouve la cause **avant** de modifier quoi que ce soit (souvent : appli restée ouverte en arrière-plan,
   semaine figée, cache). Ne corrige pas « au hasard ».
3. Correctif **minimal** : touche le moins de lignes possible, ne refais pas ce qui marche, pas de « nettoyage » au passage.
4. Incrémente le cache dans `sw.js`.
5. Teste dans Chromium (Playwright est installé) : la page se charge sans erreur JS, et le cas signalé est réglé.
6. Commit en français, qui explique le problème vécu et la cause (voir l'historique git pour le ton).
7. Ajoute une ligne à `docs/JOURNAL.md`.
8. Réponds en termes simples, sans jargon : ce qui n'allait pas, ce qui est corrigé, et s'il faut fermer et rouvrir l'appli.

Si tu ne trouves pas la cause après une recherche raisonnable, **arrête-toi** et transmets ce que tu as trouvé
plutôt que de tenter des modifications.

## Pièges connus

- Les téléphones gardent l'appli ouverte des heures en arrière-plan : toute valeur calculée « à l'ouverture »
  (semaine, jours disponibles, version) peut être périmée au retour. Voir `rafraichirSemaineCommandeClient`
  et la section `L'APPLI SE MET À JOUR TOUTE SEULE`.
- `state.semaine` (semaine affichée côté équipe) ≠ `semaineCommandeActive()` (semaine de commande client).
- Plusieurs commandes d'un même client la même semaine sont possibles : ne jamais indexer les commandes par client seul.
- Émojis récents (🫜, 🫛…) non affichés sur beaucoup de téléphones : les légumes sans émoji fiable ont un dessin maison.
- iPhone : les notifications ne marchent que si l'appli est ouverte depuis l'icône de l'écran d'accueil.
- Les heures sont celles de **Paris** (été/hiver) ; GitHub Actions planifié part avec plusieurs heures de retard.
