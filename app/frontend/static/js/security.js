/**
 * Production hardening: no sensitive data in the browser console.
 * Set window.__LICENSEIQ__.isDev from the server before this script loads.
 */
(function (global) {
  const cfg = global.__LICENSEIQ__ || {};
  const isDev = cfg.isDev === true;
  global.__LICENSEIQ__ = Object.assign({}, cfg, { isDev });

  if (!isDev && typeof console !== 'undefined') {
    const noop = function () {};
    [
      'log', 'debug', 'info', 'warn', 'error', 'trace',
      'dir', 'table', 'group', 'groupCollapsed', 'groupEnd',
    ].forEach(function (m) {
      if (typeof console[m] === 'function') {
        try { console[m] = noop; } catch (_) { /* some browsers lock console */ }
      }
    });
  }

  global.licenseiqIsDev = function () {
    return global.__LICENSEIQ__ && global.__LICENSEIQ__.isDev === true;
  };

  global.licenseiqUserError = function (err, fallback) {
    const fb = fallback || 'Something went wrong. Please try again.';
    if (licenseiqIsDev() && err && err.message) return String(err.message);
    return fb;
  };
})(typeof window !== 'undefined' ? window : globalThis);
