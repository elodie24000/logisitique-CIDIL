// Fonction Supabase Edge : prévient Élodie par e-mail dès qu'une personne de l'équipe
// (Atika, Amélie…) déclare un problème avec le bouton « 🛟 Déclarer un problème » de l'appli.
//
// Appelée par le trigger de la table signalements (migration 20261120_signalements) avec { id }.
// La fonction relit la ligne elle-même, n'envoie rien si elle a plus de 10 minutes ou si elle a
// déjà été transmise : un appel extérieur ne peut donc pas faire envoyer un message arbitraire.
// Canal SÉPARÉ des alertes équipe (notifier-equipe) : rien n'est envoyé aux encadrantes ici.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BREVO_API_KEY = Deno.env.get('BREVO_API_KEY')!;

const EXPEDITEUR = { email: 'eti.maraichage1@cidil-asso.fr', name: 'CIDIL Maraîchage' };
const GESTIONNAIRE = { email: 'plassin.elodie24@gmail.com', name: 'Elodie' };

const H = { apikey: SERVICE_ROLE_KEY, Authorization: 'Bearer ' + SERVICE_ROLE_KEY };

function echapper(t: string) {
  return String(t ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

Deno.serve(async (req) => {
  const repondre = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
  try {
    const { id } = await req.json();
    const res = await fetch(`${SUPABASE_URL}/rest/v1/signalements?id=eq.${Number(id)}&select=*`, { headers: H });
    const [s] = await res.json();
    if (!s || s.statut !== 'nouveau' || Date.now() - new Date(s.created_at).getTime() > 10 * 60 * 1000) {
      return repondre({ skipped: true });
    }
    const quand = new Date(s.created_at).toLocaleString('fr-FR', { timeZone: 'Europe/Paris', dateStyle: 'full', timeStyle: 'short' });
    const qui = s.qui || s.role || 'quelqu\'un de l\'équipe';
    const html = `
      <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
        <div style="background:#2e8650;padding:20px;text-align:center;border-radius:12px 12px 0 0;">
          <h1 style="color:#fff;font-size:19px;margin:0;">🛟 Problème déclaré par ${echapper(qui)}</h1>
        </div>
        <div style="padding:22px;background:#f7f6f2;border-radius:0 0 12px 12px;color:#1c2b22;">
          <p style="font-size:13px;color:#4a6358;margin:0 0 12px;">${echapper(quand)} · page « ${echapper(s.page || '?')} »</p>
          <div style="background:#fff;border-left:4px solid #2e8650;padding:14px 16px;font-size:16px;line-height:1.5;white-space:pre-wrap;">${echapper(s.texte)}</div>
          <p style="font-size:12px;color:#8aab97;margin:16px 0 0;">Signalement n° ${s.id} — détails techniques :<br>${echapper(s.contexte || '')}</p>
        </div>
      </div>`;
    const envoi = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ sender: EXPEDITEUR, to: [GESTIONNAIRE], subject: `🛟 CIDIL - ${qui} déclare un problème`, htmlContent: html }),
    });
    if (!envoi.ok) throw new Error(`Brevo ${envoi.status} ${await envoi.text()}`);
    await fetch(`${SUPABASE_URL}/rest/v1/signalements?id=eq.${s.id}`, {
      method: 'PATCH', headers: { ...H, 'Content-Type': 'application/json' },
      body: JSON.stringify({ statut: 'transmis' }),
    });
    return repondre({ ok: true });
  } catch (e) {
    console.error(e);
    return repondre({ error: String(e) }, 500);
  }
});
