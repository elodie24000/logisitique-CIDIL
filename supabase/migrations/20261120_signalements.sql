-- Bouton « 🛟 Déclarer un problème » : signalements de l'équipe (Atika, Amélie…) vers Élodie.
create table if not exists public.signalements (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  qui text,                 -- prénom (Atika / Amélie) si connu
  role text,                -- rôle connecté (encadrant, livreur…)
  page text,                -- onglet affiché au moment du signalement
  texte text not null check (length(texte) between 3 and 4000),
  contexte text,            -- téléphone, version, dernières erreurs techniques
  statut text not null default 'nouveau'  -- nouveau → transmis (e-mail parti) → resolu
);
alter table public.signalements enable row level security;
create policy "ajout public signalements" on public.signalements for insert to public with check (statut = 'nouveau');
create policy "lecture publique signalements" on public.signalements for select to public using (true);

-- Prévient Élodie (fonction Edge signalement-recu) à chaque nouveau signalement.
create or replace function public.signalement_recu()
returns trigger language plpgsql security definer set search_path to 'public', 'extensions' as $$
begin
  perform net.http_post(
    url := 'https://ulvrwtwxzhlrplvbcsrd.supabase.co/functions/v1/signalement-recu',
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
drop trigger if exists signalement_recu on public.signalements;
create trigger signalement_recu after insert on public.signalements for each row execute function public.signalement_recu();
