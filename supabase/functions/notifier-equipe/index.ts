// Fonction Supabase Edge : notification push (bandeau sur le téléphone, application fermée)
// aux téléphones de l'équipe inscrits (push_subscriptions.role = 'encadrant'),
// à chaque nouvelle commande ou nouveau client.
//
// Appelée par les triggers de la base (voir migration notifier_equipe_triggers) avec
// { table: 'commandes_clients' | 'clients', id }. La fonction relit la ligne elle-même et
// n'envoie rien si elle a plus de 10 minutes : un appel extérieur ne peut donc pas faire
// envoyer un message arbitraire.
// Appelée aussi par l'application avec { test: true, endpoint } pour le bouton
// « Tester la notification » (n'envoie qu'au téléphone qui a demandé le test).
//
// Clé privée VAPID (associée à VAPID_PUBLIC de index.html) : secret VAPID_PRIVATE_KEY des
// Edge Functions s'il existe, sinon lue dans le Vault (secret « vapid_private_key ») via la
// fonction SQL public.vapid_private_key(), réservée au rôle service.

import webpush from 'npm:web-push@3.6.7';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const VAPID_PUBLIC_KEY = 'BCYNvEKKGUTnY12GwTJl1ChT-353ZZo7RFM6V_Xcbn2eQp_2upUP2Qo39GmdNI8FgWG11qoOHIoi_TO7w9p22Qw';
const VAPID_SUBJECT = 'mailto:plassin.elodie24@gmail.com';
const URL_APP = 'https://elodie24000.github.io/logisitique-CIDIL/';
const ROLES_EQUIPE = ['encadrant'];

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://elodie24000.github.io',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
};

const H = { apikey: SERVICE_ROLE_KEY, Authorization: 'Bearer ' + SERVICE_ROLE_KEY };

async function sbGet(path: string) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: H });
  if (!res.ok) throw new Error(`${path} : ${res.status} ${await res.text()}`);
  return res.json();
}

async function clePriveeVapid(): Promise<string | null> {
  const env = Deno.env.get('VAPID_PRIVATE_KEY');
  if (env) return env;
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/vapid_private_key`, {
    method: 'POST', headers: { ...H, 'Content-Type': 'application/json' }, body: '{}',
  });
  if (!res.ok) return null;
  return await res.json();
}

async function sbDelete(path: string) {
  await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { method: 'DELETE', headers: H }).catch(() => {});
}

function pluriel(n: number, mot: string) {
  return `${n} ${mot}${n > 1 ? 's' : ''}`;
}

function recent(iso: string | null) {
  return !!iso && Date.now() - new Date(iso).getTime() < 10 * 60 * 1000;
}

// Contenu du bandeau selon ce qui vient d'arriver
async function construireMessage(table: string, id: number) {
  if (table === 'commandes_clients') {
    const [c] = await sbGet(`commandes_clients?id=eq.${id}&select=client_nom,items,jour_livraison,mode_livraison,created_at`);
    if (!c || !recent(c.created_at)) return null;
    const items = typeof c.items === 'string' ? JSON.parse(c.items) : (c.items || []);
    const quand = c.mode_livraison === 'retrait' ? `retrait sur place ${c.jour_livraison || ''}` : `livraison ${c.jour_livraison || ''}`;
    return {
      title: `🛒 Nouvelle commande : ${c.client_nom}`,
      body: `${pluriel(items.length, 'article')} — ${quand.trim()}. Touchez pour ouvrir l'application.`,
      tag: `cidil-commande-${id}`,
    };
  }
  if (table === 'clients') {
    const [c] = await sbGet(`clients?id=eq.${id}&select=nom,note,created_at`);
    if (!c || !recent(c.created_at)) return null;
    const enLigne = (c.note || '').startsWith('Inscription en ligne');
    return {
      title: `🆕 Nouveau client : ${c.nom}`,
      body: enLigne ? `Inscription en ligne, fiche à vérifier. Touchez pour ouvrir l'application.` : `Touchez pour ouvrir l'application.`,
      tag: `cidil-client-${id}`,
    };
  }
  return null;
}

async function envoyer(subs: { id: number; subscription: string }[], message: Record<string, string>) {
  const payload = JSON.stringify({ ...message, url: URL_APP });
  const dejaVus = new Set<string>();
  let ok = 0, echecs = 0;
  for (const s of subs) {
    let info;
    try { info = JSON.parse(s.subscription); } catch { continue; }
    if (!info?.endpoint || dejaVus.has(info.endpoint)) continue;
    dejaVus.add(info.endpoint);
    try {
      await webpush.sendNotification(info, payload, { TTL: 24 * 3600, urgency: 'high' });
      ok++;
    } catch (e) {
      echecs++;
      const code = (e as { statusCode?: number }).statusCode;
      console.error('Echec push', s.id, code);
      // Abonnement expiré (téléphone réinitialisé, notifications désactivées…) : on le retire
      if (code === 404 || code === 410) await sbDelete(`push_subscriptions?id=eq.${s.id}`);
    }
  }
  return { ok, echecs };
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS_HEADERS });
  const repondre = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } });
  try {
    const clePrivee = await clePriveeVapid();
    if (!clePrivee) return repondre({ error: 'Clé privée VAPID introuvable' }, 500);
    webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, clePrivee);
    const body = await req.json();

    if (body.test) {
      const subs = (await sbGet(`push_subscriptions?select=id,subscription&role=in.(${ROLES_EQUIPE.join(',')})`))
        .filter((s: { subscription: string }) => { try { return JSON.parse(s.subscription).endpoint === body.endpoint; } catch { return false; } });
      if (!subs.length) return repondre({ error: 'Ce téléphone n\'est pas inscrit aux alertes' }, 404);
      const r = await envoyer(subs, {
        title: '✅ Test réussi',
        body: 'Vous recevrez un bandeau comme celui-ci à chaque nouvelle commande ou nouveau client.',
        tag: 'cidil-test',
      });
      return repondre(r);
    }

    const message = await construireMessage(String(body.table), Number(body.id));
    if (!message) return repondre({ skipped: true });
    const subs = await sbGet(`push_subscriptions?select=id,subscription&role=in.(${ROLES_EQUIPE.join(',')})`);
    const r = await envoyer(subs, message);
    console.log(`${body.table} ${body.id} : ${r.ok} envoi(s), ${r.echecs} échec(s)`);
    return repondre(r);
  } catch (e) {
    console.error(e);
    return repondre({ error: String(e) }, 500);
  }
});
