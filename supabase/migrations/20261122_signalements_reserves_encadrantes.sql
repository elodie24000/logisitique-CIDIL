-- Le Claude de dépannage est réservé aux deux encadrantes (décision d'Élodie du 22/11/2026).
drop policy if exists "ajout public signalements" on public.signalements;
create policy "ajout signalements encadrantes" on public.signalements for insert to public
  with check (statut = 'nouveau' and role = 'encadrant' and qui in ('Atika', 'Amélie'));

drop policy if exists "ajout public signalement_messages" on public.signalement_messages;
create policy "ajout messages encadrantes" on public.signalement_messages for insert to public
  with check (
    auteur in ('Atika', 'Amélie') and length(texte) <= 4000
    and exists (select 1 from public.signalements s where s.id = signalement_id and s.role = 'encadrant' and s.qui in ('Atika', 'Amélie'))
  );
