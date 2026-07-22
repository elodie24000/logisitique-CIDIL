# -*- coding: utf-8 -*-
"""Envoie chaque vendredi a 10h un email au gestionnaire recapitulant
toutes les commandes livrees de la semaine en cours (lundi -> vendredi)."""
import os, json, urllib.request
from datetime import date, timedelta

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
BREVO_KEY = os.environ['BREVO_API_KEY']

EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr'
EXPEDITEUR_NOM = 'CIDIL Maraîchage'
DESTINATAIRES = [
    {'email': 'comptable@cidil-asso.fr', 'name': 'Comptable CIDIL'},
    {'email': 'coordination@cidil-asso.fr', 'name': 'Coordination CIDIL'},
]
LIEN_APP = 'https://elodie24000.github.io/logisitique-CIDIL/'

H_SUPA = {'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY}


def lundi_de_cette_semaine():
    today = date.today()
    return today - timedelta(days=today.weekday())


def pluriel(qty, unite):
    u = (unite or 'kg').lower()
    if qty is None or qty <= 1:
        return u
    if u == 'botte':
        return 'bottes'
    if u in ('piece', 'pièce'):
        return 'pièces'
    return u


def get_commandes_livrees(semaine_str):
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/commandes_clients?semaine=eq.{semaine_str}&livre=eq.true'
        '&select=client_nom,jour_livraison,items,total',
        headers=H_SUPA
    )
    return json.loads(urllib.request.urlopen(req).read())


def bloc_recap_html(commandes):
    if not commandes:
        return '<p>Aucune commande livrée cette semaine.</p>'

    lignes = ''
    total_general = 0
    for c in commandes:
        items = c.get('items') or []
        if isinstance(items, str):
            items = json.loads(items)
        items_txt = ''
        for it in items:
            if it.get('dispo') is False:
                continue
            qty = it.get('quantite_reelle', it.get('quantite'))
            unite = pluriel(qty, it.get('unite'))
            items_txt += f'{it.get("nom")} : {qty} {unite}<br>'
        total = c.get('total') or 0
        total_general += total
        lignes += (
            f'<tr>'
            f'<td style="padding:10px 0;border-bottom:1px solid #e5e3dc;vertical-align:top;">'
            f'<strong>{c.get("client_nom")}</strong><br>'
            f'<span style="color:#888;font-size:12px;">{c.get("jour_livraison") or ""}</span>'
            f'</td>'
            f'<td style="padding:10px 0;border-bottom:1px solid #e5e3dc;font-size:13px;">{items_txt}</td>'
            f'<td style="padding:10px 0;border-bottom:1px solid #e5e3dc;text-align:right;font-weight:500;">'
            f'{total:.2f} €</td>'
            f'</tr>'
        )
    lignes += (
        f'<tr><td colspan="2" style="padding:10px 0;font-weight:bold;">Total de la semaine</td>'
        f'<td style="padding:10px 0;text-align:right;font-weight:bold;">{total_general:.2f} €</td></tr>'
    )
    return f'<table style="width:100%;border-collapse:collapse;font-size:14px;">{lignes}</table>'


def envoyer_email(recap_html, nb_commandes, semaine_str):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">CIDIL Maraîchage</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p>Bonjour,</p>
        <p>Voici le récapitulatif des <strong>{nb_commandes} commande(s) livrée(s)</strong> pour la semaine du {semaine_str}.</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
          {recap_html}
        </div>
        <p style="text-align:center;margin:28px 0;">
          <a href="{LIEN_APP}" style="background:#0d2818;color:#fff;padding:14px 28px;
          border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;">Ouvrir l'application</a>
        </p>
        <p style="font-size:13px;color:#888;">L'équipe CIDIL</p>
      </div>
    </div>
    """
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': DESTINATAIRES,
        'subject': f'CIDIL - Récap des commandes réalisées (semaine du {semaine_str})',
        'htmlContent': html
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=body,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json', 'accept': 'application/json'},
        method='POST'
    )
    urllib.request.urlopen(req)


semaine = lundi_de_cette_semaine().isoformat()
print(f"Semaine ciblee : {semaine}")

commandes = get_commandes_livrees(semaine)
print(f"{len(commandes)} commande(s) livree(s) trouvee(s)")

recap_html = bloc_recap_html(commandes)
envoyer_email(recap_html, len(commandes), semaine)
print("Email gestionnaire envoye")
