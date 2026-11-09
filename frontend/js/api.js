// OAuth 2.0 client for the browser: token storage, authenticated fetch, page guards.
//
// This app is a PUBLIC OAuth client: it identifies itself with a client_id only,
// because anything in browser JavaScript (like a client secret) can be read by users.

const Auth = (() => {
  const CLIENT_ID = "taskforge-web";
  const TOKEN_URL = "/api/auth/token";
  const REVOKE_URL = "/api/auth/revoke";

  const ACCESS = "tm_access_token";
  const REFRESH = "tm_refresh_token";
  const USER = "tm_user";
  const SCOPE = "tm_scope";

  function save(data) {
    sessionStorage.setItem(ACCESS, data.access_token);
    if (data.refresh_token) sessionStorage.setItem(REFRESH, data.refresh_token);
    if (data.user) sessionStorage.setItem(USER, JSON.stringify(data.user));
    if (data.scope !== undefined) sessionStorage.setItem(SCOPE, data.scope);
  }

  function clear() {
    [ACCESS, REFRESH, USER, SCOPE].forEach((k) => sessionStorage.removeItem(k));
  }

  function user() {
    try { return JSON.parse(sessionStorage.getItem(USER)); } catch { return null; }
  }

  // Does the current token include this scope? (UI hint only - the server enforces it)
  function hasScope(scope) {
    return (sessionStorage.getItem(SCOPE) || "").split(" ").includes(scope);
  }

  // POST to an OAuth endpoint using the standard form encoding
  function postForm(url, fields) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: CLIENT_ID, ...fields }),
    });
  }

  // grant_type=password: exchange username/password for tokens
  async function login(username, password, portal) {
    const res = await postForm(TOKEN_URL, { grant_type: "password", username, password, portal });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error_description || data.message || "Sign in failed.");
    save(data);
    return data.user;
  }

  // grant_type=refresh_token: get a new access token (and a new refresh token - rotation).
  // If several requests need a refresh at once, they share one call, because a
  // refresh token can only be used once.
  let refreshing = null;
  function refresh() {
    if (!refreshing) {
      refreshing = (async () => {
        const token = sessionStorage.getItem(REFRESH);
        if (!token) return false;
        const res = await postForm(TOKEN_URL, { grant_type: "refresh_token", refresh_token: token });
        if (!res.ok) return false;
        save(await res.json());
        return true;
      })().finally(() => (refreshing = null));
    }
    return refreshing;
  }

  // fetch() that adds "Authorization: Bearer <token>" and retries once after refreshing
  async function request(url, options = {}) {
    const send = () =>
      fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
          Authorization: `Bearer ${sessionStorage.getItem(ACCESS)}`,
        },
      });

    let res = await send();
    if (res.status === 401 && (await refresh())) res = await send();
    if (res.status === 401) {
      clear();
      window.location.href = "/";
    }
    return res;
  }

  // Revoke both tokens on the server (RFC 7009), then forget them locally
  async function logout() {
    const tokens = [sessionStorage.getItem(ACCESS), sessionStorage.getItem(REFRESH)].filter(Boolean);
    await Promise.allSettled(tokens.map((token) => postForm(REVOKE_URL, { token })));
    clear();
    window.location.href = "/";
  }

  // Call on a protected page: sends you to login if not signed in or wrong role.
  // Resolves with the user object when the token is valid.
  async function guard(requiredRole) {
    const u = user();
    if (!u || !sessionStorage.getItem(ACCESS)) return void (window.location.href = "/");
    if (u.role !== requiredRole) return void (window.location.href = `/${u.role}.html`);

    const res = await request("/api/auth/me"); // the server verifies the token here
    if (!res.ok) return;
    return res.json();
  }

  return { login, logout, request, refresh, guard, user, hasScope };
})();
