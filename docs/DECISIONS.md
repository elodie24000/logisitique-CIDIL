# Décisions et pièges connus

Le *pourquoi* des choix faits sur l'appli. Si un comportement semble être un bug, vérifie ici qu'il n'est pas voulu.
Les dates renvoient à l'historique git (`git log --since=AAAA-MM-JJ`).

## Commandes et calendrier

- **Clôture à 9h** (depuis le 15/10/2026, avant 12h) : lundi 9h pour mardi, mardi 9h pour mercredi, mercredi 9h pour jeudi.
  Boutique, Labo et clients `sans_delai` n'ont pas de délai.
- **Deux bascules de semaine différentes** (23/09/2026) : l'écran client passe à la semaine suivante dès la clôture
  du mercredi ; les écrans équipe gardent la semaine en cours jusqu'au **vendredi 14h**, sinon les commandes encore
  à livrer partaient dans l'historique en lecture seule. Encadré « Déjà commandé pour la semaine prochaine » entre les deux.
- **Jours imposés par client** (`clients.jours_livraison`) : Le Patio = mardi (trop loin pour le jeudi) ;
  ferme charentaise = mercredi (03/11/2026). Un jour imposé est pris dans toute la semaine, pas seulement mardi/jeudi.
- **Plusieurs commandes par client et par semaine** (03/11/2026) : chaque commande a sa carte. Bug corrigé : l'une des
  deux disparaissait quand elles étaient rangées par client.
- **Fiche commande encadrant** (19/11/2026) : quand les créneaux de la semaine affichée sont fermés, bouton
  « Passer à la semaine prochaine » (avant : aucun jour proposé, blocage silencieux).
- **Historique** limité aux 2 semaines précédentes.
- **Légumes triés de A à Z** (03/11/2026), à la demande des encadrants ; la famille reste en base pour les icônes.
- **Reprise automatique** de la liste de légumes de la semaine précédente si l'encadrante ne l'a pas mise à jour,
  avec une alerte le jeudi pour qu'elle y pense.

## Livraison

- **Livreur** (09/09/2026) : page Tournée = commandes prêtes à livrer (hors retrait sur place et clients internes),
  signature tactile = preuve de livraison, bon de livraison PDF envoyé par e-mail (`send-delivery-signed-email`).
  Les livraisons internes / retrait sont marquées livrées automatiquement.
- **Sans réseau** (03/11/2026) : signature et souci gardés sur le téléphone puis envoyés au retour du réseau.
- Une annonce de stock acceptée par Boutique/Labo peut devenir une commande livrée par le livreur (`force_livreur`).

## Rappels, e-mails, notifications

- **Rappels à l'heure exacte par Supabase** (19/10/2026) : GitHub lançait les envois planifiés avec plusieurs heures
  de retard (rappel « clôture 9h » reçu à 12h38). La fonction `rappels-clients` tourne toutes les 10 min via `pg_cron`
  et n'envoie qu'une fois : lundi/mardi/mercredi 7h « dernière chance » selon les jours du client, vendredi 10h
  « légumes disponibles », chaque jour 9h30 veille (site, rappels, e-mails en échec). Les workflows GitHub
  correspondants restent en déclenchement manuel de secours.
- **Récap du vendredi** au gestionnaire : premier créneau après 14h, une seule fois (repère dans `activity_log`).
- **Alertes équipe** : push sur le téléphone de l'encadrante à chaque nouvelle commande / nouveau client
  (`notifier-equipe`, déclenché par des triggers en base). On vérifie le vrai abonnement push du téléphone,
  pas un repère local (certains Android le perdent).
- **Clé VAPID** : régénérée le 23/09/2026 ; la privée est dans le Vault Supabase et les secrets GitHub, jamais dans le code.

## Sécurité

- **Codes PIN** vérifiés côté Supabase (`verifier_pin`), blocage 10 min après 10 erreurs (01/10/2026). Ils ne doivent
  jamais réapparaître dans la page.

## Affichage

- **Icônes de légumes** : les émojis récents ne s'affichent pas partout, mais remplacer par des ronds abstraits a été
  rejeté (on ne reconnaissait plus les légumes). Solution retenue : dessins maison (radis, cosses, navet, rutabaga,
  topinambour, pâtisson, artichaut), repli sur l'icône de la famille du légume.
- Carte légume : texte non sélectionnable, sinon un appui long ouvre la recherche Google d'Android.
- Style « jardin » (fond clair, vert tendre) depuis le 15/10/2026 ; textes et boutons agrandis pour le terrain.

## Mise à jour de l'appli sur les téléphones

- Service worker « réseau d'abord » (03/11/2026) : la dernière version est toujours demandée au serveur.
- **Retour sur l'appli après l'arrière-plan** (19/11/2026) : rechargement automatique si une nouvelle version est
  en ligne (bandeau si une saisie est en cours), sinon rechargement des données de la page. La plupart des
  « ça ne marche pas » venaient d'une appli restée ouverte des heures avec une page ou une semaine périmée.
