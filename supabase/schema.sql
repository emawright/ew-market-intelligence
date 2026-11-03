-- ShaqFX Supabase schema
-- Run this entire file in Supabase Dashboard > SQL Editor > New query.
-- All new users are members. Promote the first administrator manually after signup.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  role text not null default 'member' check (role in ('member','admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, display_name, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'display_name', ''),
    'member'
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = excluded.display_name;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

create or replace function public.is_shaqfx_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.profiles p
    where p.id = (select auth.uid())
      and p.role = 'admin'
  );
$$;

create table if not exists public.market_posts (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  market text,
  timeframe text,
  bias text,
  body text not null,
  published boolean not null default true,
  created_by uuid not null default auth.uid() references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.announcements (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  body text not null,
  created_by uuid not null default auth.uid() references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.notification_reads (
  announcement_id uuid not null references public.announcements(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  read_at timestamptz not null default now(),
  primary key (announcement_id, user_id)
);

alter table public.profiles enable row level security;
alter table public.market_posts enable row level security;
alter table public.announcements enable row level security;
alter table public.notification_reads enable row level security;

-- Profiles: members can read their own profile; admins can read all profiles.
drop policy if exists "Members read own profile and admins read all" on public.profiles;
create policy "Members read own profile and admins read all"
on public.profiles for select to authenticated
using (id = (select auth.uid()) or (select public.is_shaqfx_admin()));

-- No client-side insert/update/delete policies on profiles. Role changes are SQL-administered.

drop policy if exists "Authenticated members read published market posts" on public.market_posts;
create policy "Authenticated members read published market posts"
on public.market_posts for select to authenticated
using (published = true or (select public.is_shaqfx_admin()));

drop policy if exists "Admins insert market posts" on public.market_posts;
create policy "Admins insert market posts"
on public.market_posts for insert to authenticated
with check ((select public.is_shaqfx_admin()) and created_by = (select auth.uid()));

drop policy if exists "Admins update market posts" on public.market_posts;
create policy "Admins update market posts"
on public.market_posts for update to authenticated
using ((select public.is_shaqfx_admin()))
with check ((select public.is_shaqfx_admin()));

drop policy if exists "Admins delete market posts" on public.market_posts;
create policy "Admins delete market posts"
on public.market_posts for delete to authenticated
using ((select public.is_shaqfx_admin()));

drop policy if exists "Authenticated users read announcements" on public.announcements;
create policy "Authenticated users read announcements"
on public.announcements for select to authenticated
using (true);

drop policy if exists "Admins create announcements" on public.announcements;
create policy "Admins create announcements"
on public.announcements for insert to authenticated
with check ((select public.is_shaqfx_admin()) and created_by = (select auth.uid()));

drop policy if exists "Admins update announcements" on public.announcements;
create policy "Admins update announcements"
on public.announcements for update to authenticated
using ((select public.is_shaqfx_admin()))
with check ((select public.is_shaqfx_admin()));

drop policy if exists "Admins delete announcements" on public.announcements;
create policy "Admins delete announcements"
on public.announcements for delete to authenticated
using ((select public.is_shaqfx_admin()));

drop policy if exists "Users read own notification receipts" on public.notification_reads;
create policy "Users read own notification receipts"
on public.notification_reads for select to authenticated
using (user_id = (select auth.uid()));

drop policy if exists "Users mark own notifications read" on public.notification_reads;
create policy "Users mark own notifications read"
on public.notification_reads for insert to authenticated
with check (user_id = (select auth.uid()));

drop policy if exists "Users clear own notification receipts" on public.notification_reads;
create policy "Users clear own notification receipts"
on public.notification_reads for delete to authenticated
using (user_id = (select auth.uid()));

grant usage on schema public to authenticated;
grant select on public.profiles to authenticated;
grant select, insert, update, delete on public.market_posts to authenticated;
grant select, insert, update, delete on public.announcements to authenticated;
grant select, insert, delete on public.notification_reads to authenticated;

-- Promote your own account only AFTER registering it through the ShaqFX sign-up page.
-- Replace the email below with the exact email used for your first account, then run
-- this separately in the SQL Editor. Never expose this operation in client-side code.
--
-- update public.profiles
-- set role = 'admin', updated_at = now()
-- where email = 'YOUR-EMAIL@example.com';
