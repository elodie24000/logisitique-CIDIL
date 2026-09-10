// Fonction Supabase Edge : envoie par email le récapitulatif mensuel de veille
// concurrentielle (ce que font les autres logiciels/plateformes de vente en ligne
// de légumes), préparé par une routine automatique. Destinataire fixe : Elodie.
// La clé Brevo reste secrète (stockée côté serveur), jamais exposée au navigateur.

const BREVO_API_KEY = Deno.env.get('BREVO_API_KEY')!;

const EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr';
const EXPEDITEUR_NOM = 'CIDIL Maraîchage';
const DESTINATAIRE = { email: 'plassin.elodie24@gmail.com', name: 'Elodie' };

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS_HEADERS });

  try {
    const { sujet, contenu_html } = await req.json();
    if (!sujet || !contenu_html) {
      return new Response(JSON.stringify({ error: 'sujet ou contenu_html manquant' }), { status: 400, headers: CORS_HEADERS });
    }

    const html = `
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">Veille concurrentielle CIDIL</h1>
        <p style="color:#c9e5d2;font-size:13px;margin:4px 0 0;">Récapitulatif mensuel</p>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        ${contenu_html}
      </div>
    </div>`;

    const brevoRes = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({
        sender: { email: EXPEDITEUR_EMAIL, name: EXPEDITEUR_NOM },
        to: [DESTINATAIRE],
        subject: sujet,
        htmlContent: html,
      }),
    });

    if (!brevoRes.ok) {
      const errTxt = await brevoRes.text();
      return new Response(JSON.stringify({ error: 'Echec envoi Brevo', detail: errTxt }), { status: 502, headers: CORS_HEADERS });
    }

    return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: CORS_HEADERS });
  }
});
