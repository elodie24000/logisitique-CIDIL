"""
Mise à jour automatique des prix depuis RNM Nantes (FranceAgriMer)
Exécuté chaque lundi à 7h via GitHub Actions
"""
import os, json, urllib.request, urllib.error

SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
SUPA_KEY = os.environ['SUPABASE_SERVICE_KEY']

HEADERS_SUPA = {
    'apikey': SUPA_KEY,
    'Authorization': 'Bearer ' + SUPA_KEY,
    'Content-Type': 'application/json'
}

# Correspondances noms catalogue → mots-clés RNM
CORRESPONDANCES = {
    'Tomate':      ['tomate'],
    'Courgette':   ['courgette'],
    'Concombre':   ['concombre'],
    'Aubergine':   ['aubergine'],
    'Poivron':     ['poivron'],
    'Carotte':     ['carotte'],
    'Betterave':   ['betterave'],
    'Radis':       ['radis'],
    'Oignon':      ['oignon'],
    'Poireau':     ['poireau'],
    'Pomme de terre': ['pomme de terre', 'pomme terre'],
    'Salade':      ['laitue', 'salade'],
    'Épinard':     ['epinard', 'épinard'],
    'Blette':      ['blette', 'bette'],
    'Chou':        ['chou'],
    'Haricot':     ['haricot'],
    'Ail':         ['ail'],
    'Fenouil':     ['fenouil'],
    'Navet':       ['navet'],
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

def fetch_rnm_nantes():
    """Tente de récupérer les cours RNM du marché de Nantes"""
    # URL API RNM FranceAgriMer - marché de Nantes (code NAN)
    urls_to_try = [
        'https://rnm.franceagrimer.fr/prix?MARCHE=NAN&format=json',
        'https://rnm.franceagrimer.fr/prix?marche=NAN&format=json',
    ]
    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                if data:
                    print(f"✓ RNM récupéré : {len(data)} entrées")
                    return data
        except Exception as e:
            print(f"Tentative échouée ({url}) : {e}")
    return None

def trouver_prix_rnm(nom_legume, rnm_data):
    """Cherche le prix RNM correspondant à un légume"""
    mots_cles = CORRESPONDANCES.get(nom_legume, [nom_legume.lower()])
    for entry in rnm_data:
        produit = str(entry.get('produit', '') or entry.get('libelle', '') or '').lower()
        if any(mc in produit for mc in mots_cles):
            prix = entry.get('prix_moyen') or entry.get('prix') or entry.get('prixMoyen')
            if prix:
                return float(prix)
    return None

def main():
    print("=== Mise à jour prix RNM Nantes ===")

    # Charger le catalogue
    catalogue = supa_get('catalogue', 'order=nom.asc')
    print(f"Catalogue : {len(catalogue)} légumes")

    # Récupérer les cours RNM
    rnm_data = fetch_rnm_nantes()
    if not rnm_data:
        print("⚠ RNM non disponible - arrêt du script")
        return

    # Mettre à jour les prix
    mis_a_jour = 0
    for legume in catalogue:
        nom = legume['nom']
        prix_rnm = trouver_prix_rnm(nom, rnm_data)
        if prix_rnm and prix_rnm != legume.get('prix_defaut'):
            try:
                supa_patch('catalogue', legume['id'], {'prix_defaut': prix_rnm})
                print(f"✓ {nom} : {legume.get('prix_defaut')} → {prix_rnm} €")
                mis_a_jour += 1
            except Exception as e:
                print(f"✗ Erreur mise à jour {nom} : {e}")

    print(f"\n=== Terminé : {mis_a_jour} prix mis à jour ===")

if __name__ == '__main__':
    main()
