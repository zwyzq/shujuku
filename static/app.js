async function api(method, path, data) {
  const opts = {
    method,
    credentials: "same-origin",
    headers: {},
  };
  if (data !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(data);
  }
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch (_) { body = null; }
  if (!res.ok) {
    const err = new Error((body && body.error) || res.statusText);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

function $(sel, root = document) { return root.querySelector(sel); }
function $$ (sel, root = document) { return [...root.querySelectorAll(sel)]; }

function showMsg(el, text, ok) {
  if (!el) return;
  el.textContent = text || "";
  el.className = "msg " + (ok ? "ok" : "err");
}

function statusBadge(status) {
  const map = { draft: "草稿", published: "已发布", closed: "已关闭" };
  return `<span class="badge ${status || ""}">${map[status] || status || ""}</span>`;
}

async function loadMe() {
  try {
    const data = await api("GET", "/api/auth/me");
    return data.user;
  } catch (_) {
    return null;
  }
}

async function requireLogin() {
  const user = await loadMe();
  if (!user) {
    location.href = "/login";
    return null;
  }
  return user;
}
