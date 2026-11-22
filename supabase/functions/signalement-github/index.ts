// Fonction Supabase Edge : transmet les messages de l'encadré « Déclarer un problème » au Claude de dépannage.
// (L'e-mail à Élodie reste envoyé par la fonction signalement-recu, inchangée.)
//
// { id }         : nouveau signalement (trigger de la table signalements)
//                  → fiche GitHub (issue) qui déclenche le workflow .github/workflows/claude-signalement.yml.
// { message_id } : nouvelle réponse de l'équipe dans la conversation (trigger de signalement_messages)
//                  → commentaire sur la fiche, qui relance le workflow.
//
// La fonction relit les lignes elle-même et ignore tout ce qui a plus de 10 minutes : un appel extérieur
// ne peut donc pas faire publier un message arbitraire.
// Jeton GitHub : secret CIDIL_GITHUB_TOKEN (Edge Functions → Secrets), limité aux issues du dépôt.
// Ne touche jamais à signalements.statut (géré par signalement-recu puis par le workflow).

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const GITHUB_TOKEN = Deno.env.get('CIDIL_GITHUB_TOKEN');
const DEPOT = 'elodie24000/logisitique-CIDIL';

const H = { apikey: SERVICE_ROLE_KEY, Authorization: 'Bearer ' + SERVICE_ROLE_KEY };

function recent(iso: string) {
  return Date.now() - new Date(iso).getTime() < 10 * 60 * 1000;
}
async function sbGet(path: string) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: H });
  if (!res.ok) throw new Error(`${path} : ${res.status} ${await res.text()}`);
  return res.json();
}
async function github(chemin: string, body: unknown) {
  const res = await fetch(`https://api.github.com/repos/${DEPOT}/${chemin}`, {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + GITHUB_TOKEN, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json', 'User-Agent': 'cidil-signalements',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`GitHub ${chemin} : ${res.status} ${await res.text()}`);
  return res.json();
}
const citer = (t: string) => '> ' + String(t ?? '').split('\n').join('\n> ');

async function nouveauSignalement(id: number) {
  const [s] = await sbGet(`signalements?id=eq.${id}&select=*`);
  if (!s || s.github_issue || !recent(s.created_at)) return { skipped: true };
  const quand = new Date(s.created_at).toLocaleString('fr-FR', { timeZone: 'Europe/Paris', dateStyle: 'full', timeStyle: 'short' });
  const qui = s.qui || s.role || 'quelqu\'un de l\'équipe';
  const r = await github('issues', {
    title: `🛟 ${qui} : ${String(s.texte).replace(/\s+/g, ' ').slice(0, 70)}`,
    body: [
      `<!-- signalement-app id=${s.id} -->`,
      `**Signalé par : ${qui}** (rôle \`${s.role || '?'}\`) — page « ${s.page || '?'} » — ${quand}`,
      '', citer(s.texte), '',
      '<details><summary>Détails techniques</summary>', '', '```', s.contexte || '', '```', '</details>',
      '', `_Signalement n° ${s.id} envoyé depuis l'appli. Les réponses de Claude s'affichent dans l'encadré « Déclarer un problème »._`,
    ].join('\n'),
  });
  await fetch(`${SUPABASE_URL}/rest/v1/signalements?id=eq.${s.id}`, {
    method: 'PATCH', headers: { ...H, 'Content-Type': 'application/json' }, body: JSON.stringify({ github_issue: r.number }),
  });
  return { ok: true, issue: r.number };
}

async function nouveauMessage(messageId: number) {
  const [m] = await sbGet(`signalement_messages?id=eq.${messageId}&select=*`);
  if (!m || m.auteur === 'Claude' || !recent(m.created_at)) return { skipped: true };
  const [s] = await sbGet(`signalements?id=eq.${m.signalement_id}&select=id,github_issue`);
  if (!s?.github_issue) return { skipped: true, raison: 'pas de fiche GitHub' };
  await github(`issues/${s.github_issue}/comments`, {
    body: `<!-- message-app id=${m.id} -->\n**${m.auteur}** :\n\n${citer(m.texte)}`,
  });
  return { ok: true };
}

Deno.serve(async (req) => {
  const repondre = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
  try {
    if (!GITHUB_TOKEN) return repondre({ error: 'Secret CIDIL_GITHUB_TOKEN absent' }, 500);
    const body = await req.json();
    if (body.message_id) return repondre(await nouveauMessage(Number(body.message_id)));
    return repondre(await nouveauSignalement(Number(body.id)));
  } catch (e) {
    console.error(e);
    return repondre({ error: String(e) }, 500);
  }
});
