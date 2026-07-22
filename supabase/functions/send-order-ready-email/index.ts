// Fonction Supabase Edge : envoie le "bon de livraison" par email au gestionnaire
// quand l'encadrant technique clique sur "Commande prête".
// La clé Brevo reste secrète (stockée côté serveur), jamais exposée au navigateur.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BREVO_API_KEY = Deno.env.get('BREVO_API_KEY')!;

const EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr';
const EXPEDITEUR_NOM = 'CIDIL Maraîchage';
const DESTINATAIRES = [
  { email: 'comptable@cidil-asso.fr', name: 'Comptable CIDIL' },
  { email: 'coordination@cidil-asso.fr', name: 'Coordination CIDIL' },
];

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
};

function pluriel(qty: number, unite: string) {
  const u = (unite || 'kg').toLowerCase();
  if (qty == null || qty <= 1) return u;
  if (u === 'botte') return 'bottes';
  if (u === 'piece' || u === 'pièce') return 'pièces';
  return u;
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS_HEADERS });

  try {
    const { commande_id } = await req.json();
    if (!commande_id) {
      return new Response(JSON.stringify({ error: 'commande_id manquant' }), { status: 400, headers: CORS_HEADERS });
    }

    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/commandes_clients?id=eq.${commande_id}&select=client_nom,jour_livraison,semaine,items,total`,
      { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}` } }
    );
    const rows = await res.json();
    const cmd = rows[0];
    if (!cmd) {
      return new Response(JSON.stringify({ error: 'Commande introuvable' }), { status: 404, headers: CORS_HEADERS });
    }

    const items = typeof cmd.items === 'string' ? JSON.parse(cmd.items) : (cmd.items || []);
    let lignes = '';
    for (const it of items) {
      if (it.dispo === false) {
        lignes += `<tr><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-decoration:line-through;color:#999;">${it.nom}</td><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-align:right;color:#c0392b;">Non disponible</td></tr>`;
        continue;
      }
      const qty = it.quantite_reelle != null ? it.quantite_reelle : it.quantite;
      const unite = pluriel(qty, it.unite);
      lignes += `<tr><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;">${it.nom}</td><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-align:right;">${qty} ${unite}</td></tr>`;
    }

    const html = `
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">Bon de livraison</h1>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p><strong>${cmd.client_nom}</strong></p>
        <p style="color:#666;font-size:13px;margin-top:-8px;">Livraison : ${cmd.jour_livraison || ''}</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">${lignes}</table>
        </div>
        <p style="font-weight:bold;">Total : ${(cmd.total || 0).toFixed(2)} €</p>
        <p style="font-size:13px;color:#888;">Commande prête, à préparer / livrer.</p>
      </div>
    </div>`;

    const brevoRes = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({
        sender: { email: EXPEDITEUR_EMAIL, name: EXPEDITEUR_NOM },
        to: DESTINATAIRES,
        subject: `CIDIL - Commande prête : ${cmd.client_nom}`,
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
