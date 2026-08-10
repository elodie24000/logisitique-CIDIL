# -*- coding: utf-8 -*-
"""Envoie chaque vendredi a 10h un email au gestionnaire recapitulant
toutes les commandes livrees de la semaine en cours (lundi -> vendredi)."""
import os, json, base64, urllib.request
from datetime import date, timedelta
from fpdf import FPDF

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


def get_commandes_semaine(semaine_str):
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/commandes_clients?semaine=eq.{semaine_str}'
        '&select=client_nom,jour_livraison,items,total,numero_bl,livre'
        '&order=numero_bl.asc',
        headers=H_SUPA
    )
    rows = json.loads(urllib.request.urlopen(req).read())
    livrees = [r for r in rows if r.get('livre')]
    non_livrees = [r for r in rows if not r.get('livre')]
    return livrees, non_livrees


def bloc_recap_html(commandes, titre_vide):
    if not commandes:
        return f'<p>{titre_vide}</p>'

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
        numero_bl = c.get('numero_bl')
        bl_txt = f'BL n°{numero_bl}' if numero_bl else 'Sans BL'
        lignes += (
            f'<tr>'
            f'<td style="padding:10px 0;border-bottom:1px solid #e5e3dc;vertical-align:top;white-space:nowrap;color:#0d2818;font-weight:600;">'
            f'{bl_txt}'
            f'</td>'
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
        f'<tr><td colspan="3" style="padding:10px 0;font-weight:bold;">Total de la semaine</td>'
        f'<td style="padding:10px 0;text-align:right;font-weight:bold;">{total_general:.2f} €</td></tr>'
    )
    return f'<table style="width:100%;border-collapse:collapse;font-size:14px;">{lignes}</table>'


def build_pdf(livrees, non_livrees, semaine_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Recapitulatif des BL', ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 8, f'Semaine du {semaine_str}', ln=1)
    pdf.ln(4)

    def section(titre, commandes):
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(0, 8, titre, ln=1)
        pdf.ln(1)
        if not commandes:
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(0, 6, '  Aucune', ln=1)
            pdf.ln(2)
            return 0
        sous_total = 0
        for c in commandes:
            items = c.get('items') or []
            if isinstance(items, str):
                items = json.loads(items)
            numero_bl = c.get('numero_bl')
            bl_txt = f'BL n{numero_bl}' if numero_bl else 'Sans BL'

            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 7, f'{bl_txt} - {c.get("client_nom")}', ln=1)
            pdf.set_font('Helvetica', '', 9)
            for it in items:
                if it.get('dispo') is False:
                    pdf.cell(0, 5, f'  {it.get("nom")} : non disponible', ln=1)
                    continue
                qty = it.get('quantite_reelle', it.get('quantite'))
                unite = pluriel(qty, it.get('unite'))
                pdf.cell(0, 5, f'  {it.get("nom")} : {qty} {unite}', ln=1)
            total = c.get('total') or 0
            sous_total += total
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(0, 6, f'  Total : {total:.2f} EUR', ln=1)
            pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 7, f'Sous-total {titre} : {sous_total:.2f} EUR', ln=1)
        pdf.ln(4)
        return sous_total

    total_livrees = section('Commandes livrees', livrees)
    total_non_livrees = section('Commandes non confirmees livrees', non_livrees)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, f'Total general : {(total_livrees + total_non_livrees):.2f} EUR', ln=1)

    out = pdf.output(dest='S')
    return bytes(out) if not isinstance(out, (bytes, bytearray)) else bytes(out)


def envoyer_email(html_livrees, html_non_livrees, nb_livrees, nb_non_livrees, semaine_str, pdf_bytes):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">CIDIL Maraîchage</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p>Bonjour,</p>
        <p>Voici le récapitulatif des commandes pour la semaine du {semaine_str} (ce récapitulatif regroupe les BL déjà envoyés, ce n'est pas un BL en soi).</p>

        <p style="font-weight:bold;margin:20px 0 8px;">✅ Commandes livrées ({nb_livrees})</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:0 0 18px;">
          {html_livrees}
        </div>

        <p style="font-weight:bold;margin:20px 0 8px;">⏳ Commandes non confirmées livrées ({nb_non_livrees})</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:0 0 18px;">
          {html_non_livrees}
        </div>

        <p style="text-align:center;margin:28px 0;">
          <a href="{LIEN_APP}" style="background:#0d2818;color:#fff;padding:14px 28px;
          border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;">Ouvrir l'application</a>
        </p>
        <p style="font-size:13px;color:#888;">L'équipe CIDIL</p>
      </div>
    </div>
    """
    pdf_b64 = base64.b64encode(pdf_bytes).decode('ascii')
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': DESTINATAIRES,
        'subject': f'CIDIL - Récap des commandes (semaine du {semaine_str})',
        'htmlContent': html,
        'attachment': [{'content': pdf_b64, 'name': f'Recap_BL_{semaine_str}.pdf'}]
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

livrees, non_livrees = get_commandes_semaine(semaine)
print(f"{len(livrees)} commande(s) livree(s), {len(non_livrees)} commande(s) non confirmee(s) livree(s)")

html_livrees = bloc_recap_html(livrees, 'Aucune commande livrée cette semaine.')
html_non_livrees = bloc_recap_html(non_livrees, 'Aucune commande en attente cette semaine.')
pdf_bytes = build_pdf(livrees, non_livrees, semaine)
envoyer_email(html_livrees, html_non_livrees, len(livrees), len(non_livrees), semaine, pdf_bytes)
print("Email gestionnaire envoye")
