-- Prénom de la personne de l'équipe (Atika, Amélie) qui a fait l'action / à qui appartient le téléphone abonné.
alter table public.activity_log add column if not exists qui text;
alter table public.push_subscriptions add column if not exists qui text;
