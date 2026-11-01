/* Apply before page paint; preferences are independent of account/session data. */
(() => {
  'use strict';
  const key = 'signsight.theme', choices = ['system', 'light', 'dark'];
  let media = null;
  try { media = window.matchMedia('(prefers-color-scheme: dark)'); } catch (_) {}
  function read() {
    try { const value = window.localStorage.getItem(key); return choices.includes(value) ? value : 'system'; }
    catch (_) { return 'system'; }
  }
  let preference = read();
  function apply() {
    document.documentElement.dataset.theme = preference === 'system' ? (media?.matches ? 'dark' : 'light') : preference;
    for (const button of document.querySelectorAll('[data-theme-choice]')) {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === preference));
    }
  }
  apply();
  function bind() {
    apply();
    for (const button of document.querySelectorAll('[data-theme-choice]')) {
      button.addEventListener('click', () => {
        if (!choices.includes(button.dataset.themeChoice)) return;
        preference = button.dataset.themeChoice;
        try { window.localStorage.setItem(key, preference); } catch (_) {}
        apply();
      });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, {once:true});
  else bind();
  const systemChanged = () => { if (preference === 'system') apply(); };
  if (media?.addEventListener) media.addEventListener('change', systemChanged);
  else media?.addListener?.(systemChanged);
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { preference = read(); apply(); }
  });
})();
