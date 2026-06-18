"""
Mise à jour automatique des prix depuis data.gouv.fr (FranceAgriMer)
Dataset : cotations fruits et légumes par marché et par produit
Exécuté chaque lundi à 7h via GitHub Actions
"""
import os, json, urllib.request, urllib.error, csv, io

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_SERVICE_KEY']

HEADERS_SUPA = {
    'apikey': SUPA_KEY,
    'Authorization': 'Bearer ' + SUPA_KEY,
    'Content-Type': 'application/json'
}

# Correspondances noms catalogue → mots-clés dans les données
CORRESPONDANCES = {
    'Tomate':         ['tomate'],
    'Courgette':      ['courgette'],
    'Concombre':      ['concombre'],
    'Aubergine':      ['aubergine'],
    'Poivron':        ['poivron'],
    'Carotte':        ['carotte'],
    'Betterave':      ['betterave'],
    'Radis':          ['radis'],
    'Oignon':         ['oignon'],
    'Poireau':        ['poireau'],
    'Pomme de terre': ['pomme de terre'],
    'Salade':         ['laitue', 'salade', 'batavia'],
    'Épinard':        ['epinard', 'épinard'],
    'Blette':         ['blette', 'bette'],
    'Chou':           ['chou'],
    'Haricot':        ['haricot'],
    'Ail':            ['ail'],
    'Fenouil':        ['fenouil'],
    'Navet':          ['navet'],
    'Basilic':        ['basilic'],
    'Persil':         ['persil'],
    'Coriandre':      ['coriandre'],
}

def supa_get(table, params=''):
    url = f'{SUPA_URL}/rest/v1/{table}?{params}'
    req = urllib.request.Request(url, headers=HEADERS_SUPA)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def supa_patch(table, id_, data):
    url = f'{SUPA_URL}/rest/v1/{table}?id=eq.{id_}'
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={**HEADERS_SUPA, 'Prefer': 'return=minimal'}, method='PATCH')
    with urllib.request.urlopen(req) as r:
        return r.status

def fetch_datagouv():
    """Récupère les cotations depuis data.gouv.fr via l'API CKAN"""
    # ID du dataset FranceAgriMer sur data.gouv.fr
    dataset_id = '573051'
    api_url = f'https://www.data.gouv.fr/api/1/datasets/cotations-des-fruits-et-legumes-par-marche-et-par-produit-{dataset_id}/'

    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'CIDIL-App/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.loads(r.read())

        # Trouver la ressource CSV la plus récente
        resources = meta.get('resources', [])
        csv_resources = [r for r in resources if r.get('format','').upper() == 'CSV']
        if not csv_resources:
            print("Aucune ressource CSV trouvée")
            return None

        # Prendre la plus récente
        latest = sorted(csv_resources, key=lambda x: x.get('last_modified',''), reverse=True)[0]
        csv_url = latest['url']
        print(f"CSV trouvé : {csv_url}")

        req2 = urllib.request.Request(csv_url, headers={'User-Agent': 'CIDIL-App/1.0'})
        with urllib.request.urlopen(req2, timeout=30) as r:
            content = r.read().decode('utf-8', errors='replace')

        reader = csv.DictReader(io.StringIO(content), delimiter=';')
        rows = list(reader)
        print(f"✓ {len(rows)} lignes chargées")
        return rows

    except Exception as e:
        print(f"Erreur data.gouv.fr : {e}")
        return None

def trouver_prix(nom_legume, rows):
    """Cherche le prix moyen le plus récent pour un légume"""
    mots_cles = CORRESPONDANCES.get(nom_legume, [nom_legume.lower()])

    # Colonnes possibles selon le format du fichier
    col_produit = next((k for k in (rows[0].keys() if rows else []) if 'produit' in k.lower() or 'libelle' in k.lower()), None)
    col_prix = next((k for k in (rows[0].keys() if rows else []) if 'prix' in k.lower() and 'moyen' in k.lower()), None)
    if not col_prix:
        col_prix = next((k for k in (rows[0].keys() if rows else []) if 'prix' in k.lower()), None)

    if not col_produit or not col_prix:
        print(f"Colonnes non trouvées. Disponibles : {list(rows[0].keys()) if rows else []}")
        return None

    candidats = []
    for row in rows:
        produit = str(row.get(col_produit, '')).lower()
        if any(mc in produit for mc in mots_cles):
            try:
                prix_str = row.get(col_prix, '').replace(',', '.').strip()
                if prix_str:
                    candidats.append(float(prix_str))
            except:
                pass

    if candidats:
        return round(sum(candidats) / len(candidats), 2)
    return None

def main():
    print("=== Mise à jour prix FranceAgriMer (data.gouv.fr) ===")

    catalogue = supa_get('catalogue', 'order=nom.asc')
    print(f"Catalogue : {len(catalogue)} légumes")

    rows = fetch_datagouv()
    if not rows:
        print("⚠ Données non disponibles - arrêt")
        return

    mis_a_jour = 0
    for legume in catalogue:
        nom = legume['nom']
        prix = trouver_prix(nom, rows)
        if prix and prix != legume.get('prix_defaut'):
            try:
                supa_patch('catalogue', legume['id'], {'prix_defaut': prix})
                print(f"✓ {nom} : {legume.get('prix_defaut')} → {prix} €")
                mis_a_jour += 1
            except Exception as e:
                print(f"✗ Erreur {nom} : {e}")
        elif prix:
            print(f"= {nom} : {prix} € (inchangé)")
        else:
            print(f"? {nom} : pas de correspondance RNM")

    print(f"\n=== Terminé : {mis_a_jour} prix mis à jour ===")

if __name__ == '__main__':
    main()
