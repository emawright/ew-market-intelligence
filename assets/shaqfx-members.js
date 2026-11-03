import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

const SUPABASE_URL = 'https://cqlumfvrkgysvqwawogu.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_HP6yrdtggLune-4h5ZuqmA_E8twVxh5';
const sb = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
const $ = (id) => document.getElementById(id);
const status = (message, isError = false) => {
  const el = $('memberStatus');
  if (el) { el.textContent = message; el.className = isError ? 'red small' : 'green small'; }
};
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function loadMemberArea() {
  const { data: { user } } = await sb.auth.getUser();
  $('memberSignedOut').hidden = !!user;
  $('memberSignedIn').hidden = !user;
  $('memberAdmin').hidden = true;
  if (!user) {
    $('memberIdentity').textContent = 'You are not signed in.';
    $('memberPosts').innerHTML = '<p class="muted small">Sign in to view member-only market updates.</p>';
    $('memberNotifications').innerHTML = '<p class="muted small">Sign in to view announcements.</p>';
    return;
  }
  $('memberIdentity').textContent = user.email || 'Signed in';
  const { data: profile, error: profileError } = await sb.from('profiles').select('role,display_name').eq('id', user.id).single();
  if (profileError) {
    status('Signed in, but the profile table is not ready. Run supabase/schema.sql in the Supabase SQL Editor.', true);
    return;
  }
  const isAdmin = profile.role === 'admin';
  $('memberRole').textContent = isAdmin ? 'Administrator' : 'Member';
  $('memberAdmin').hidden = !isAdmin;
  await Promise.all([loadPosts(), loadAnnouncements(user.id)]);
}
async function loadPosts() {
  const { data, error } = await sb.from('market_posts').select('id,title,market,timeframe,bias,body,created_at').eq('published', true).order('created_at', {ascending:false}).limit(30);
  if (error) { $('memberPosts').textContent = error.message; return; }
  $('memberPosts').innerHTML = data.length ? data.map(p => `<article class="item"><div class="row"><b>${escapeHtml(p.title)}</b><span class="pill">${escapeHtml([p.market,p.timeframe,p.bias].filter(Boolean).join(' · ') || 'Market update')}</span></div><p>${escapeHtml(p.body).replace(/\n/g,'<br>')}</p><div class="muted small">${new Date(p.created_at).toLocaleString()}</div></article>`).join('') : '<p class="muted small">No market updates have been published yet.</p>';
}
async function loadAnnouncements(userId) {
  const [{ data: announcements, error }, { data: reads }] = await Promise.all([
    sb.from('announcements').select('id,title,body,created_at').order('created_at', {ascending:false}).limit(40),
    sb.from('notification_reads').select('announcement_id').eq('user_id', userId)
  ]);
  if (error) { $('memberNotifications').textContent = error.message; return; }
  const readIds = new Set((reads || []).map(r => r.announcement_id));
  const unread = (announcements || []).filter(a => !readIds.has(a.id));
  $('unreadCount').textContent = String(unread.length);
  $('memberNotifications').innerHTML = announcements?.length ? announcements.map(a => {
    const isRead = readIds.has(a.id);
    return `<article class="item"><div class="row"><b>${escapeHtml(a.title)}</b><span class="pill">${isRead ? 'Read' : 'New'}</span></div><p>${escapeHtml(a.body).replace(/\n/g,'<br>')}</p><div class="row"><span class="muted small">${new Date(a.created_at).toLocaleString()}</span>${isRead ? '' : `<button class="btn" data-read="${a.id}">Mark as read</button>`}</div></article>`;
  }).join('') : '<p class="muted small">No announcements yet.</p>';
  document.querySelectorAll('[data-read]').forEach(button => button.addEventListener('click', async () => {
    const { error: insertError } = await sb.from('notification_reads').insert({announcement_id:button.dataset.read,user_id:userId});
    if (insertError && insertError.code !== '23505') { status(insertError.message, true); return; }
    await loadAnnouncements(userId);
  }));
}
$('memberSignUp').addEventListener('click', async () => {
  const email = $('memberEmail').value.trim();
  const password = $('memberPassword').value;
  if (!email || password.length < 8) { status('Enter a valid email and a password of at least 8 characters.', true); return; }
  const { data, error } = await sb.auth.signUp({email,password});
  if (error) { status(error.message, true); return; }
  status(data.session ? 'Account created. You are signed in.' : 'Account created. Check your email for the confirmation link, then sign in.');
  await loadMemberArea();
});
$('memberSignIn').addEventListener('click', async () => {
  const { error } = await sb.auth.signInWithPassword({email:$('memberEmail').value.trim(),password:$('memberPassword').value});
  if (error) { status(error.message, true); return; }
  status('Signed in successfully.');
  await loadMemberArea();
});
$('memberSignOut').addEventListener('click', async () => {
  const { error } = await sb.auth.signOut();
  if (error) { status(error.message, true); return; }
  status('You have signed out.');
  await loadMemberArea();
});
$('publishMarketPost').addEventListener('click', async () => {
  const payload = {
    title:$('adminPostTitle').value.trim(), market:$('adminPostMarket').value,
    timeframe:$('adminPostTimeframe').value, bias:$('adminPostBias').value,
    body:$('adminPostBody').value.trim()
  };
  if (!payload.title || !payload.body) { status('Add a title and market update before publishing.', true); return; }
  const { error } = await sb.from('market_posts').insert(payload);
  if (error) { status(error.message, true); return; }
  $('adminPostTitle').value = ''; $('adminPostBody').value = '';
  status('Market update published to members.');
  await loadPosts();
});
$('publishAnnouncement').addEventListener('click', async () => {
  const payload = {title:$('adminNoticeTitle').value.trim(),body:$('adminNoticeBody').value.trim()};
  if (!payload.title || !payload.body) { status('Add an announcement title and message.', true); return; }
  const { error } = await sb.from('announcements').insert(payload);
  if (error) { status(error.message, true); return; }
  $('adminNoticeTitle').value = ''; $('adminNoticeBody').value = '';
  status('Announcement published to the in-app notification centre.');
  const { data: { user } } = await sb.auth.getUser();
  if (user) await loadAnnouncements(user.id);
});
sb.auth.onAuthStateChange(() => { setTimeout(loadMemberArea, 0); });
loadMemberArea();
