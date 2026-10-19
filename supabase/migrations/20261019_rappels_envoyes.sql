-- Journal des rappels clients envoyés par la fonction rappels-clients (une ligne par envoi et par jour).
-- La clé unique empêche tout double envoi. Accès réservé au rôle service (RLS sans politique).
create table if not exists public.rappels_envoyes (
  cle text primary key,
  envoye_at timestamptz not null default now(),
  detail jsonb
);
alter table public.rappels_envoyes enable row level security;
