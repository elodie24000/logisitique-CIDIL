# -*- coding: utf-8 -*-
"""Alerte l'encadrant technique le jeudi si la liste des legumes de la semaine
suivante (celle qui part par email vendredi 10h) n'a pas encore ete saisie :
un email + une notification push (abonnes 'encadrant' uniquement)."""
import os, json, urllib.request
from datetime import date, timedelta

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
BREVO_KEY = os.environ['BREVO_API_KEY']
VAPID_PRIVATE = os.environ['VAPID_PRIVATE_KEY']
VAPID_CLAIMS = {'sub': 'mailto:plassin.elodie24@gmail.com'}

EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr'
EXPEDITEUR_NOM = 'CIDIL Maraîchage'
DESTINATAIRE_ETI = {'email': 'eti.maraichage1@cidil-asso.fr', 'name': 'Encadrant technique'}

H_SUPA = {'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY}


def prochain_lundi():
    today = date.today()
    delta = (7 - today.weekday()) % 7
    delta = delta if delta != 0 else 7
    return today + timedelta(days=delta)


def legumes_deja_saisis(semaine_str):
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/legumes?semaine=eq.{semaine_str}&select=id&limit=1',
        headers=H_SUPA
    )
    rows = json.loads(urllib.request.urlopen(req).read())
    return bool(rows)


def envoyer_email():
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#c0392b;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">⚠ Légumes de la semaine à saisir</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p>La liste des légumes de la semaine prochaine n'est pas encore saisie dans l'application.</p>
        <p><strong>Pense à la mettre à jour avant demain (vendredi) 10h</strong>, heure à laquelle elle part automatiquement par email à tous les clients.</p>
      </div>
    </div>
    """
    body = json.dumps({
        'sender': {'email': EXPEDITEUR_EMAIL, 'name': EXPEDITEUR_NOM},
        'to': [DESTINATAIRE_ETI],
        'subject': "CIDIL - Pense a mettre a jour la liste des legumes avant vendredi 10h",
        'htmlContent': html
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=body,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json', 'accept': 'application/json'},
        method='POST'
    )
    urllib.request.urlopen(req)


def envoyer_push():
    from pywebpush import webpush, WebPushException
    req = urllib.request.Request(
        f'{SUPA_URL}/rest/v1/push_subscriptions?role=eq.encadrant&select=id,subscription',
        headers=H_SUPA
    )
    subs = json.loads(urllib.request.urlopen(req).read())
    payload = json.dumps({
        'title': 'CIDIL Maraîchage 🥕',
        'body': "Pense à mettre à jour la liste des légumes avant demain 10h !",
        'url': 'https://elodie24000.github.io/logisitique-CIDIL/'
    })
    ok = 0
    for s in subs:
        try:
            info = json.loads(s['subscription'])
            webpush(subscription_info=info, data=payload,
                    vapid_private_key=VAPID_PRIVATE, vapid_claims=dict(VAPID_CLAIMS))
            ok += 1
        except WebPushException as e:
            print(f"Echec push {s['id']}: {e}")
        except Exception as e:
            print(f"Erreur push {s['id']}: {e}")
    print(f"{ok}/{len(subs)} notification(s) push envoyee(s) a l'encadrant")


semaine = prochain_lundi().isoformat()
print(f"Semaine ciblee : {semaine}")

if legumes_deja_saisis(semaine):
    print("Liste deja saisie pour la semaine prochaine, pas d'alerte necessaire")
else:
    print("Liste pas encore saisie, envoi de l'alerte")
    envoyer_email()
    print("Email envoye a l'encadrant technique")
    envoyer_push()
