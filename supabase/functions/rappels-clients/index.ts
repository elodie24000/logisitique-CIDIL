// Fonction Supabase Edge : rappels aux clients, à l'heure de Paris, sans retard.
//
// Remplace les envois programmés de GitHub Actions, qui partaient avec plusieurs heures
// de retard (ex. rappel « dernière chance, clôture à 9h » reçu à 12h38).
// Appelée toutes les 10 minutes par pg_cron (job « rappels-clients », voir migration
// rappels_clients_cron). Elle ne reçoit aucun paramètre utile : c'est elle qui regarde
// l'heure de Paris et décide quoi envoyer.
//
//   lundi    7h00–8h59  → rappel « dernière chance » (livraison mardi, clôture lundi 9h)
//   mercredi 7h00–8h59  → rappel « dernière chance » (livraison jeudi, clôture mercredi 9h)
//   vendredi 10h00–13h59 → « les légumes de la semaine sont disponibles » (email + push)
//   chaque jour 9h30–11h59 → veille : alerte la gestionnaire si un rappel du jour n'est pas parti
//
// Chaque envoi est inscrit dans la table rappels_envoyes (clé unique par jour) : il ne
// part qu'une seule fois, même si la fonction est appelée plusieurs fois ou de l'extérieur.
//
// { apercu: true } : ne fait rien, renvoie ce qui serait envoyé maintenant (pour vérifier).
// { test: 'cloture' | 'vendredi' } : envoie le message à la gestionnaire uniquement
// (au plus une fois par heure et par type), pour voir le rendu réel.

import webpush from 'npm:web-push@3.6.7';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BREVO_API_KEY = Deno.env.get('BREVO_API_KEY')!;
const VAPID_PUBLIC_KEY = 'BCYNvEKKGUTnY12GwTJl1ChT-353ZZo7RFM6V_Xcbn2eQp_2upUP2Qo39GmdNI8FgWG11qoOHIoi_TO7w9p22Qw';
const VAPID_SUBJECT = 'mailto:plassin.elodie24@gmail.com';

const EXPEDITEUR = { email: 'eti.maraichage1@cidil-asso.fr', name: 'CIDIL Maraîchage' };
const GESTIONNAIRE = { email: 'plassin.elodie24@gmail.com', name: 'Elodie' };
const LIEN_COMMANDE = 'https://elodie24000.github.io/logisitique-CIDIL/?commande';
const SITE_URL = 'https://elodie24000.github.io/logisitique-CIDIL/';

const H = { apikey: SERVICE_ROLE_KEY, Authorization: 'Bearer ' + SERVICE_ROLE_KEY };

// ── Heure de Paris ──
function maintenantParis() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('fr-FR', {
      timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', weekday: 'short', hour12: false,
    }).formatToParts(new Date()).map((p) => [p.type, p.value]),
  );
  const jours: Record<string, number> = { 'lun.': 1, 'mar.': 2, 'mer.': 3, 'jeu.': 4, 'ven.': 5, 'sam.': 6, 'dim.': 0 };
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    jour: jours[parts.weekday] ?? -1,
    minutes: Number(parts.hour) * 60 + Number(parts.minute),
  };
}

function lundiSuivant(dateIso: string) {
  const d = new Date(dateIso + 'T12:00:00Z');
  const delta = ((8 - d.getUTCDay()) % 7) || 7;
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
}

// ── Base ──
async function sbGet(path: string) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: H });
  if (!res.ok) throw new Error(`${path} : ${res.status} ${await res.text()}`);
  return res.json();
}
async function sbPost(path: string, body: unknown, prefer = 'return=representation') {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method: 'POST', headers: { ...H, 'Content-Type': 'application/json', Prefer: prefer }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} : ${res.status} ${await res.text()}`);
  return res.json();
}

// Réserve une clé d'envoi ; false si elle existe déjà (déjà envoyé).
async function reserver(cle: string) {
  const rows = await sbPost('rappels_envoyes?on_conflict=cle', { cle }, 'resolution=ignore-duplicates,return=representation');
  return rows.length > 0;
}
async function noter(cle: string, detail: unknown) {
  await fetch(`${SUPABASE_URL}/rest/v1/rappels_envoyes?cle=eq.${encodeURIComponent(cle)}`, {
    method: 'PATCH', headers: { ...H, 'Content-Type': 'application/json' }, body: JSON.stringify({ detail }),
  });
}
async function dejaEnvoye(cle: string) {
  const rows = await sbGet(`rappels_envoyes?cle=eq.${encodeURIComponent(cle)}&select=cle`);
  return rows.length > 0;
}

// ── Emails (Brevo) ──
async function envoyerEmail(to: { email: string; name: string }, sujet: string, html: string) {
  const res = await fetch('https://api.brevo.com/v3/smtp/email', {
    method: 'POST',
    headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
    body: JSON.stringify({ sender: EXPEDITEUR, to: [to], subject: sujet, htmlContent: html }),
  });
  if (!res.ok) throw new Error(`Brevo ${res.status} ${await res.text()}`);
}

function gabarit(contenu: string) {
  return `
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#2e8650;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">CIDIL Maraîchage</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        ${contenu}
        <p style="text-align:center;margin:28px 0;">
          <a href="${LIEN_COMMANDE}" style="background:#2e8650;color:#fff;padding:14px 28px;
          border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;">Passer ma commande</a>
        </p>
        <p style="font-size:13px;color:#888;">À bientôt,<br>L'équipe CIDIL</p>
      </div>
    </div>`;
}

function echapper(t: string) {
  return String(t ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function mailCloture(nom: string, jourLivraison: string, jourCloture: string) {
  return gabarit(`
    <p>Bonjour ${echapper(nom)},</p>
    <p><strong>Dernière chance</strong> pour passer votre commande en vue de la livraison de <strong>${jourLivraison}</strong> !</p>
    <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
      <p style="margin:0;font-weight:bold;">⏰ Les commandes ferment aujourd'hui (${jourCloture}) à 9h.</p>
    </div>`);
}

function pluriel(qty: number | null, unite: string | null) {
  const u = (unite || 'kg').toLowerCase();
  if (qty == null || qty <= 1) return u;
  if (u === 'botte') return 'bottes';
  if (u === 'piece' || u === 'pièce') return 'pièces';
  return u;
}

type Legume = { nom: string; kg_dispo: number | null; prix_kg: number | null; unite: string | null; famille?: string | null; semaine?: string };

function blocLegumes(legumes: Legume[]) {
  if (!legumes.length) return '<p>La liste des légumes de la semaine sera bientôt disponible dans l\'application.</p>';
  const lignes = legumes.map((l) => {
    const prix = l.prix_kg ? ` · ${Number(l.prix_kg).toFixed(2)} €/${l.unite || 'kg'}` : '';
    return `<tr><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;">${echapper(l.nom)}</td>`
      + `<td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-align:right;color:#555;">${l.kg_dispo ?? ''} ${pluriel(l.kg_dispo, l.unite)}${prix}</td></tr>`;
  }).join('');
  return `<table style="width:100%;border-collapse:collapse;font-size:14px;">${lignes}</table>`;
}

function mailVendredi(nom: string, legumesHtml: string) {
  return gabarit(`
    <p>Bonjour ${echapper(nom)},</p>
    <p>Voici les légumes disponibles pour la semaine à venir. Pensez à passer votre commande !</p>
    <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">${legumesHtml}</div>
    <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
      <p style="margin:0 0 8px;font-weight:bold;">📅 Quand commander ?</p>
      <p style="margin:0 0 4px;">Livraison le <strong>mardi</strong> → commandez avant <strong>lundi 9h</strong></p>
      <p style="margin:0;">Livraison le <strong>jeudi</strong> → commandez avant <strong>mercredi 9h</strong></p>
    </div>`);
}

// Légumes de la semaine ciblée ; si l'encadrant ne les a pas saisis, reprise de la dernière semaine
async function legumesSemaine(semaine: string, dupliquer: boolean): Promise<Legume[]> {
  const rows: Legume[] = await sbGet(`legumes?semaine=eq.${semaine}&order=nom.asc&select=nom,kg_dispo,prix_kg,unite`);
  if (rows.length) return rows;
  const prev: Legume[] = await sbGet(`legumes?semaine=lt.${semaine}&order=semaine.desc&limit=80&select=nom,kg_dispo,prix_kg,unite,famille,semaine`);
  if (!prev.length) return [];
  const derniere = prev.filter((r) => r.semaine === prev[0].semaine).sort((a, b) => a.nom.localeCompare(b.nom, 'fr'));
  if (dupliquer) {
    await sbPost('legumes', derniere.map((l) => ({
      nom: l.nom, kg_dispo: l.kg_dispo, prix_kg: l.prix_kg, semaine, unite: l.unite || 'kg', famille: l.famille || '',
    })));
  }
  return derniere;
}

async function clientsAvecEmail(): Promise<{ nom: string; email: string }[]> {
  const rows = await sbGet('clients?select=nom,email&email=not.is.null&cat=neq.Interne');
  return rows.filter((c: { email: string }) => /\S+@\S+\.\S+/.test(c.email || ''));
}

async function envoyerEmails(clients: { nom: string; email: string }[], sujet: string, html: (nom: string) => string) {
  let ok = 0; const echecs: string[] = [];
  for (const c of clients) {
    try { await envoyerEmail({ email: c.email.trim(), name: c.nom }, sujet, html(c.nom)); ok++; }
    catch (e) { echecs.push(`${c.email} : ${String(e).slice(0, 120)}`); }
  }
  return { ok, echecs };
}

// ── Notifications push ──
async function clePriveeVapid(): Promise<string | null> {
  const env = Deno.env.get('VAPID_PRIVATE_KEY');
  if (env) return env;
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/vapid_private_key`, {
    method: 'POST', headers: { ...H, 'Content-Type': 'application/json' }, body: '{}',
  });
  return res.ok ? await res.json() : null;
}

async function envoyerPush(message: Record<string, string>) {
  const cle = await clePriveeVapid();
  if (!cle) return { ok: 0, echecs: 1, erreur: 'clé VAPID introuvable' };
  webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, cle);
  const subs = await sbGet('push_subscriptions?select=id,subscription');
  const payload = JSON.stringify({ ...message, url: LIEN_COMMANDE });
  const vus = new Set<string>();
  let ok = 0, echecs = 0;
  for (const s of subs) {
    let info;
    try { info = JSON.parse(s.subscription); } catch { continue; }
    if (!info?.endpoint || vus.has(info.endpoint)) continue;
    vus.add(info.endpoint);
    try { await webpush.sendNotification(info, payload, { TTL: 6 * 3600, urgency: 'high' }); ok++; }
    catch (e) {
      echecs++;
      const code = (e as { statusCode?: number }).statusCode;
      if (code === 404 || code === 410) {
        await fetch(`${SUPABASE_URL}/rest/v1/push_subscriptions?id=eq.${s.id}`, { method: 'DELETE', headers: H }).catch(() => {});
      }
    }
  }
  return { ok, echecs };
}

// ── Les envois ──
const CLOTURES: Record<number, { livraison: string; cloture: string }> = {
  1: { livraison: 'mardi', cloture: 'lundi' },
  3: { livraison: 'jeudi', cloture: 'mercredi' },
};

async function rappelCloture(jour: number, destinataires?: { nom: string; email: string }[]) {
  const c = CLOTURES[jour] || CLOTURES[1];
  const clients = destinataires ?? await clientsAvecEmail();
  const mails = await envoyerEmails(clients, `CIDIL - Dernière chance pour commander (livraison ${c.livraison})`,
    (nom) => mailCloture(nom, c.livraison, c.cloture));
  const push = destinataires ? { ok: 0, echecs: 0 } : await envoyerPush({
    title: 'CIDIL Maraîchage 🥕',
    body: `Dernière chance pour commander pour la livraison de ${c.livraison} ! Clôture aujourd'hui à 9h.`,
    tag: `cidil-cloture-${c.livraison}`,
  });
  return { emails: mails, push };
}

async function ouvertureVendredi(dateParis: string, destinataires?: { nom: string; email: string }[]) {
  const semaine = lundiSuivant(dateParis);
  const legumes = await legumesSemaine(semaine, !destinataires);
  const html = blocLegumes(legumes);
  const clients = destinataires ?? await clientsAvecEmail();
  const mails = await envoyerEmails(clients, 'CIDIL - Les légumes de la semaine sont disponibles', (nom) => mailVendredi(nom, html));
  const push = destinataires ? { ok: 0, echecs: 0 } : await envoyerPush({
    title: 'CIDIL Maraîchage 🥕',
    body: 'Les légumes de la semaine sont disponibles ! Commandez avant lundi 9h (livraison mardi) ou mercredi 9h (livraison jeudi).',
    tag: 'cidil-ouverture-vendredi',
  });
  return { semaine, legumes: legumes.length, emails: mails, push };
}

// Veille quotidienne : site en ligne + rappels du jour bien partis
async function veille(now: ReturnType<typeof maintenantParis>) {
  const problemes: string[] = [];
  try {
    const r = await fetch(SITE_URL, { redirect: 'follow' });
    if (r.status !== 200) problemes.push(`Le site répond avec le code ${r.status} (les clients ne peuvent peut-être plus commander).`);
  } catch (e) { problemes.push(`Le site ne répond pas : ${String(e).slice(0, 120)}`); }
  if (CLOTURES[now.jour]) {
    const [r] = await sbGet(`rappels_envoyes?cle=eq.cloture-${now.date}&select=detail`);
    if (!r) problemes.push(`Le rappel « dernière chance » de ce ${CLOTURES[now.jour].cloture} matin n'est pas parti.`);
    else if (!r.detail) problemes.push(`Le rappel « dernière chance » de ce ${CLOTURES[now.jour].cloture} matin a démarré mais ne s'est pas terminé.`);
  }
  // Emails non partis lors des envois des dernières 24 h
  const depuis = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const avecEchecs = (await sbGet(`rappels_envoyes?envoye_at=gte.${depuis}&select=cle,detail`))
    .filter((r: { detail: { emails?: { echecs?: string[] } } | null }) => (r.detail?.emails?.echecs?.length ?? 0) > 0);
  for (const r of avecEchecs) {
    problemes.push(`Envoi « ${r.cle} » : ${r.detail.emails.echecs.length} email(s) non parti(s) — ${r.detail.emails.echecs.slice(0, 3).join(' ; ')}`);
  }
  if (problemes.length) {
    await envoyerEmail(GESTIONNAIRE, '⚠ CIDIL - Problème détecté par la veille', gabarit(
      `<p>Bonjour,</p><p>La vérification du ${now.date} a trouvé :</p><ul>${problemes.map((p) => `<li>${echapper(p)}</li>`).join('')}</ul>
       <p>Vous pouvez demander à Claude de regarder.</p>`));
  }
  return { problemes };
}

Deno.serve(async (req) => {
  const repondre = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
  try {
    const body = await req.json().catch(() => ({}));
    const now = maintenantParis();
    const fenetreCloture = !!CLOTURES[now.jour] && now.minutes >= 7 * 60 && now.minutes < 9 * 60;
    const fenetreVendredi = now.jour === 5 && now.minutes >= 10 * 60 && now.minutes < 14 * 60;
    const fenetreVeille = now.minutes >= 9 * 60 + 30 && now.minutes < 12 * 60;

    if (body.apercu) {
      return repondre({ paris: now, fenetreCloture, fenetreVendredi, fenetreVeille,
        dejaCloture: await dejaEnvoye(`cloture-${now.date}`), dejaVendredi: await dejaEnvoye(`vendredi-${now.date}`) });
    }

    if (body.test === 'cloture' || body.test === 'vendredi') {
      const heure = Math.floor(now.minutes / 60);
      if (!(await reserver(`test-${body.test}-${now.date}-${heure}`))) return repondre({ skipped: 'test déjà envoyé cette heure-ci' });
      const r = body.test === 'cloture'
        ? await rappelCloture(CLOTURES[now.jour] ? now.jour : 1, [{ nom: 'Elodie (test)', email: GESTIONNAIRE.email }])
        : await ouvertureVendredi(now.date, [{ nom: 'Elodie (test)', email: GESTIONNAIRE.email }]);
      return repondre({ test: body.test, ...r });
    }

    const fait: Record<string, unknown> = {};
    if (fenetreCloture && await reserver(`cloture-${now.date}`)) {
      const r = await rappelCloture(now.jour);
      await noter(`cloture-${now.date}`, r);
      console.log(`cloture-${now.date} : ${r.emails.ok} email(s), ${r.emails.echecs.length} échec(s), ${r.push.ok} push`);
      fait.cloture = r;
    }
    if (fenetreVendredi && await reserver(`vendredi-${now.date}`)) {
      const r = await ouvertureVendredi(now.date);
      await noter(`vendredi-${now.date}`, r);
      console.log(`vendredi-${now.date} : ${r.legumes} légume(s), ${r.emails.ok} email(s), ${r.emails.echecs.length} échec(s), ${r.push.ok} push`);
      fait.vendredi = r;
    }
    if (fenetreVeille && await reserver(`veille-${now.date}`)) {
      const r = await veille(now);
      await noter(`veille-${now.date}`, r);
      console.log(`veille-${now.date} : ${r.problemes.length} problème(s)`);
      fait.veille = r;
    }
    return repondre({ paris: now, ...fait });
  } catch (e) {
    console.error(e);
    return repondre({ error: String(e) }, 500);
  }
});
