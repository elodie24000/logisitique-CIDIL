# -*- coding: utf-8 -*-
"""Synchronise les prix du catalogue depuis le fichier SharePoint
"Prix vente legumes - CIDIL - 2025.xlsx", onglet "MISE A JOUR " (colonnes
A=libelle, B=variete, C=unite, BE=prix moyen HT bio).

La correspondance entre les lignes du fichier et les fiches de l'app a ete
validee manuellement avec la gestionnaire (regles ci-dessous). Les produits
absents du fichier ou sans prix renseigne sont ignores."""
import os, json, re, base64, urllib.request, urllib.error, urllib.parse
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

# Association (libelle, variete, unite) du fichier Excel -> mise a jour a appliquer au catalogue.
# L'unite du fichier fait partie de la cle car certains legumes ont plusieurs lignes
# avec le meme libelle/variete mais des unites (et donc des prix) differentes (ex: Melon).
# 'nom' : nom de la fiche catalogue a mettre a jour (creee si besoin pour les cas separes kg/botte/piece)
# 'unite' : unite a appliquer sur cette fiche (harmonisation demandee par la gestionnaire)
MAPPING = {
    ('AIL', 'THÉRADOR', 'KG'): {'nom': 'Ail', 'unite': 'kg'},
    ('AUBERGINE', 'BLACK PEARL / BARBENTANE / ZEBRINA', 'KG'): {'nom': 'Aubergine', 'unite': 'kg'},
    ('BETTERAVE ROUGE', 'PRIMEUR CRUE BOTTE', 'BOTTE'): {'nom': 'Betterave', 'unite': 'botte', 'split_from': 'Betterave', 'nom_split': 'Betterave botte'},
    ('BETTERAVE ROUGE', 'PRIMEUR CRUE KG', 'KG'): {'nom': 'Betterave', 'unite': 'kg'},
    ('BETTERAVE ROUGE', 'RONDE PRIMEUR CUITE', 'KG'): {'nom': 'Betterave cuite', 'unite': 'kg'},
    ('BLETTE', 'BLANCHE OU COULEUR', 'KG'): {'nom': 'Blette', 'unite': None},
    ('BOUQUET AROMATIQUE', 'CORIANDRE', 'BOUQUET'): {'nom': 'Coriandre', 'unite': 'botte'},
    ('BOUQUET AROMATIQUE', 'CIBOULETTE', 'BOUQUET'): {'nom': 'Ciboulette', 'unite': 'botte'},
    ('BOUQUET AROMATIQUE', 'BASILIC', 'BOUQUET'): {'nom': 'Basilic', 'unite': 'botte'},
    ('BOUQUET AROMATIQUE', 'PERSIL', 'BOUQUET'): {'nom': 'Persil', 'unite': 'botte'},
    ('CAROTTE', 'FANE', 'LA BOTTE'): {'nom': 'Carotte', 'unite': 'botte', 'split_from': 'Carotte', 'nom_split': 'Carotte botte'},
    ('CAROTTE', 'VRAC', 'KG'): {'nom': 'Carotte', 'unite': 'kg'},
    ('CÉLERI', 'BRANCHE', 'KG'): {'nom': 'Céleri branche', 'unite': 'kg'},
    ('CÉLERI', 'RAVE', 'KG'): {'nom': 'Céleri-rave', 'unite': 'kg'},
    ('CHOU', 'BLANC', 'KG'): {'nom': 'Chou cabus blanc', 'unite': 'kg'},
    ('CHOU', 'ROUGE', 'KG'): {'nom': 'Chou cabus rouge', 'unite': 'kg'},
    ('CHOU', 'BROCOLI', 'KG'): {'nom': 'Brocoli', 'unite': 'kg'},
    ('CHOU', 'CHINOIS', 'KG'): {'nom': 'Chou chinois', 'unite': 'kg'},
    ('CHOU', 'FLEUR', 'KG'): {'nom': 'Chou-fleur', 'unite': 'kg'},
    ('CHOU', 'RAVE', 'PIÈCE'): {'nom': 'Chou-rave', 'unite': 'pièce'},
    ('CHOU', 'VERT FRISÉ', 'KG'): {'nom': 'Chou vert', 'unite': None},
    ('CONCOMBRE', 'LONG PRO', 'PIÈCE'): {'nom': 'Concombre long vert', 'unite': 'pièce'},
    ('CONCOMBRE', 'EPINEUX', 'KG'): {'nom': 'Concombre épineux (court)', 'unite': 'kg'},
    ('COURGETTE', 'JAUNE', 'KG'): {'nom': 'Courgette jaune', 'unite': 'kg'},
    ('COURGETTE', 'VERTE', 'KG'): {'nom': 'Courgette verte', 'unite': 'kg'},
    ('FENOUIL', '', 'KG'): {'nom': 'Fenouil', 'unite': 'kg'},
    ('FÈVE', 'FINE', 'KG'): {'nom': 'Fève', 'unite': 'kg'},
    ('FRAISE', '', 'KG'): {'nom': 'Fraise', 'unite': 'kg'},
    ('HARICOT', 'VERT FIN', 'KG'): {'nom': 'Haricot vert', 'unite': 'kg'},
    ('MÂCHE', 'VERTE', 'KG'): {'nom': 'Mâche', 'unite': 'kg'},
    ('MELON', 'MAKEBA', 'PIÈCE'): {'nom': 'Melon', 'unite': 'pièce', 'split_from': 'Melon', 'nom_split': 'Melon pièce'},
    ('MELON', 'MAKEBA', 'KG'): {'nom': 'Melon', 'unite': 'kg'},
    ('MESCLUN', 'JEUNE POUSSE SALADE', 'KG'): {'nom': 'Mesclun', 'unite': 'kg'},
    ('NAVET', 'ROND VIOLET PRIMEUR', 'BOTTE'): {'nom': 'Navet violet', 'unite': 'botte', 'split_from': 'Navet violet', 'nom_split': 'Navet violet botte'},
    ('OIGNON', 'BLANC', 'KG'): {'nom': 'Oignon blanc', 'unite': 'kg'},
    ('OIGNON', 'JAUNE', 'KG'): {'nom': 'Oignon jaune', 'unite': 'kg'},
    ('PATATE', 'DOUCE LONGUE', 'KG'): {'nom': 'Patate douce', 'unite': 'kg'},
    ('PASTÈQUE', '', 'KG'): {'nom': 'Pastèque', 'unite': 'kg'},
    ("PIMENT D'ESPELETTE", 'GORIA', 'KG'): {'nom': 'Piment', 'unite': 'kg'},
    ('POIS', 'ÉCOSSER', 'KG'): {'nom': 'Pois', 'unite': 'kg'},
    ('POIVRON', 'VERT', 'KG'): {'nom': 'Poivron vert', 'unite': 'kg'},
    ('POMME DE TERRE', 'PRIMEUR', 'KG'): {'nom': 'Pomme de terre primeurs', 'unite': 'kg'},
    ('POMME DE TERRE', 'CONSERVATION', 'KG'): {'nom': 'Pomme de terre conservation', 'unite': 'kg'},
    ('RADIS', 'ROSE', 'BOTTE'): {'nom': 'Radis botte', 'unite': None},
    ('RADIS', 'NOIR', 'KG'): {'nom': 'Radis noir', 'unite': 'kg'},
    ('RADIS', 'BLANC', 'KG'): {'nom': 'Radis blanc', 'unite': 'kg'},
    ('SALADE', 'BATAVIA', 'PIÈCE'): {'nom': 'Batavia', 'unite': 'pièce'},
    ('SALADE', 'FEUILLE DE CHÊNE', 'PIÈCE'): {'nom': 'Feuille de chêne', 'unite': 'pièce'},
    ('SALADE', 'LAITUE POMMÉE', 'PIÈCE'): {'nom': 'Laitue', 'unite': 'pièce'},
    ('TOMATE', 'CERISE', 'KG'): {'nom': 'Tomate cerise', 'unite': 'kg'},
    ('TOMATE', 'CÔTELÉE ANCIENNE', 'KG'): {'nom': 'Tomate ancienne', 'unite': 'kg'},
    ('TOMATE', 'ANCIENNE', 'KG'): {'nom': 'Tomate ancienne', 'unite': 'kg'},
    ('TOMATE', 'RONDE', 'KG'): {'nom': 'Tomate classique', 'unite': 'kg'},
    ('TOMATE', 'CLASSIQUE', 'KG'): {'nom': 'Tomate classique', 'unite': 'kg'},
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
    return re.sub(r'\s+', ' ', (s or '').strip()).upper()


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

legumes_toutes_semaines = sb_get('legumes', 'select=id,nom,prix_kg,semaine')
legumes_par_nom = {}
for l in legumes_toutes_semaines:
    legumes_par_nom.setdefault(l['nom'], []).append(l)


def maj_legume_semaine(nom, prix):
    lignes = legumes_par_nom.get(nom, [])
    maj_count = 0
    for l in lignes:
        if l.get('prix_kg') != prix:
            sb_patch('legumes', l['id'], {'prix_kg': prix})
            maj_count += 1
    if maj_count:
        print(f"    (prix mis a jour sur {maj_count} liste(s) hebdomadaire(s) existante(s))")


maj, crees, ignores = 0, 0, 0
non_reconnues = []
for row in valeurs[1:]:
    libelle = norm(row[0] if len(row) > 0 else '')
    variete = norm(row[1] if len(row) > 1 else '')
    unite = norm(row[2] if len(row) > 2 else '')
    prix = row[56] if len(row) > 56 else None
    if not isinstance(prix, (int, float)) or prix <= 0:
        ignores += 1
        continue
    regle = MAPPING.get((libelle, variete, unite))
    if not regle:
        ignores += 1
        non_reconnues.append((libelle, variete, unite, prix))
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

print(f"\n{maj} prix mis a jour, {crees} nouvelle(s) fiche(s) creee(s), {ignores} ligne(s) ignoree(s)")

if non_reconnues:
    print(f"\nATTENTION : {len(non_reconnues)} ligne(s) avec un prix mais SANS correspondance connue (a verifier / ajouter au mapping) :")
    for libelle, variete, unite, prix in non_reconnues:
        print(f"  - {libelle} / {variete} / {unite} -> {prix}")
