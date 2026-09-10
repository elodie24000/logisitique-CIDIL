"""
Script de diagnostic (lecture seule, ne touche jamais Supabase) pour comprendre
pourquoi scripts/update_prix_rnm.py echoue systematiquement ("Aucune ressource
CSV trouvee") depuis juillet 2026.

Etapes :
1) Reproduit l'appel actuel (dataset_id code en dur) et affiche la reponse brute.
2) Cherche sur data.gouv.fr les datasets FranceAgriMer de cotations fruits/legumes
   via l'API de recherche, pour voir si le dataset a ete renomme/deplace.
3) Pour le/les dataset(s) trouve(s), liste les ressources (titre, format, url).
4) Telecharge la premiere ressource CSV ou XLSX trouvee et affiche ses colonnes
   + 5 lignes d'exemple, pour verifier la structure reelle des donnees.

A supprimer une fois le vrai correctif valide.
"""
import json
import urllib.request
import urllib.error
import urllib.parse
import csv
import io

UA = {'User-Agent': 'CIDIL-App-Diagnostic/1.0'}


def get_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def section(title):
    print('\n' + '=' * 70)
    print(title)
    print('=' * 70)


# --- 1) Reproduire l'appel actuel ---
section("1) Appel actuel (dataset_id code en dur = 573051)")
dataset_id = '573051'
api_url = f'https://www.data.gouv.fr/api/1/datasets/cotations-des-fruits-et-legumes-par-marche-et-par-produit-{dataset_id}/'
print(f"URL appelee : {api_url}")
try:
    meta = get_json(api_url)
    print(f"Titre du dataset : {meta.get('title')}")
    print(f"Nombre de ressources : {len(meta.get('resources', []))}")
    for r in meta.get('resources', [])[:20]:
        print(f"  - format={r.get('format')!r} title={r.get('title')!r} url={r.get('url')}")
except urllib.error.HTTPError as e:
    print(f"HTTPError {e.code} : {e.reason}")
except Exception as e:
    print(f"Erreur : {e}")

# --- 2) Recherche sur data.gouv.fr (plusieurs requetes, de large a precise) ---
section("2) Recherche de datasets (plusieurs requetes)")
queries = ['cotations', 'FranceAgriMer', 'RNM', 'cotations legumes', 'marche interet national']
found_datasets = []
seen_ids = set()
for q in queries:
    search_url = 'https://www.data.gouv.fr/api/1/datasets/?' + urllib.parse.urlencode({'q': q, 'page_size': 15})
    print(f"\nRequete : {q!r}")
    print(f"URL appelee : {search_url}")
    try:
        results = get_json(search_url)
        total = results.get('total', '?')
        print(f"Total resultats : {total}")
        for d in results.get('data', []):
            print(f"  - id={d.get('id')} slug={d.get('slug')} title={d.get('title')!r} organization={(d.get('organization') or {}).get('name')}")
            if d.get('id') not in seen_ids:
                seen_ids.add(d.get('id'))
                found_datasets.append(d)
    except Exception as e:
        print(f"Erreur recherche : {e}")

# --- 2bis) Organisation FranceAgriMer : lister ses datasets directement ---
section("2bis) Datasets de l'organisation FranceAgriMer")
try:
    org_search = get_json('https://www.data.gouv.fr/api/1/organizations/?' + urllib.parse.urlencode({'q': 'FranceAgriMer'}))
    for org in org_search.get('data', []):
        print(f"Organisation trouvee : id={org.get('id')} name={org.get('name')!r} slug={org.get('slug')}")
        org_id = org.get('id')
        if org_id:
            org_datasets = get_json(f'https://www.data.gouv.fr/api/1/organizations/{org_id}/datasets/?page_size=50')
            ds_list = org_datasets.get('data', org_datasets) if isinstance(org_datasets, dict) else org_datasets
            if isinstance(ds_list, dict):
                ds_list = ds_list.get('data', [])
            print(f"  Nombre de datasets de cette organisation : {len(ds_list) if isinstance(ds_list, list) else '?'}")
            if isinstance(ds_list, list):
                for d in ds_list:
                    title = d.get('title', '')
                    if any(k in title.lower() for k in ['cotation', 'prix', 'marche']):
                        print(f"    * id={d.get('id')} title={title!r}")
                        if d.get('id') not in seen_ids:
                            seen_ids.add(d.get('id'))
                            found_datasets.append(d)
except Exception as e:
    print(f"Erreur organisation : {e}")

# --- 3) Detail des ressources pour chaque dataset trouve ---
section("3) Detail des ressources des datasets trouves")
candidate_resource = None
for d in found_datasets[:5]:
    slug_or_id = d.get('id')
    detail_url = f'https://www.data.gouv.fr/api/1/datasets/{slug_or_id}/'
    print(f"\n--- Dataset: {d.get('title')} ({detail_url}) ---")
    try:
        detail = get_json(detail_url)
        for r in detail.get('resources', []):
            fmt = (r.get('format') or '').upper()
            print(f"  format={fmt!r} title={r.get('title')!r} last_modified={r.get('last_modified')} url={r.get('url')}")
            if fmt in ('CSV', 'XLS', 'XLSX') and candidate_resource is None:
                candidate_resource = {'format': fmt, 'url': r.get('url'), 'dataset_title': d.get('title')}
    except Exception as e:
        print(f"  Erreur : {e}")

# --- 4) Telecharger et inspecter la premiere ressource exploitable ---
section("4) Inspection de la premiere ressource CSV/XLS(X) trouvee")
if not candidate_resource:
    print("Aucune ressource CSV/XLS/XLSX trouvee dans les datasets candidats ci-dessus.")
else:
    print(f"Ressource choisie : {candidate_resource}")
    url = candidate_resource['url']
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        print(f"Taille telechargee : {len(raw)} octets")

        if candidate_resource['format'] == 'CSV':
            for delim in [';', ',', '\t']:
                content = raw.decode('utf-8', errors='replace')
                reader = csv.DictReader(io.StringIO(content), delimiter=delim)
                rows = list(reader)
                if rows and len(rows[0].keys()) > 1:
                    print(f"Delimiteur detecte : {delim!r}")
                    print(f"Colonnes : {list(rows[0].keys())}")
                    print(f"Nombre de lignes : {len(rows)}")
                    print("5 premieres lignes :")
                    for row in rows[:5]:
                        print(f"  {row}")
                    break
        else:
            print("Format XLS/XLSX : necessite openpyxl, non installe dans ce diagnostic minimal.")
            print("Premiers octets (signature) :", raw[:8])
    except Exception as e:
        print(f"Erreur telechargement/parsing : {e}")

# --- 5) Verification cibles : "COTATIONS JOURNALIERES FRUITS ET LEGUMES" (probable dataset actuel) ---
section("5) Dataset cible : COTATIONS JOURNALIERES FRUITS ET LEGUMES (id 536991d7a3a729239d203d80)")
try:
    detail = get_json('https://www.data.gouv.fr/api/1/datasets/536991d7a3a729239d203d80/')
    print(f"Titre : {detail.get('title')}")
    print(f"Description (200 premiers caracteres) : {(detail.get('description') or '')[:200]!r}")
    for r in detail.get('resources', []):
        print(f"  format={r.get('format')!r} title={r.get('title')!r} url={r.get('url')}")
    resources = detail.get('resources', [])
    if resources:
        url = resources[0].get('url')
        print(f"\nTest telechargement de : {url}")
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read(2000)
            print(f"OK - premiers octets : {raw[:300]}")
        except Exception as e:
            print(f"Erreur telechargement : {e}")
except Exception as e:
    print(f"Erreur : {e}")

section("FIN DU DIAGNOSTIC")
