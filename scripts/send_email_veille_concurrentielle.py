# -*- coding: utf-8 -*-
"""Envoie par email le recapitulatif mensuel de veille concurrentielle (redige
par une routine automatique Claude) a Elodie. Declenche via workflow_dispatch,
jamais sur un planning fixe (le declenchement mensuel est gere cote routine)."""
import os, json, urllib.request

BREVO_KEY = os.environ['BREVO_API_KEY']
SUJET = os.environ['SUJET']
CONTENU_HTML = os.environ['CONTENU_HTML']

EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr'
EXPEDITEUR_NOM = 'CIDIL Maraîchage'
DESTINATAIRE = {'email': 'plassin.elodie24@gmail.com', 'name': 'Elodie'}


def envoyer_email():
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">Veille concurrentielle CIDIL</h1>
        <p style="color:#c9e5d2;font-size:13px;margin:4px 0 0;">Récapitulatif mensuel</p>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        {CONTENU_HTML}
      </div>
    </div>
    """
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': [DESTINATAIRE],
        'subject': SUJET,
        'htmlContent': html
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=body,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json', 'accept': 'application/json'},
        method='POST'
    )
    urllib.request.urlopen(req)


envoyer_email()
print("Email de veille concurrentielle envoye")
