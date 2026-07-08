# -*- coding: utf-8 -*-
"""Envoie une notification push de rappel a tous les abonnes (vendredi)."""
import os, json, urllib.request
from pywebpush import webpush, WebPushException

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
VAPID_PRIVATE = os.environ['VAPID_PRIVATE_KEY']
VAPID_CLAIMS = {'sub': 'mailto:plassin.elodie24@gmail.com'}

H = {'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY}

def get_subs():
    req = urllib.request.Request(f'{SUPA_URL}/rest/v1/push_subscriptions?select=id,subscription', headers=H)
    return json.loads(urllib.request.urlopen(req).read())

def delete_sub(sid):
    req = urllib.request.Request(f'{SUPA_URL}/rest/v1/push_subscriptions?id=eq.{sid}', headers=H, method='DELETE')
    try: urllib.request.urlopen(req)
    except Exception: pass

payload = json.dumps({
    'title': 'CIDIL Maraîchage \U0001F4E2',
    'body': "Derniere ligne droite ! Pensez a passer votre commande avant la fin de la semaine.",
    'url': 'https://elodie24000.github.io/logisitique-CIDIL/?commande',
    'tag': 'cidil-rappel-vendredi'
})

subs = get_subs()
print(f"{len(subs)} abonne(s)")
ok = 0
for s in subs:
    try:
        info = json.loads(s['subscription'])
        webpush(subscription_info=info, data=payload,
                vapid_private_key=VAPID_PRIVATE, vapid_claims=dict(VAPID_CLAIMS))
        ok += 1
    except WebPushException as e:
        code = getattr(e.response, 'status_code', None)
        print(f"Echec {s['id']} (code {code})")
        if code in (404, 410):
            delete_sub(s['id'])
    except Exception as e:
        print(f"Erreur {s['id']}: {e}")

print(f"{ok} notification(s) envoyee(s)")
