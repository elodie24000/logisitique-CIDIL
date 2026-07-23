// Fonction Supabase Edge : envoie le "bon de livraison" par email au gestionnaire
// quand l'encadrant technique clique sur "Commande prête".
// La clé Brevo reste secrète (stockée côté serveur), jamais exposée au navigateur.

import { PDFDocument, StandardFonts } from 'npm:pdf-lib@1.17.1';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BREVO_API_KEY = Deno.env.get('BREVO_API_KEY')!;

const EXPEDITEUR_EMAIL = 'eti.maraichage1@cidil-asso.fr';
const EXPEDITEUR_NOM = 'CIDIL Maraîchage';
const DESTINATAIRES = [
  { email: 'comptable@cidil-asso.fr', name: 'Comptable CIDIL' },
  { email: 'coordination@cidil-asso.fr', name: 'Coordination CIDIL' },
];
const CC = [
  { email: 'eti.maraichage1@cidil-asso.fr', name: 'CIDIL Maraîchage' },
];

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://elodie24000.github.io',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
};

function pluriel(qty: number, unite: string) {
  const u = (unite || 'kg').toLowerCase();
  if (qty == null || qty <= 1) return u;
  if (u === 'botte') return 'bottes';
  if (u === 'piece' || u === 'pièce') return 'pièces';
  return u;
}

function toBase64(bytes: Uint8Array) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function sansAccents(s: string) {
  return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '');
}

async function buildPdfBase64(numeroBL: number, dateStr: string, cmd: any, items: any[]) {
  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([420, 595]);
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica);
  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  let y = 550;
  const left = 40;

  page.drawText('BON DE LIVRAISON', { x: left, y, size: 18, font: fontBold });
  y -= 22;
  page.drawText(`N ${numeroBL}`, { x: left, y, size: 12, font });
  y -= 18;
  page.drawText(`Date : ${sansAccents(dateStr)}`, { x: left, y, size: 10, font });
  y -= 24;
  page.drawText(sansAccents(cmd.client_nom), { x: left, y, size: 13, font: fontBold });
  y -= 16;
  page.drawText(`Livraison : ${sansAccents(cmd.jour_livraison || '')}`, { x: left, y, size: 10, font });
  y -= 26;

  for (const it of items) {
    if (y < 60) break;
    if (it.dispo === false) {
      page.drawText(sansAccents(it.nom), { x: left, y, size: 10, font });
      page.drawText('Non disponible', { x: 300, y, size: 10, font });
      y -= 16;
      continue;
    }
    const qty = it.quantite_reelle != null ? it.quantite_reelle : it.quantite;
    const unite = pluriel(qty, it.unite);
    page.drawText(sansAccents(it.nom), { x: left, y, size: 10, font });
    page.drawText(`${qty} ${sansAccents(unite)}`, { x: 300, y, size: 10, font });
    y -= 16;
  }

  y -= 10;
  page.drawText(`Total : ${(cmd.total || 0).toFixed(2)} EUR`, { x: left, y, size: 12, font: fontBold });

  const bytes = await pdfDoc.save();
  return toBase64(bytes);
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS_HEADERS });

  try {
    const { commande_id } = await req.json();
    if (!commande_id) {
      return new Response(JSON.stringify({ error: 'commande_id manquant' }), { status: 400, headers: CORS_HEADERS });
    }

    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/commandes_clients?id=eq.${commande_id}&select=client_nom,jour_livraison,semaine,items,total,numero_bl`,
      { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}` } }
    );
    const rows = await res.json();
    const cmd = rows[0];
    if (!cmd) {
      return new Response(JSON.stringify({ error: 'Commande introuvable' }), { status: 404, headers: CORS_HEADERS });
    }

    // Attribue un numéro de BL séquentiel (1, 2, 3...) la première fois seulement
    let numeroBL = cmd.numero_bl;
    if (!numeroBL) {
      const countRes = await fetch(
        `${SUPABASE_URL}/rest/v1/commandes_clients?numero_bl=not.is.null&select=numero_bl`,
        { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}`, Prefer: 'count=exact' } }
      );
      const existants = await countRes.json();
      numeroBL = existants.length + 1;
      await fetch(`${SUPABASE_URL}/rest/v1/commandes_clients?id=eq.${commande_id}`, {
        method: 'PATCH',
        headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero_bl: numeroBL }),
      });
    }

    const dateStr = new Date().toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

    const items = typeof cmd.items === 'string' ? JSON.parse(cmd.items) : (cmd.items || []);
    let lignes = '';
    for (const it of items) {
      if (it.dispo === false) {
        lignes += `<tr><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-decoration:line-through;color:#999;">${it.nom}</td><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-align:right;color:#c0392b;">Non disponible</td></tr>`;
        continue;
      }
      const qty = it.quantite_reelle != null ? it.quantite_reelle : it.quantite;
      const unite = pluriel(qty, it.unite);
      const prixUnit = it.prix_kg;
      const sousTotal = prixUnit != null ? qty * prixUnit : null;
      const prixTxt = prixUnit != null
        ? `<div style="font-size:12px;color:#888;">${prixUnit.toFixed(2)} €/${it.unite || 'kg'}${sousTotal != null ? ' · ' + sousTotal.toFixed(2) + ' €' : ''}</div>`
        : '';
      lignes += `<tr><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;">${it.nom}${prixTxt}</td><td style="padding:6px 0;border-bottom:1px solid #e5e3dc;text-align:right;vertical-align:top;">${qty} ${unite}</td></tr>`;
    }

    const html = `
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">BON DE LIVRAISON</h1>
        <p style="color:#c9e5d2;font-size:13px;margin:4px 0 0;">N° ${numeroBL}</p>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p style="color:#666;font-size:13px;margin:0 0 12px;">Date : ${dateStr}</p>
        <p><strong>${cmd.client_nom}</strong></p>
        <p style="color:#666;font-size:13px;margin-top:-8px;">Livraison : ${cmd.jour_livraison || ''}</p>
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin:18px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">${lignes}</table>
        </div>
        <p style="font-weight:bold;">Total : ${(cmd.total || 0).toFixed(2)} €</p>
        <p style="font-size:13px;color:#888;">Commande prête, à préparer / livrer.</p>
      </div>
    </div>`;

    let pdfBase64: string | null = null;
    let pdfErreur: string | null = null;
    try {
      pdfBase64 = await buildPdfBase64(numeroBL, dateStr, cmd, items);
    } catch (e) {
      pdfErreur = String(e);
    }

    const nomFichier = sansAccents(cmd.client_nom).replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const emailBody: any = {
      sender: { email: EXPEDITEUR_EMAIL, name: EXPEDITEUR_NOM },
      to: DESTINATAIRES,
      cc: CC,
      subject: `CIDIL - BL n°${numeroBL} - Commande prête : ${cmd.client_nom}`,
      htmlContent: html,
    };
    if (pdfBase64) {
      emailBody.attachment = [{ content: pdfBase64, name: `BL_n${numeroBL}_${nomFichier}.pdf` }];
    }

    const brevoRes = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
      body: JSON.stringify(emailBody),
    });

    if (!brevoRes.ok) {
      const errTxt = await brevoRes.text();
      return new Response(JSON.stringify({ error: 'Echec envoi Brevo', detail: errTxt }), { status: 502, headers: CORS_HEADERS });
    }

    return new Response(JSON.stringify({ ok: true, pdf_attache: !!pdfBase64, pdf_erreur: pdfErreur }), { headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: CORS_HEADERS });
  }
});
