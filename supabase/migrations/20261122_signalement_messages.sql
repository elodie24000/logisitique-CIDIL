-- Conversation entre l'équipe (Atika, Amélie…) et le Claude de dépannage, rattachée à un signalement.
alter table public.signalements add column if not exists github_issue integer;
-- statut : nouveau → transmis (e-mail parti, fiche GitHub créée) → en_cours → repondu | corrige | pour_elodie

create table if not exists public.signalement_messages (
  id bigint generated always as identity primary key,
  signalement_id bigint not null references public.signalements(id) on delete cascade,
  created_at timestamptz not null default now(),
  auteur text not null,          -- prénom (Atika / Amélie / rôle) ou 'Claude'
  texte text not null check (length(texte) between 1 and 4000)
);
alter table public.signalement_messages enable row level security;
create policy "lecture publique signalement_messages" on public.signalement_messages for select to public using (true);
-- Depuis l'appli : impossible d'écrire au nom de Claude (seul le workflow GitHub, avec la clé service, le peut).
create policy "ajout public signalement_messages" on public.signalement_messages for insert to public
  with check (auteur <> 'Claude' and length(texte) <= 4000);

-- Chaque réponse de l'équipe est transmise à la fiche GitHub (fonction Edge signalement-github, { message_id }).
create or replace function public.signalement_message_recu()
returns trigger language plpgsql security definer set search_path to 'public', 'extensions' as $$
begin
  if NEW.auteur <> 'Claude' then
    perform net.http_post(
      url := 'https://ulvrwtwxzhlrplvbcsrd.supabase.co/functions/v1/signalement-github',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'apikey', 'sb_publishable_dxH_p3Wo4Suin-QejMzRVg_NQ_MjwfQ',
        'Authorization', 'Bearer sb_publishable_dxH_p3Wo4Suin-QejMzRVg_NQ_MjwfQ'
      ),
      body := jsonb_build_object('message_id', NEW.id)
    );
  end if;
  return NEW;
exception when others then
  return NEW;
end;
$$;
drop trigger if exists signalement_message_recu on public.signalement_messages;
create trigger signalement_message_recu after insert on public.signalement_messages
  for each row execute function public.signalement_message_recu();

-- Chaque nouveau signalement crée une fiche GitHub pour le Claude de dépannage (fonction Edge signalement-github, { id }).
-- L'e-mail à Élodie reste envoyé par le trigger signalement_recu (fonction signalement-recu).
create or replace function public.signalement_vers_github()
returns trigger language plpgsql security definer set search_path to 'public', 'extensions' as $$
begin
  perform net.http_post(
    url := 'https://ulvrwtwxzhlrplvbcsrd.supabase.co/functions/v1/signalement-github',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'apikey', 'sb_publishable_dxH_p3Wo4Suin-QejMzRVg_NQ_MjwfQ',
      'Authorization', 'Bearer sb_publishable_dxH_p3Wo4Suin-QejMzRVg_NQ_MjwfQ'
    ),
    body := jsonb_build_object('id', NEW.id)
  );
  return NEW;
exception when others then
  return NEW;
end;
$$;
drop trigger if exists signalement_vers_github on public.signalements;
create trigger signalement_vers_github after insert on public.signalements
  for each row execute function public.signalement_vers_github();
