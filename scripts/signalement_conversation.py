"""Circuit « Déclarer un problème » : étapes du workflow .github/workflows/claude-signalement.yml.

  preparer : écrit la conversation (fiche GitHub + commentaires) dans $RUNNER_TEMP/conversation.md
             pour le Claude de dépannage, et donne le n° de signalement à l'étape suivante.
  publier  : lit la réponse structurée de Claude, vérifie et publie le correctif (ou le met de côté
             pour Élodie), écrit la réponse dans l'encadré de l'appli (table signalement_messages),
             la recopie sur la fiche GitHub et envoie le récapitulatif par e-mail à Élodie.

Garde-fous du correctif publié tout seul : seuls index.html, sw.js et docs/JOURNAL.md peuvent changer,
le JavaScript doit se compiler, et le point de sauvegarde (tag avant-signalement-…) est posé avant.
Sinon, le correctif part sur une branche à part et Élodie décide.
"""
import ast, json, os, re, subprocess, sys, urllib.request

DEPOT = os.environ.get('GITHUB_REPOSITORY', 'elodie24000/logisitique-CIDIL')
ISSUE = int(os.environ['ISSUE'])
GH_TOKEN = os.environ['GH_TOKEN']
TMP = os.environ.get('RUNNER_TEMP', '/tmp')
SUPA_URL = 'https://ulvrwtwxzhlrplvbcsrd.supabase.co'
LIEN_APP = 'https://elodie24000.github.io/logisitique-CIDIL/'
FICHIERS_AUTORISES = {'index.html', 'sw.js', 'docs/JOURNAL.md'}
EXPEDITEUR = {'email': None, 'name': 'CIDIL Maraîchage'}


def http(methode, url, headers, corps=None):
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=data, method=methode, headers={**headers, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt.strip() else None


def gh(methode, chemin, corps=None):
    return http(methode, f'https://api.github.com/repos/{DEPOT}/{chemin}', {
        'Authorization': 'Bearer ' + GH_TOKEN, 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'cidil-signalements'}, corps)


def sortie(cle, valeur):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
        f.write(f'{cle}={valeur}\n')


def git(*args, check=True):
    return subprocess.run(['git', *args], check=check, capture_output=True, text=True).stdout.strip()


# ── Étape 1 : préparer la conversation ──────────────────────────────────────
def preparer():
    issue = gh('GET', f'issues/{ISSUE}')
    m = re.search(r'<!-- signalement-app id=(\d+) -->', issue.get('body') or '')
    if not m:
        sys.exit('Fiche sans repère signalement-app')
    lignes = [f'# Signalement n° {m.group(1)} (fiche GitHub n° {ISSUE})', '', '## Message de départ', '',
              issue['body'], '']
    page = 1
    while True:
        coms = gh('GET', f'issues/{ISSUE}/comments?per_page=100&page={page}') or []
        for c in coms:
            corps = c.get('body') or ''
            if '<!-- reponse-claude' in corps:
                auteur = 'Claude (toi, réponse précédente)'
                corps = corps.split('<!-- detail-elodie -->')[0]
            elif '<!-- message-app' in corps:
                auteur = 'Équipe, depuis l\'appli'
            elif c['user']['login'] == DEPOT.split('/')[0]:
                auteur = 'Élodie (propriétaire, directement sur GitHub)'
            else:
                continue  # commentaires d'outils ou d'inconnus : ignorés
            lignes += [f'## {auteur} — {c["created_at"]}', '', corps.strip(), '']
        if len(coms) < 100:
            break
        page += 1
    with open(os.path.join(TMP, 'conversation.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lignes))
    sortie('signalement_id', m.group(1))


# ── Étape 2 : vérifier, publier, répondre ───────────────────────────────────
def js_compile():
    """Le JavaScript de index.html et sw.js doit au moins se compiler."""
    script = r'''
const fs = require('fs'), vm = require('vm');
const html = fs.readFileSync('index.html', 'utf8');
const blocs = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (!blocs.length) throw new Error('aucun script trouvé dans index.html');
blocs.forEach((b, i) => new vm.Script(b, { filename: 'index.html#script' + i }));
new vm.Script(fs.readFileSync('sw.js', 'utf8'), { filename: 'sw.js' });
'''
    r = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or '')[-600:]


def destinataire_elodie():
    """Adresse d'Élodie, reprise de la liste déjà utilisée pour le récap du vendredi."""
    src = open('scripts/send_email_gestionnaire_vendredi.py', encoding='utf-8').read()
    arbre = ast.parse(src)
    for n in arbre.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'DESTINATAIRES':
            for d in ast.literal_eval(n.value):
                if 'gestionnaire' in d.get('name', '').lower():
                    return d
        if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'EXPEDITEUR_EMAIL':
            EXPEDITEUR['email'] = ast.literal_eval(n.value)
    return None


def publier():
    sid = int(os.environ['SIGNALEMENT_ID'])
    supa = {'apikey': os.environ['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + os.environ['SUPABASE_SERVICE_KEY']}
    try:
        rep = json.loads(os.environ.get('STRUCTURED') or '{}')
    except json.JSONDecodeError:
        rep = {}
    statut = rep.get('statut') or 'pour_elodie'
    reponse = (rep.get('reponse') or '').strip() or \
        "Je n'ai pas réussi à traiter ta demande tout seul. Élodie est prévenue et va regarder."
    resume = (rep.get('resume_elodie') or '').strip() or 'Pas de réponse structurée de Claude (voir le journal du workflow).'
    if not rep:
        statut = 'pour_elodie'

    git('add', '-A')
    modifies = [f for f in git('diff', '--cached', '--name-only', 'origin/main').splitlines() if f]
    commits = [f for f in git('diff', '--name-only', 'origin/main', 'HEAD').splitlines() if f]
    modifies = sorted(set(modifies) | set(commits))
    publie, branche, note = False, None, ''

    if statut != 'corrige' and modifies:
        note = f'Claude avait modifié {", ".join(modifies)} sans conclure à un correctif : modifications abandonnées.'
        modifies = []
    elif statut == 'corrige' and not modifies:
        statut, note = 'pour_elodie', 'Claude a annoncé un correctif mais aucun fichier n\'a changé.'

    if modifies:
        git('config', 'user.name', 'Claude (dépannage CIDIL)')
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        titre = (rep.get('message_commit') or f'Dépannage signalement n° {sid}').strip()
        git('commit', '-m', f'{titre}\n\nSignalement n° {sid} (fiche #{ISSUE}), corrigé par le Claude de dépannage.', check=False)
        hors_cadre = [f for f in modifies if f not in FICHIERS_AUTORISES]
        ok_js, err_js = js_compile()
        if not hors_cadre and ok_js:
            r = subprocess.run(['git', 'push', 'origin', 'HEAD:main'], capture_output=True, text=True)
            publie = r.returncode == 0
            if not publie:
                note = 'La version en ligne a changé entre-temps : correctif mis de côté.'
        else:
            note = (f'Fichiers hors du cadre : {", ".join(hors_cadre)}. ' if hors_cadre else '') + \
                   ('' if ok_js else f'Le JavaScript ne se compile pas : {err_js}')
        if not publie:
            branche = f'signalement-{ISSUE}'
            subprocess.run(['git', 'push', '-f', 'origin', f'HEAD:refs/heads/{branche}'], capture_output=True, text=True)
            statut = 'pour_elodie'
            reponse = ("J'ai préparé une correction, mais elle doit d'abord être validée par Élodie. "
                       "Elle est prévenue, tu n'as rien à faire pour l'instant.")
        else:
            try:  # GitHub Pages : relance la mise en ligne (un push du workflow ne la déclenche pas toujours)
                gh('POST', 'pages/builds')
            except Exception as e:
                print('pages/builds :', e)

    # Réponse dans l'encadré de l'appli
    http('POST', f'{SUPA_URL}/rest/v1/signalement_messages', supa,
         {'signalement_id': sid, 'auteur': 'Claude', 'texte': reponse[:4000]})
    etat = {'corrige': 'corrige' if publie else 'pour_elodie', 'question': 'repondu',
            'rien_a_corriger': 'repondu'}.get(statut, 'pour_elodie')
    http('PATCH', f'{SUPA_URL}/rest/v1/signalements?id=eq.{sid}', supa, {'statut': etat})

    # Trace sur la fiche GitHub
    libelle = {'corrige': '✅ Corrigé et mis en ligne', 'repondu': '💬 Réponse / question',
               'pour_elodie': '🙋 Transmis à Élodie'}[etat]
    lien_commit = f'\n- Correctif : {git("rev-parse", "HEAD")}' if publie else ''
    lien_branche = f'\n- Correctif en attente sur la branche `{branche}`' if branche else ''
    gh('POST', f'issues/{ISSUE}/comments', {'body': (
        f'<!-- reponse-claude -->\n**{libelle}**\n\n{reponse}\n\n<!-- detail-elodie -->\n'
        f'<details><summary>Pour Élodie</summary>\n\n{resume}\n\n- Fichiers : {", ".join(modifies) or "aucun"}'
        f'{lien_commit}{lien_branche}\n- Point de sauvegarde : tag `{os.environ.get("TAG_SAUVEGARDE", "?")}`'
        f'{chr(10) + "- " + note if note else ""}\n</details>')})

    # Récapitulatif à Élodie
    elodie = destinataire_elodie()
    if elodie and EXPEDITEUR['email'] and os.environ.get('BREVO_API_KEY'):
        import html as h
        corps = f'''<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1c2b22;">
  <div style="background:#2e8650;padding:18px;border-radius:12px 12px 0 0;color:#fff;font-size:18px;">🛟 {h.escape(libelle)} — signalement n° {sid}</div>
  <div style="padding:20px;background:#f7f6f2;border-radius:0 0 12px 12px;">
    <p style="margin:0 0 6px;font-size:13px;color:#4a6358;">Réponse de Claude dans l'appli :</p>
    <div style="background:#fff;border-left:4px solid #2e8650;padding:12px 14px;white-space:pre-wrap;">{h.escape(reponse)}</div>
    <p style="margin:16px 0 6px;font-size:13px;color:#4a6358;">Pour toi :</p>
    <div style="background:#fff;padding:12px 14px;white-space:pre-wrap;font-size:14px;">{h.escape(resume)}{h.escape(chr(10) + note) if note else ""}</div>
    <p style="font-size:13px;margin:16px 0 0;">Fichiers modifiés : {h.escape(", ".join(modifies) or "aucun")}
      {"· <b>mis en ligne</b>" if publie else ""}{f" · en attente sur la branche {h.escape(branche)}" if branche else ""}</p>
    <p style="margin:12px 0 0;"><a href="https://github.com/{DEPOT}/issues/{ISSUE}" style="color:#2e8650;">Voir toute la conversation</a>
      · <a href="{LIEN_APP}" style="color:#2e8650;">Ouvrir l'appli</a></p>
    <p style="font-size:12px;color:#8aab97;margin:12px 0 0;">Pour annuler un correctif : demande-le à Claude, ou reviens au tag {h.escape(os.environ.get("TAG_SAUVEGARDE", "?"))}.</p>
  </div></div>'''
        try:
            http('POST', 'https://api.brevo.com/v3/smtp/email', {'api-key': os.environ['BREVO_API_KEY'], 'accept': 'application/json'}, {
                'sender': {'email': EXPEDITEUR['email'], 'name': EXPEDITEUR['name']}, 'to': [elodie],
                'subject': f'🛟 CIDIL - {libelle} (signalement n° {sid})', 'htmlContent': corps})
        except Exception as e:
            print('E-mail récapitulatif non envoyé :', e)
    print(f'statut={etat} publie={publie} fichiers={modifies} {note}')


if __name__ == '__main__':
    {'preparer': preparer, 'publier': publier}[sys.argv[1]]()
