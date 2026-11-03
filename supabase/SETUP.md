# ShaqFX Supabase setup

This repository uses Supabase Auth and Postgres for member accounts, admin-only market publishing, and in-app announcements.

## 1. Create the database tables and security policies

1. Open the ShaqFX Supabase project.
2. Open **SQL Editor**.
3. Choose **New query**.
4. Open `supabase/schema.sql` from this repository and copy its entire contents.
5. Paste into the SQL Editor and click **Run**.
6. Confirm the query completes without errors.

The schema enables Row Level Security on every application table. New accounts are always created with the `member` role. The browser cannot change a profile role.

## 2. Configure email authentication

In Supabase Dashboard:

1. Open **Authentication → URL Configuration**.
2. Set **Site URL** to `https://emawright.github.io/ew-market-intelligence/`.
3. Add this exact URL to **Redirect URLs**:
   `https://emawright.github.io/ew-market-intelligence/`
4. Open **Authentication → Providers → Email** and ensure Email is enabled.

For safer accounts, leave email confirmation enabled. A newly registered user may need to click the confirmation link sent by Supabase before signing in. Configure the email SMTP provider later if you want branded/reliable delivery; default email sending may be rate-limited.

## 3. Create your administrator account

1. Open the ShaqFX website and choose **Members / Login**.
2. Create your own account using the email address that should own the administrator role.
3. If email confirmation is enabled, confirm the email first.
4. Sign in once so the account is created in Supabase Auth and its profile row is generated.
5. In Supabase Dashboard, open **SQL Editor → New query**.
6. Replace the example email below with the exact email you used to register, then run:

```sql
update public.profiles
set role = 'admin', updated_at = now()
where email = 'YOUR-EMAIL@example.com';
```

7. Refresh the ShaqFX page or sign out and back in. The **Administrator publishing desk** should appear.

Do not run the promotion query with another person's email. Do not put this query into website JavaScript.

## 4. Test member permissions

- Register a second account using a different email address.
- It should see the member area, published market updates and announcements.
- It should not see the administrator publishing desk.
- Attempting to insert a market post or announcement as this second account must be rejected by database Row Level Security.

## Security notes

- The Supabase project URL and `sb_publishable_...` key are designed for browser use. They do not grant administrator privileges.
- Never put a Supabase secret key, legacy `service_role` key, database password, or SMTP password in this GitHub repository or browser code.
- RLS policies in `schema.sql` are the security boundary. Hiding the admin interface is only a user-interface convenience.
- The notification centre currently broadcasts in-app announcements to authenticated members. It does not yet send email or browser push notifications.
