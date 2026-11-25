-- Harden function resolution and qualify the protected table.
create or replace function public.guard_match_feature_cutoff()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
declare target_kickoff timestamptz;
begin
  select m.kickoff_at into target_kickoff
  from public.matches as m
  where m.id = new.match_id;

  if target_kickoff is null then
    raise exception 'feature snapshot references missing match %', new.match_id;
  end if;
  if new.feature_cutoff_at >= target_kickoff then
    raise exception 'feature_cutoff_at must be strictly before kickoff_at';
  end if;
  if new.generated_at >= target_kickoff then
    raise exception 'generated_at must be strictly before kickoff_at';
  end if;
  return new;
end;
$function$;
