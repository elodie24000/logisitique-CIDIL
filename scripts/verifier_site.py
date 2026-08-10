# -*- coding: utf-8 -*-
"""Verifie chaque jour que le site est bien accessible (pas d'erreur 404 /
site coupe). Envoie un email d'alerte a la gestionnaire si ce n'est pas le cas."""
import os, json, urllib.request, urllib.error

SITE_URL = 'https://elodie24000.github.io/logisitique-CIDIL/'
BREVO_KEY = os.environ['BREVO_API_KEY']

EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr'
EXPEDITEUR_NOM = 'CIDIL Maraîchage'
DESTINATAIRE = {'email': 'plassin.elodie24@gmail.com', 'name': 'Elodie'}


def verifier():
    try:
        req = urllib.request.Request(SITE_URL, method='GET')
        res = urllib.request.urlopen(req, timeout=15)
        return res.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f'ERREUR: {e}'


def envoyer_alerte(statut):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#c0392b;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">⚠ Site CIDIL inaccessible</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p>Le site <strong>{SITE_URL}</strong> ne répond pas correctement.</p>
        <p>Code retourné : <strong>{statut}</strong></p>
        <p>Les clients ne peuvent probablement plus passer commande. Vérifie l'onglet
        "Settings → Pages" du dépôt GitHub, ou demande à Claude de vérifier.</p>
      </div>
    </div>
    """
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': [DESTINATAIRE],
        'subject': '⚠ ALERTE - Le site CIDIL est inaccessible',
        'htmlContent': html
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email', data=body,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json', 'accept': 'application/json'},
        method='POST'
    )
    urllib.request.urlopen(req)


statut = verifier()
print(f"Statut du site : {statut}")
if statut != 200:
    envoyer_alerte(statut)
    print("Alerte envoyee.")
else:
    print("Site OK, pas d'alerte necessaire.")
