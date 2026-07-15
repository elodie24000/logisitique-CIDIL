# -*- coding: utf-8 -*-
"""Envoie un email de rappel chaque vendredi a tous les clients ayant un email,
avec la vraie liste des legumes de la semaine a venir (deja saisie dans l'appli)."""
import os, json, urllib.request
from datetime import date, timedelta

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
BREVO_KEY = os.environ['BREVO_API_KEY']

EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr'
EXPEDITEUR_NOM = 'CIDIL Maraîchage'
LIEN_COMMANDE = 'https://elodie24000.github.io/logisitique-CIDIL/?commande'

H_SUPA = {'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY}

def prochain_lundi():
    today = date.today()
    delta = (7 - today.weekday()) % 7
    delta = delta if delta != 0 else 7
    return today + timedelta(days=delta)

def pluriel(qty, unite):
    u = (unite or 'kg').lower()
    if qty is None or qty <= 1:
        return u
    if u == 'botte':
        return 'bottes'
    if u in ('piece', 'pièce'):
        return 'pièces'
    return u

def get_legumes_semaine(semaine_str):
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/legumes?semaine=eq.{semaine_str}&order=nom.asc'
        '&select=nom,kg_dispo,prix_kg,unite',
        headers=H_SUPA
    )
    return json.loads(urllib.request.urlopen(req).read())

def get_clients_avec_email():
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/clients?select=nom,email&email=not.is.null&cat=neq.Interne',
        headers=H_SUPA
    )
    return json.loads(urllib.request.urlopen(req).read())

def bloc_legumes_html(legumes):
    if not legumes:
        return '<p>La liste des légumes de la semaine sera bientôt disponible dans l\'application.</p>'
    lignes = ''
    for l in legumes:
        qty = l.get('kg_dispo')
        unite = pluriel(qty, l.get('unite'))
        prix = l.get('prix_kg')
        prix_txt = f" · {prix:.2f} €/{(l.get('unite') or 'kg')}" if prix else ''
        lignes += (
            f'<tr>'
            f'<td style="padding:6px 0;border-bottom:1px solid #e5e3dc;">{l["nom"]}</td>'
            f'<td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-align:right;color:#555;">'
            f'{qty} {unite}{prix_txt}</td>'
            f'</tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;font-size:14px;">{lignes}</table>'

def envoyer_email(destinataire_email, destinataire_nom, legumes_html):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">CIDIL Maraîchage</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p>Bonjour {destinataire_nom},</p>
        <p>Voici les légumes disponibles pour la semaine à venir. Pensez à passer votre commande !</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
          {legumes_html}
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
        'subject': 'CIDIL - Les légumes de la semaine sont disponibles',
        'htmlContent': html
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=body,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json', 'accept': 'application/json'},
        method='POST'
    )
    urllib.request.urlopen(req)

semaine = prochain_lundi().isoformat()
print(f"Semaine ciblee : {semaine}")

legumes = get_legumes_semaine(semaine)
print(f"{len(legumes)} legume(s) trouve(s) pour cette semaine")
legumes_html = bloc_legumes_html(legumes)

clients = get_clients_avec_email()
print(f"{len(clients)} client(s) avec email")
ok = 0
for c in clients:
    try:
        envoyer_email(c['email'], c['nom'], legumes_html)
        ok += 1
    except Exception as e:
        print(f"Erreur envoi a {c['email']}: {e}")

print(f"{ok} email(s) envoye(s)")
