/* Browser credentials are held in an HttpOnly cookie, never web storage. */
window.signSightAuth = (() => {
  const STATE_KEY = 'signsight.auth-state';
  let user = null, generation = 0, mutationCount = 0;
  let mutations = Promise.resolve();

  function notify() { window.dispatchEvent(new CustomEvent('signsight-auth-changed')); }
  function setUser(profile, announce = true) {
    const changed = JSON.stringify(user) !== JSON.stringify(profile);
    user = profile;
    for (const link of window.document?.querySelectorAll('[data-staff-only]') || []) {
      link.hidden = !['admin', 'manager'].includes(user?.role);
    }
    if (changed && announce) notify();
  }
  function storedState() {
    try { return JSON.parse(window.localStorage.getItem(STATE_KEY)); } catch (_) { return null; }
  }
  function publish(state) {
    // This is only a notification/offline-logout marker, not an identity or credential.
    try { window.localStorage.setItem(STATE_KEY, JSON.stringify({state, nonce: `${Date.now()}-${Math.random()}`})); }
    catch (_) { /* Cookies still restore across pages when web storage is disabled. */ }
  }
  function clear(announce = true) { generation++; setUser(null, announce); }

  async function request(path, options = {}) {
    if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//') || path.includes('\\')) {
      throw new Error('Invalid API path');
    }
    const { responseType, ...fetchOptions } = options;
    const headers = new Headers(options.headers || {});
    headers.delete('Authorization');
    headers.set('X-SignSight-Web', '1');
    const version = generation;
    const response = await fetch(`/api/v1${path}`, { ...fetchOptions, headers, credentials: 'same-origin' });
    if (response.status === 401 && version === generation && !['/auth/login', '/auth/register'].includes(path)) {
      clear();
    }
    if (response.status === 403 && user && version === generation && path !== '/auth/me') {
      try {
        const profile = await request('/auth/me');
        if (version === generation) setUser(profile);
      } catch (_) { /* Preserve the original operation error. */ }
    }
    if (!response.ok) {
      let message = `Yêu cầu thất bại (${response.status})`;
      try {
        const body = await response.json();
        if (typeof body.detail === 'string') message = body.detail;
        else if (Array.isArray(body.detail)) message = body.detail.map(item => `${item.loc.join('.')}: ${item.msg}`).join('; ');
      } catch (_) { /* Keep the status when an upstream error is not JSON. */ }
      const error = new Error(message); error.status = response.status; throw error;
    }
    return response.status === 204 ? null : responseType === 'blob' ? response.blob() : response.json();
  }

  async function restore(announce = true) {
    if (mutationCount) await mutations.catch(() => {});
    const version = ++generation;
    if (storedState()?.state === 'out') { setUser(null, announce); return null; }
    try {
      const profile = await request('/auth/me');
      if (version === generation) setUser(profile, announce);
    } catch (error) {
      // A network failure must not erase the shared browser session.
      if (version === generation && error.status === 401) setUser(null, announce);
    }
    return user;
  }

  function mutate(operation) {
    mutationCount++;
    const run = mutations.catch(() => {}).then(() => {
      // Serialize cookie-changing responses in this page and, where supported,
      // across tabs so a late logout cannot clear a newer login cookie.
      return window.navigator?.locks
        ? window.navigator.locks.request('signsight-auth', operation) : operation();
    });
    mutations = run.finally(() => { mutationCount--; });
    return mutations;
  }
  async function signIn(username, password, rememberMe = false) {
    const version = ++generation;
    const result = await request('/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, remember_me: rememberMe === true }),
    });
    if (version === generation) { publish('in'); setUser(result.user); }
    return user;
  }
  function login(username, password, rememberMe = false) { return mutate(() => signIn(username, password, rememberMe)); }
  function register(username, email, password) {
    return mutate(async () => {
      await request('/auth/register', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });
      return signIn(username, password);
    });
  }
  function logout() {
    return mutate(async () => {
      clear(); publish('out');
      // Keep the local signed-out marker even when server revocation is offline.
      await request('/auth/logout', { method: 'POST' });
    });
  }

  window.addEventListener('storage', event => {
    if (event.key !== STATE_KEY) return;
    // Ignore an old queued notification if a newer change has already won.
    try { if (event.newValue !== window.localStorage.getItem(STATE_KEY)) return; } catch (_) {}
    if (storedState()?.state === 'out') clear();
    else restore();
  });
  window.addEventListener('focus', () => { restore(); });
  window.addEventListener('pageshow', event => { if (event.persisted) restore(); });
  const ready = restore(false);
  return { request, login, register, logout, restore, ready, get user() { return user; } };
})();
