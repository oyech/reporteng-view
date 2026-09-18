-- Migrasi akses anggota dari reporteng_team_members ke profiles.
-- Asumsi: profiles.id = auth.users.id. Semua pemilik profil adalah anggota tim.
-- Jalankan melalui SQL Editor sebagai pemilik proyek.
begin;
alter table public.profiles enable row level security;
grant select on public.profiles to authenticated;
drop policy if exists reporteng_profiles_read_self on public.profiles;
create policy reporteng_profiles_read_self on public.profiles
  for select to authenticated using (id = (select auth.uid()));

alter table public.report_eng enable row level security;
grant select on public.report_eng to authenticated;
-- Mengganti policy yang sebelumnya bergantung pada reporteng_team_members.
drop policy if exists reporteng_team_read_gate on public.report_eng;
create policy reporteng_team_read_gate on public.report_eng
  as restrictive for select to authenticated
  using (exists (select 1 from public.profiles p where p.id = (select auth.uid())));
drop policy if exists reporteng_team_read_all on public.report_eng;
create policy reporteng_team_read_all on public.report_eng
  for select to authenticated
  using (exists (select 1 from public.profiles p where p.id = (select auth.uid())));
drop policy if exists reporteng_no_anonymous_read on public.report_eng;
create policy reporteng_no_anonymous_read on public.report_eng
  as restrictive for select to anon using (false);
commit;

-- Tabel anggota lama dibiarkan; aplikasi dan policy baru tidak memakainya.
-- Policy restrictive lain tetap berlaku. Periksa jika pembacaan masih terhalang.
select tablename, policyname, permissive, roles, cmd, qual
from pg_policies
where schemaname = 'public' and tablename in ('profiles', 'report_eng');
