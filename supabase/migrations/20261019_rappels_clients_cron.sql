-- Appelle la fonction rappels-clients toutes les 10 minutes entre 4h et 12h59 UTC
-- (6h–14h59 en heure d'été, 5h–13h59 en heure d'hiver). La fonction décide elle-même,
-- à l'heure de Paris, s'il faut envoyer quelque chose, et n'envoie chaque rappel qu'une fois.
select cron.unschedule(jobid) from cron.job where jobname = 'rappels-clients';
select cron.schedule(
  'rappels-clients',
  '*/10 4-12 * * *',
  $$
  select net.http_post(
    url := 'https://ulvrwtwxzhlrplvbcsrd.supabase.co/functions/v1/rappels-clients',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'apikey', 'sb_publishable_dxH_p3Wo4Suin-QejMzRVg_NQ_MjwfQ',
      'Authorization', 'Bearer sb_publishable_dxH_p3Wo4Suin-QejMzRVg_NQ_MjwfQ'
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 60000
  );
  $$
);
