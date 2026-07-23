# -*- coding: utf-8 -*-
"""Synchronise les prix du catalogue depuis le fichier SharePoint
"Prix vente legumes - CIDIL - 2025.xlsx", onglet "MISE A JOUR " (colonnes
A=libelle, B=variete, C=unite, BE=prix moyen HT bio).

La correspondance entre les lignes du fichier et les fiches de l'app a ete
validee manuellement avec la gestionnaire (regles ci-dessous). Les produits
absents du fichier ou sans prix renseigne sont ignores."""
import os, json, base64, urllib.request, urllib.error, urllib.parse
from datetime import date, timedelta

TENANT_ID = os.environ['AZURE_TENANT_ID']
CLIENT_ID = os.environ['AZURE_CLIENT_ID']
CLIENT_SECRET = os.environ['AZURE_CLIENT_SECRET']

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_KEY']
H_SUPA = {'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY, 'Content-Type': 'application/json'}

SHAREPOINT_URL = (
    'https://jardinsdubandiat.sharepoint.com/:x:/r/sites/BOUTIQUE/_layouts/15/Doc.aspx'
    '?sourcedoc=%7B9A749FA5-292A-4291-8C94-C2BB4A56852D%7D'
    '&file=Prix%20vente%20l%25u00e9gumes%20-%20CIDIL%20-%202025.xlsx'
    '&action=default&mobileredirect=true'
)
SHEET_NAME = 'MISE A JOUR '

# Association (libelle, variete) du fichier Excel -> mise a jour a appliquer au catalogue.
# 'nom' : nom de la fiche catalogue a mettre a jour (creee si besoin pour les cas separes kg/botte/piece)
# 'unite' : unite a appliquer sur cette fiche (harmonisation demandee par la gestionnaire)
# 'famille_source' : nom d'une fiche existante dont on recopie la famille (pour les nouvelles fiches)
MAPPING = {
    ('AIL', 'THÉRADOR'): {'nom': 'Ail', 'unite': 'kg'},
    ('AUBERGINE', 'BLACK PEARL / BARBENTANE / ZEBRINA'): {'nom': 'Aubergine', 'unite': 'kg'},
    ('BETTERAVE ROUGE', 'PRIMEUR CRUE BOTTE'): {'nom': 'Betterave', 'unite': 'botte', 'split_from': 'Betterave', 'nom_split': 'Betterave botte'},
    ('BETTERAVE ROUGE', 'PRIMEUR CRUE KG'): {'nom': 'Betterave', 'unite': 'kg'},
    ('BETTERAVE ROUGE', 'RONDE PRIMEUR CUITE'): {'nom': 'Betterave cuite', 'unite': 'kg'},
    ('BLETTE', 'BLANCHE OU COULEUR'): {'nom': 'Blette', 'unite': None},
    ('BOUQUET AROMATIQUE', 'CORIANDRE'): {'nom': 'Coriandre', 'unite': 'botte'},
    ('BOUQUET AROMATIQUE', 'CIBOULETTE'): {'nom': 'Ciboulette', 'unite': 'botte'},
    ('BOUQUET AROMATIQUE', 'BASILIC'): {'nom': 'Basilic', 'unite': 'botte'},
    ('BOUQUET AROMATIQUE', 'PERSIL'): {'nom': 'Persil', 'unite': 'botte'},
    ('CAROTTE', 'FANE'): {'nom': 'Carotte', 'unite': 'botte', 'split_from': 'Carotte', 'nom_split': 'Carotte botte'},
    ('CAROTTE', 'VRAC'): {'nom': 'Carotte', 'unite': 'kg'},
    ('CÉLERI', 'BRANCHE'): {'nom': 'Céleri branche', 'unite': 'kg'},
    ('CÉLERI', 'RAVE'): {'nom': 'Céleri-rave', 'unite': 'kg'},
    ('CHOU', 'BLANC'): {'nom': 'Chou cabus blanc', 'unite': 'kg'},
    ('CHOU', 'BROCOLI'): {'nom': 'Brocoli', 'unite': 'kg'},
    ('CHOU', 'CHINOIS'): {'nom': 'Chou chinois', 'unite': 'kg'},
    ('CHOU', 'FLEUR'): {'nom': 'Chou-fleur', 'unite': 'kg'},
    ('CHOU', 'RAVE'): {'nom': 'Chou-rave', 'unite': 'pièce'},
    ('CHOU', 'VERT FRISÉ'): {'nom': 'Chou vert', 'unite': None},
    ('CONCOMBRE', 'LONG PRO'): {'nom': 'Concombre long vert', 'unite': 'pièce'},
    ('CONCOMBRE', 'EPINEUX'): {'nom': 'Concombre épineux (court)', 'unite': 'kg'},
    ('COURGETTE', 'JAUNE'): {'nom': 'Courgette jaune', 'unite': 'kg'},
    ('COURGETTE', 'VERTE'): {'nom': 'Courgette verte', 'unite': 'kg'},
    ('FENOUIL', ''): {'nom': 'Fenouil', 'unite': 'kg'},
    ('FÈVE', 'FINE'): {'nom': 'Fève', 'unite': 'kg'},
    ('FRAISE', ''): {'nom': 'Fraise', 'unite': 'kg'},
    ('HARICOT', 'VERT FIN'): {'nom': 'Haricot vert', 'unite': 'kg'},
    ('MÂCHE', 'VERTE'): {'nom': 'Mâche', 'unite': 'kg'},
    ('MELON', 'MAKEBA PIÈCE'): {'nom': 'Melon', 'unite': 'pièce', 'split_from': 'Melon', 'nom_split': 'Melon pièce'},
    ('MELON', 'MAKEBA KG'): {'nom': 'Melon', 'unite': 'kg'},
    ('MESCLUN', 'JEUNE POUSSE SALADE'): {'nom': 'Mesclun', 'unite': 'kg'},
    ('NAVET', 'ROND VIOLET PRIMEUR'): {'nom': 'Navet violet', 'unite': 'botte', 'split_from': 'Navet violet', 'nom_split': 'Navet violet botte'},
    ('OIGNON', 'BLANC'): {'nom': 'Oignon blanc', 'unite': 'kg'},
    ('OIGNON', 'JAUNE'): {'nom': 'Oignon jaune', 'unite': 'kg'},
    ('PATATE', 'DOUCE LONGUE'): {'nom': 'Patate douce', 'unite': 'kg'},
    ('PASTÈQUE', ''): {'nom': 'Pastèque', 'unite': 'kg'},
    ("PIMENT D'ESPELETTE", 'GORIA'): {'nom': 'Piment', 'unite': 'kg'},
    ('POIS', 'ÉCOSSER'): {'nom': 'Pois', 'unite': 'kg'},
    ('POIVRON', 'VERT'): {'nom': 'Poivron vert', 'unite': 'kg'},
    ('POMME DE TERRE', 'PRIMEUR'): {'nom': 'Pomme de terre primeurs', 'unite': 'kg'},
    ('POMME DE TERRE', 'CONSERVATION'): {'nom': 'Pomme de terre conservation', 'unite': 'kg'},
    ('RADIS', 'ROSE'): {'nom': 'Radis botte', 'unite': None},
    ('RADIS', 'NOIR'): {'nom': 'Radis noir', 'unite': 'kg'},
    ('RADIS', 'BLANC'): {'nom': 'Radis blanc', 'unite': 'kg'},
    ('SALADE', 'BATAVIA'): {'nom': 'Batavia', 'unite': 'pièce'},
    ('SALADE', 'FEUILLE DE CHÊNE'): {'nom': 'Feuille de chêne', 'unite': 'pièce'},
    ('SALADE', 'LAITUE POMMÉE'): {'nom': 'Laitue', 'unite': 'pièce'},
    ('TOMATE', 'CERISE'): {'nom': 'Tomate cerise', 'unite': 'kg'},
    ('TOMATE', 'CÔTELÉE ANCIENNE'): {'nom': 'Tomate ancienne', 'unite': 'kg'},
    ('TOMATE', 'RONDE'): {'nom': 'Tomate classique', 'unite': 'kg'},
}


def get_token():
    data = urllib.parse.urlencode({
        'grant_type': 'client_credentials', 'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET, 'scope': 'https://graph.microsoft.com/.default'
    }).encode()
    req = urllib.request.Request(f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token', data=data, method='POST')
    return json.loads(urllib.request.urlopen(req).read())['access_token']


def graph_get(url, token):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    return json.loads(urllib.request.urlopen(req).read())


def resoudre_fichier(token):
    b64 = base64.urlsafe_b64encode(SHAREPOINT_URL.encode('utf-8')).decode('utf-8').rstrip('=')
    share_id = 'u!' + b64
    item = graph_get(f'https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem', token)
    return item['parentReference']['driveId'], item['id']


def lire_prix(token, drive_id, item_id):
    sheet_enc = urllib.parse.quote(SHEET_NAME)
    url = (f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}"
           f"/workbook/worksheets('{sheet_enc}')/usedRange(valuesOnly=true)")
    return graph_get(url, token)['values']


def norm(s):
    return (s or '').strip().upper()


def sb_get(table, params):
    req = urllib.request.Request(f'{SUPA_URL}/rest/v1/{table}?{params}', headers=H_SUPA)
    return json.loads(urllib.request.urlopen(req).read())


def sb_patch(table, id_, body):
    req = urllib.request.Request(f'{SUPA_URL}/rest/v1/{table}?id=eq.{id_}', data=json.dumps(body).encode(),
                                  headers=H_SUPA, method='PATCH')
    urllib.request.urlopen(req)


def sb_post(table, body):
    req = urllib.request.Request(f'{SUPA_URL}/rest/v1/{table}', data=json.dumps(body).encode(),
                                  headers={**H_SUPA, 'Prefer': 'return=representation'}, method='POST')
    return json.loads(urllib.request.urlopen(req).read())


token = get_token()
drive_id, item_id = resoudre_fichier(token)
valeurs = lire_prix(token, drive_id, item_id)
print(f"{len(valeurs)} lignes lues dans le fichier")

catalogue = sb_get('catalogue', 'select=id,nom,unites,famille')
par_nom = {c['nom']: c for c in catalogue}

semaine_courante = (date.today() - timedelta(days=date.today().weekday())).isoformat()
legumes_semaine = sb_get('legumes', f'semaine=eq.{semaine_courante}&select=id,nom,prix_kg')
legumes_par_nom = {}
for l in legumes_semaine:
    legumes_par_nom.setdefault(l['nom'], []).append(l)


def maj_legume_semaine(nom, prix):
    for l in legumes_par_nom.get(nom, []):
        if l.get('prix_kg') != prix:
            sb_patch('legumes', l['id'], {'prix_kg': prix})
            print(f"    (prix mis a jour aussi sur la liste de la semaine en cours)")


maj, crees, ignores = 0, 0, 0
for row in valeurs[1:]:
    libelle = norm(row[0] if len(row) > 0 else '')
    variete = norm(row[1] if len(row) > 1 else '')
    prix = row[56] if len(row) > 56 else None
    if not isinstance(prix, (int, float)) or prix <= 0:
        ignores += 1
        continue
    regle = MAPPING.get((libelle, variete))
    if not regle:
        ignores += 1
        continue

    if 'split_from' in regle:
        source = par_nom.get(regle['split_from'])
        if not source:
            print(f"  ATTENTION fiche source introuvable pour split : {regle['split_from']}")
            continue
        nouveau_nom = regle['nom_split']
        if nouveau_nom in par_nom:
            sb_patch('catalogue', par_nom[nouveau_nom]['id'], {'prix_defaut': prix, 'unites': regle['unite']})
        else:
            created = sb_post('catalogue', {
                'nom': nouveau_nom, 'unites': regle['unite'], 'prix_defaut': prix,
                'famille': source.get('famille') or ''
            })
            par_nom[nouveau_nom] = created[0]
            crees += 1
        print(f"  {nouveau_nom} ({regle['unite']}) -> {prix}")
        if regle['split_from'] in legumes_par_nom:
            print(f"    (attention : {regle['split_from']} est deja publie cette semaine, prix a verifier manuellement car plusieurs unites possibles)")
        maj += 1
        continue

    cible = par_nom.get(regle['nom'])
    if not cible:
        print(f"  ATTENTION fiche catalogue introuvable : {regle['nom']}")
        continue
    body = {'prix_defaut': prix}
    if regle['unite']:
        body['unites'] = regle['unite']
    sb_patch('catalogue', cible['id'], body)
    maj_legume_semaine(regle['nom'], prix)
    print(f"  {regle['nom']} -> {prix}")
    maj += 1

print(f"\n{maj} prix mis a jour, {crees} nouvelle(s) fiche(s) creee(s), {ignores} ligne(s) ignoree(s) (sans prix ou hors correspondance connue)")
