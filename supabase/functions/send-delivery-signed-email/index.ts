// Fonction Supabase Edge : appelée par l'interface Livreur quand le client signe
// électroniquement le bon de livraison. Marque la commande comme livrée, régénère
// le bon de livraison avec la signature et l'envoie par email à la compta/coordination
// (comme pour "commande prête") ainsi qu'au client si son email est connu.
// La clé Brevo reste secrète (stockée côté serveur), jamais exposée au navigateur.

import { PDFDocument, PDFFont, PDFPage, StandardFonts, rgb } from 'npm:pdf-lib@1.17.1';
import { LOGO_PNG_BASE64 } from './logo.ts';

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
  { email: 'maraichage@cidil-asso.fr', name: 'CIDIL Maraîchage' },
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

function dataUrlToBytes(dataUrl: string): Uint8Array {
  const base64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
  return base64ToBytes(base64);
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

const PAGE_W = 420, PAGE_H = 595;
const LEFT = 40, RIGHT = PAGE_W - 40;
const GREEN = rgb(0x0d / 255, 0x28 / 255, 0x18 / 255);
const GRAY = rgb(0x55 / 255, 0x55 / 255, 0x55 / 255);
const LINE_GRAY = rgb(0xcc / 255, 0xcc / 255, 0xcc / 255);
const BOX_BG = rgb(0xee / 255, 0xf5 / 255, 0xf0 / 255);
const FOOTER_H = 90;
const LOGO_RATIO = 191 / 114;

function rightX(font: PDFFont, text: string, size: number, edge = RIGHT) {
  return edge - font.widthOfTextAtSize(text, size);
}

async function drawFooter(pdfDoc: PDFDocument, page: PDFPage, font: PDFFont, fontBold: PDFFont) {
  page.drawLine({ start: { x: LEFT, y: FOOTER_H }, end: { x: RIGHT, y: FOOTER_H }, thickness: 0.6, color: LINE_GRAY });

  const FOOT_SIZE = 8, LEADING = 10;
  const footLines: [string, boolean][] = [
    ['CIDIL — Jardins du Bandiat', true],
    ['19 Square du 08 mai, 16220 Montbron', false],
    ['Tel : 05 45 70 29 89', false],
    ['contact@cidil-asso.fr', false],
    ['www.cidil-asso.fr', false],
    ['N.A.F. 8899B  ·  SIRET 399 864 263 00047', false],
  ];
  const blockH = (footLines.length - 1) * LEADING + FOOT_SIZE * 0.9;
  const centerY = FOOTER_H / 2;
  const textTop = centerY + blockH / 2;
  const textBottom = centerY - blockH / 2;
  const ty = textTop - FOOT_SIZE * 0.75;

  const logoImg = await pdfDoc.embedPng(base64ToBytes(LOGO_PNG_BASE64));
  const logoH = blockH;
  const logoW = logoH * LOGO_RATIO;
  page.drawImage(logoImg, { x: LEFT, y: textBottom, width: logoW, height: logoH });

  footLines.forEach(([line, isName], i) => {
    const f = isName ? fontBold : font;
    page.drawText(line, { x: rightX(f, line, FOOT_SIZE), y: ty - i * LEADING, size: FOOT_SIZE, font: f, color: isName ? GREEN : GRAY });
  });
}

async function buildPdfBase64(
  numeroBL: number,
  dateStr: string,
  cmd: any,
  items: any[],
  signaturePngBytes: Uint8Array | null,
  signataireNom: string | null,
) {
  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([PAGE_W, PAGE_H]);
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica);
  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);

  let y = 550;
  page.drawText('BON DE LIVRAISON', { x: LEFT, y, size: 18, font: fontBold });
  const numTxt = `N°${numeroBL}`;
  page.drawText(numTxt, { x: rightX(fontBold, numTxt, 13), y: y + 1.5, size: 13, font: fontBold });

  y -= 18;
  page.drawLine({ start: { x: LEFT, y }, end: { x: RIGHT, y }, thickness: 0.6, color: LINE_GRAY });

  y -= 22;
  page.drawText(`Date : ${sansAccents(dateStr)}`, { x: LEFT, y, size: 10, font });
  y -= 34;
  page.drawText(sansAccents(cmd.client_nom), { x: LEFT, y, size: 13, font: fontBold });
  y -= 16;
  page.drawText(`Livraison : ${sansAccents(cmd.jour_livraison || '')}`, { x: LEFT, y, size: 10, font });
  y -= 26;

  const QTY_X = 250;
  for (const it of items) {
    if (y < FOOTER_H + 150) break;
    if (it.dispo === false) {
      page.drawText(sansAccents(it.nom), { x: LEFT, y, size: 10, font });
      const t = 'Non disponible';
      page.drawText(t, { x: rightX(font, t, 10), y, size: 10, font });
      y -= 16;
      continue;
    }
    const qty = it.quantite_reelle != null ? it.quantite_reelle : it.quantite;
    const unite = pluriel(qty, it.unite);
    page.drawText(sansAccents(it.nom), { x: LEFT, y, size: 10, font });
    const qtyTxt = `${qty} ${sansAccents(unite)}`;
    page.drawText(qtyTxt, { x: rightX(font, qtyTxt, 10, QTY_X), y, size: 10, font });
    if (it.prix_kg != null) {
      const priceTxt = `${it.prix_kg.toFixed(2)} €/${sansAccents(it.unite || 'kg')} — ${(it.prix_kg * qty).toFixed(2)} €`;
      page.drawText(priceTxt, { x: rightX(font, priceTxt, 9.5), y, size: 9.5, font });
    }
    y -= 16;
  }

  y -= 16;
  const boxW = 150, boxH = 26;
  const boxX = RIGHT - boxW;
  const boxBottom = y - boxH;
  page.drawRectangle({ x: boxX, y: boxBottom, width: boxW, height: boxH, color: BOX_BG, borderColor: GREEN, borderWidth: 1 });
  const totalTxt = `Total : ${(cmd.total || 0).toFixed(2)} €`;
  page.drawText(totalTxt, { x: rightX(fontBold, totalTxt, 13, RIGHT - 10), y: boxBottom + 8, size: 13, font: fontBold, color: GREEN });
  y = boxBottom;

  y -= 30;
  page.drawText('LIVRAISON CONFIRMÉE', { x: LEFT, y, size: 11, font: fontBold, color: GREEN });
  y -= 16;
  page.drawText(`Livré le : ${sansAccents(dateStr)}`, { x: LEFT, y, size: 10, font });
  y -= 10;

  if (signaturePngBytes) {
    try {
      const pngImage = await pdfDoc.embedPng(signaturePngBytes);
      const maxW = 160, maxH = 55;
      const scale = Math.min(maxW / pngImage.width, maxH / pngImage.height, 1);
      const w = pngImage.width * scale, h = pngImage.height * scale;
      y -= h;
      page.drawImage(pngImage, { x: LEFT, y, width: w, height: h });
      y -= 4;
      page.drawLine({ start: { x: LEFT, y }, end: { x: LEFT + Math.max(w, 140), y }, thickness: 0.5, color: rgb(0.6, 0.6, 0.6) });
      y -= 14;
    } catch (_e) {
      // signature illisible : on continue sans bloquer l'envoi du BL
    }
  }
  page.drawText(`Signé par : ${sansAccents(signataireNom || cmd.client_nom)}`, { x: LEFT, y, size: 9, font });

  await drawFooter(pdfDoc, page, font, fontBold);

  const bytes = await pdfDoc.save();
  return toBase64(bytes);
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS_HEADERS });

  try {
    const { commande_id, signature_base64, signataire_nom } = await req.json();
    if (!commande_id || !signature_base64) {
      return new Response(JSON.stringify({ error: 'commande_id ou signature_base64 manquant' }), { status: 400, headers: CORS_HEADERS });
    }

    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/commandes_clients?id=eq.${commande_id}&select=client_nom,client_idx,jour_livraison,semaine,items,total,numero_bl`,
      { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}` } }
    );
    const rows = await res.json();
    const cmd = rows[0];
    if (!cmd) {
      return new Response(JSON.stringify({ error: 'Commande introuvable' }), { status: 404, headers: CORS_HEADERS });
    }

    let numeroBL = cmd.numero_bl;
    if (!numeroBL) {
      const countRes = await fetch(
        `${SUPABASE_URL}/rest/v1/commandes_clients?numero_bl=not.is.null&select=numero_bl`,
        { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}`, Prefer: 'count=exact' } }
      );
      const existants = await countRes.json();
      numeroBL = existants.length + 1;
    }

    const maintenant = new Date().toISOString();
    await fetch(`${SUPABASE_URL}/rest/v1/commandes_clients?id=eq.${commande_id}`, {
      method: 'PATCH',
      headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        numero_bl: numeroBL,
        livre: true,
        livre_at: maintenant,
        signature_data: signature_base64,
        signataire_nom: signataire_nom || null,
      }),
    });

    let clientEmail: string | null = null;
    if (cmd.client_idx != null) {
      try {
        const clientRes = await fetch(
          `${SUPABASE_URL}/rest/v1/clients?id=eq.${cmd.client_idx}&select=email`,
          { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}` } }
        );
        const clientRows = await clientRes.json();
        clientEmail = clientRows[0]?.email || null;
      } catch (_e) { /* pas bloquant */ }
    }

    const dateStr = new Date().toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) +
      ' à ' + new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

    const items = typeof cmd.items === 'string' ? JSON.parse(cmd.items) : (cmd.items || []);

    let signatureBytes: Uint8Array | null = null;
    try { signatureBytes = dataUrlToBytes(signature_base64); } catch (_e) { signatureBytes = null; }

    let pdfBase64: string | null = null;
    let pdfErreur: string | null = null;
    try {
      pdfBase64 = await buildPdfBase64(numeroBL, dateStr, cmd, items, signatureBytes, signataire_nom || null);
    } catch (e) {
      pdfErreur = String(e);
    }

    const nomFichier = sansAccents(cmd.client_nom).replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const attachment = pdfBase64 ? [{ content: pdfBase64, name: `BL_n${numeroBL}_${nomFichier}_signe.pdf` }] : undefined;

    const htmlInterne = `
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;font-size:20px;margin:0;">BON DE LIVRAISON SIGNÉ</h1>
        <p style="color:#c9e5d2;font-size:13px;margin:4px 0 0;">N° ${numeroBL}</p>
      </div>
      <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
        <p style="color:#666;font-size:13px;margin:0 0 12px;">Livré le : ${dateStr}</p>
        <p><strong>${cmd.client_nom}</strong></p>
        <p style="font-weight:bold;">Total : ${(cmd.total || 0).toFixed(2)} €</p>
        <p style="font-size:13px;color:#888;">Signé par : ${signataire_nom || cmd.client_nom}. Le bon de livraison signé est joint en pièce jointe.</p>
      </div>
    </div>`;

    const emailInterne: any = {
      sender: { email: EXPEDITEUR_EMAIL, name: EXPEDITEUR_NOM },
      to: DESTINATAIRES,
      cc: CC,
      subject: `CIDIL - BL n°${numeroBL} signé - Livré : ${cmd.client_nom}`,
      htmlContent: htmlInterne,
    };
    if (attachment) emailInterne.attachment = attachment;

    const brevoRes = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
      body: JSON.stringify(emailInterne),
    });
    if (!brevoRes.ok) {
      const errTxt = await brevoRes.text();
      return new Response(JSON.stringify({ error: 'Echec envoi Brevo (interne)', detail: errTxt }), { status: 502, headers: CORS_HEADERS });
    }

    let clientEmailEnvoye = false;
    if (clientEmail && attachment) {
      const htmlClient = `
      <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
        <div style="background:#0d2818;padding:24px;text-align:center;border-radius:12px 12px 0 0;">
          <h1 style="color:#fff;font-size:20px;margin:0;">Votre bon de livraison</h1>
          <p style="color:#c9e5d2;font-size:13px;margin:4px 0 0;">N° ${numeroBL}</p>
        </div>
        <div style="padding:24px;background:#f7f6f2;border-radius:0 0 12px 12px;">
          <p>Bonjour,</p>
          <p style="font-size:14px;">Votre commande a bien été livrée le ${dateStr}. Vous trouverez votre bon de livraison signé en pièce jointe.</p>
          <p style="font-weight:bold;margin-top:14px;">Total : ${(cmd.total || 0).toFixed(2)} €</p>
          <p style="font-size:13px;color:#888;margin-top:16px;">Merci de votre confiance,<br>CIDIL Maraîchage</p>
        </div>
      </div>`;
      const emailClient: any = {
        sender: { email: EXPEDITEUR_EMAIL, name: EXPEDITEUR_NOM },
        to: [{ email: clientEmail, name: cmd.client_nom }],
        subject: `CIDIL - Votre bon de livraison n°${numeroBL}`,
        htmlContent: htmlClient,
        attachment,
      };
      const brevoResClient = await fetch('https://api.brevo.com/v3/smtp/email', {
        method: 'POST',
        headers: { 'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
        body: JSON.stringify(emailClient),
      });
      clientEmailEnvoye = brevoResClient.ok;
    }

    return new Response(
      JSON.stringify({ ok: true, pdf_attache: !!pdfBase64, pdf_erreur: pdfErreur, client_email_envoye: clientEmailEnvoye }),
      { headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } }
    );
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: CORS_HEADERS });
  }
});
