# -*- coding: utf-8 -*-
"""Envoie un email de rappel a tous les clients ayant un email, le matin ou
les commandes vont fermer (lundi 8h pour la livraison de mardi, mercredi 8h
pour la livraison de jeudi)."""
import os, json, urllib.request

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
BREVO_KEY = os.environ['BREVO_API_KEY']
JOUR_LIVRAISON = os.environ['JOUR_LIVRAISON']  # 'mardi' ou 'jeudi'

EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr'
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
        <p><strong>Dernière chance</strong> pour passer votre commande en vue de la livraison de <strong>{JOUR_LIVRAISON}</strong> !</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
          <p style="margin:0;font-weight:bold;">⏰ Les commandes ferment aujourd'hui à 12h.</p>
        </div>
        <p style="text-align:center;margin:28px 0;">
          <a href="{LIEN_COMMANDE}" style="background:#0d2818;color:#fff;padding:14px 28px;
          border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;">Passer ma commande</a>
        </p>
        <p style="font-size:13px;color:#888;">À bientôt,<br>L'équipe CIDIL</p>
      </div>
    </div>
    """
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': [{'email': destinataire_email, 'name': destinataire_nom}],
        'subject': f'CIDIL - Dernière chance pour commander (livraison {JOUR_LIVRAISON})',
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
