# -*- coding: utf-8 -*-
"""Envoie un email de rappel chaque vendredi a tous les clients ayant un email."""
import os, json, urllib.request

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
BREVO_KEY = os.environ['BREVO_API_KEY']

EXPEDITEUR_EMAIL = 'contact@cidil.fr'   # a adapter a l'adresse validee sur Brevo
EXPEDITEUR_NOM = 'CIDIL Maraîchage'
LIEN_COMMANDE = 'https://elodie24000.github.io/logisitique-CIDIL/?commande'

H_SUPA = {'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY}

def get_clients_avec_email():
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/clients?select=nom,email&email=not.is.null&cat=neq.Interne',
        headers=H_SUPA
    )
    return json.loads(urllib.request.urlopen(req).read())

def envoyer_email(destinataire_email, destinataire_nom):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">CIDIL Maraîchage</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p>Bonjour {destinataire_nom},</p>
        <p>Derniere ligne droite ! N'oubliez pas de passer votre commande de legumes
        pour la semaine avant la fin de la journee.</p>
        <p style="text-align:center;margin:28px 0;">
          <a href="{LIEN_COMMANDE}" style="background:#0d2818;color:#fff;padding:14px 28px;
          border-radius:10px;text-decoration:none;font-weight:bold;">Passer ma commande</a>
        </p>
        <p style="font-size:13px;color:#888;">A bientot,<br>L'equipe CIDIL</p>
      </div>
    </div>
    """
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': [{'email': destinataire_email, 'name': destinataire_nom}],
        'subject': 'CIDIL - Derniere ligne droite pour votre commande de legumes',
        'htmlContent': html
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=body,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json', 'accept': 'application/json'},
        method='POST'
    )
    urllib.request.urlopen(req)

clients = get_clients_avec_email()
print(f"{len(clients)} client(s) avec email")
ok = 0
for c in clients:
    try:
        envoyer_email(c['email'], c['nom'])
        ok += 1
    except Exception as e:
        print(f"Erreur envoi a {c['email']}: {e}")

print(f"{ok} email(s) envoye(s)")
