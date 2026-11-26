-- Commentaire libre du client sur sa commande (ex. Intermarché : « poireaux en bottes de 500 g »).
-- Affiché uniquement aux encadrantes. Décision d'Élodie du 26/11.
alter table public.commandes_clients add column if not exists commentaire text;
comment on column public.commandes_clients.commentaire is 'Commentaire libre du client (conditionnement…), visible des encadrantes uniquement';
