# Journal des dépannages

Une ligne par intervention, la plus récente en bas. Format :
`AAAA-MM-JJ | signalé par | problème vécu | cause | correctif (ou « transmis à Élodie »)`

2026-11-19 | Atika | impossible de créer une commande pour Les Papilles, aucun jour proposé | fiche commande calée sur la semaine affichée, créneaux déjà fermés | bouton « Passer à la semaine prochaine »
2026-11-19 | client Latoti | « choisissez un jour » sans jour sélectionnable sur mobile | semaine de commande figée pendant que l'appli dormait en arrière-plan | recalcul au retour sur l'appli et avant l'envoi
2026-11-19 | Élodie | Atika doit sans cesse rafraîchir l'appli | appli ouverte des heures en arrière-plan avec l'ancienne version et les anciennes données | rechargement automatique au retour (version + données de toutes les pages)
2026-11-19 | Élodie | distinguer Atika et Amélie (même PIN encadrant) | rien ne les différenciait | « Qui êtes-vous ? » à la 1re connexion, prénom dans le journal d'activité et l'abonnement aux notifications
2026-11-19 | Élodie | retirer Amélie Blanquart (ACI ARU Trois-Palis) des clients : c'est l'encadrante | déjà absente de la base | retirée de la liste de secours dans index.html
2026-11-20 | Atika (via Élodie) | rien n'a changé après « Qui êtes-vous ? », pas d'encart « Déclarer un problème » | ce bouton n'a jamais été construit (reporté le 19/11) ; au passage : téléphones des encadrantes inscrits 2 fois aux notifications (deux étiquetages en parallèle) | verrou sur l'étiquetage + doublons supprimés en base ; bouton : décision d'Élodie
2026-11-20 | Élodie | construire le bouton « Déclarer un problème » décidé le 19/11 | — | bouton 🛟 + table signalements + e-mail à Élodie (fonction signalement-recu) ; test d'envoi réussi
2026-11-20 | Élodie | encadré « Déclarer un problème » sous « Prévenir Boutique / Labo », tutoiement, Vocal / Envoyer / Annuler | — | encadré sur la page Légumes des encadrantes (bouton flottant gardé pour livreur, Boutique, Labo)
2026-11-22 | Élodie | brancher l'encadré sur Claude (chat Atika/Amélie ↔ Claude, abonnement Pro) | — | fonction signalement-github + table signalement_messages + workflow claude-signalement.yml + conversation affichée dans l'encadré
2026-11-22 | Élodie | l'accès à Claude doit être réservé à Atika et Amélie | le bouton flottant l'ouvrait aussi au livreur (ajout de ma part, jamais demandé) | bouton retiré + verrou en base (RLS) : seules les encadrantes Atika/Amélie peuvent écrire
2026-11-26 | Atika (validé par Élodie) | le livreur ne sait pas quel jour livrer chaque commande | l'écran Tournée n'affichait pas le jour de livraison pourtant enregistré avec la commande | ligne « 🚚 À livrer : Jeudi 3 déc. » en haut de chaque fiche du livreur (« jour libre » pour Intermarché / clients internes)
