// Admin "Users" view: list, add, edit and delete accounts (needs the users:manage scope).

(() => {
  const { $, $$, icon, esc, initials, toast, api } = UI;
  if (!$("[data-view-panel='users']")) return; // only on admin.html

  const SCOPE_INFO = {
    "tasks:read": "View tasks",
    "tasks:write": "Create, edit, delete tasks",
    "users:manage": "Manage user accounts",
    "reports:read": "View reports",
  };
  const ROLE_SCOPES = {
    admin: ["tasks:read", "tasks:write", "users:manage", "reports:read"],
    user: ["tasks:read"],
  };

  let users = [];
  let me = null;
  let roleFilter = "all";
  let query = "";
  let loaded = false;

  async function load() {
    try {
      users = await api("GET", "/api/users");
      loaded = true;
    } catch (err) {
      toast(err.message);
    }
    render();
  }

  function render() {
    renderStats();
    renderRows();
    $$("[data-user-count]").forEach((el) => (el.textContent = users.length));
  }

  function renderStats() {
    const admins = users.filter((u) => u.role === "admin").length;
    const assigned = users.reduce((n, u) => n + u.task_count, 0);
    const cards = [
      { label: "Total users", value: users.length, icon: "users", tone: "accent" },
      { label: "Admins", value: admins, icon: "shield", tone: "progress" },
      { label: "Read-only users", value: users.length - admins, icon: "eye", tone: "todo" },
      { label: "Tasks assigned", value: assigned, icon: "check", tone: "done" },
    ];
    $("#user-stats").innerHTML = cards
      .map(
        (c) => `<div class="stat">
          <div class="stat-icon tone-${c.tone}">${icon(c.icon)}</div>
          <div><div class="stat-value">${c.value}</div><div class="stat-label">${c.label}</div></div>
        </div>`
      )
      .join("");
  }

  function renderRows() {
    const rows = users
      .filter((u) => roleFilter === "all" || u.role === roleFilter)
      .filter((u) => !query || `${u.username} ${u.email}`.toLowerCase().includes(query));

    if (!rows.length) {
      $("#user-rows").innerHTML = `<tr><td colspan="5" class="empty">${loaded ? "No users match." : "Loading users…"}</td></tr>`;
      return;
    }

    $("#user-rows").innerHTML = rows
      .map((u) => {
        const isMe = me && u.id === me.id;
        const joined = u.created_at ? new Date(u.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—";
        return `<tr>
          <td>
            <div class="user-cell">
              <span class="avatar">${esc(initials(u.username))}</span>
              <div>
                <div class="task-title">${esc(u.username)} ${isMe ? '<span class="you">You</span>' : ""}</div>
                <div class="task-desc">${esc(u.email)}</div>
              </div>
            </div>
          </td>
          <td><span class="role-chip ${u.role}">${u.role === "admin" ? icon("shield") + " Admin" : icon("eye") + " User"}</span></td>
          <td class="hide-sm">${u.task_count}</td>
          <td class="hide-sm">${joined}</td>
          <td class="actions">
            <button class="icon-btn" title="Edit" data-user-edit="${u.id}">${icon("edit")}</button>
            <button class="icon-btn danger" title="${isMe ? "You can't delete your own account" : "Delete"}" data-user-delete="${u.id}" ${isMe ? "disabled" : ""}>${icon("trash")}</button>
          </td>
        </tr>`;
      })
      .join("");
  }

  function renderPermissions() {
    const scopes = Object.keys(SCOPE_INFO);
    $("#perm-table").innerHTML = `
      <table class="perm-grid">
        <thead><tr><th>Scope</th><th>Admin</th><th>User</th></tr></thead>
        <tbody>
          ${scopes
            .map(
              (s) => `<tr>
                <td><code>${s}</code><div class="task-desc">${SCOPE_INFO[s]}</div></td>
                <td>${ROLE_SCOPES.admin.includes(s) ? `<span class="yes">${icon("check")}</span>` : `<span class="no">—</span>`}</td>
                <td>${ROLE_SCOPES.user.includes(s) ? `<span class="yes">${icon("check")}</span>` : `<span class="no">—</span>`}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  // ---------- Add / edit dialog ----------
  let editingId = null;

  function openDialog(user = null) {
    editingId = user ? user.id : null;
    const form = $("#user-form");
    form.reset();
    $("#user-form-error").hidden = true;
    $("#user-dialog-title").textContent = user ? "Edit user" : "Add user";
    $("#user-save-btn").textContent = user ? "Save changes" : "Add user";
    $("#u-password-label").textContent = user ? "New password" : "Password";
    $("#u-password-hint").hidden = !user;

    if (user) {
      form.username.value = user.username;
      form.email.value = user.email;
      form.role.value = user.role;
    }
    // Admins can't demote themselves (the server blocks it too)
    form.role.disabled = Boolean(user && me && user.id === me.id);
    $("#user-dialog").showModal();
    form.username.focus();
  }

  function showError(msg) {
    const el = $("#user-form-error");
    el.textContent = msg;
    el.hidden = false;
  }

  async function save(e) {
    e.preventDefault();
    const form = e.target;
    const payload = {
      username: form.username.value.trim(),
      email: form.email.value.trim(),
    };
    if (!form.role.disabled) payload.role = form.role.value;
    if (form.password.value) payload.password = form.password.value;

    if (!payload.username || !payload.email) return showError("Username and email are required.");
    if (!editingId && !payload.password) return showError("Please set a password.");
    if (payload.password && payload.password.length < 8) return showError("Password must be at least 8 characters.");

    const btn = $("#user-save-btn");
    btn.disabled = true;
    try {
      if (editingId) {
        await api("PUT", `/api/users/${editingId}`, payload);
        toast("User updated");
      } else {
        await api("POST", "/api/users", payload);
        toast("User added");
      }
      $("#user-dialog").close();
      await load();
      window.Dashboard?.reloadUsers(); // refresh the "Assign to" dropdown
      window.Dashboard?.reloadTasks(); // usernames may have changed
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Delete ----------
  let deletingId = null;

  function openDelete(user) {
    deletingId = user.id;
    const n = user.task_count;
    $("#user-confirm-text").textContent =
      `“${user.username}” will be removed and can no longer sign in.` +
      (n ? ` Their ${n} task${n === 1 ? "" : "s"} will become unassigned.` : "");
    $("#user-confirm-dialog").showModal();
  }

  async function confirmDelete() {
    const btn = $("#user-confirm-delete");
    btn.disabled = true;
    try {
      await api("DELETE", `/api/users/${deletingId}`);
      toast("User deleted");
      $("#user-confirm-dialog").close();
      await load();
      window.Dashboard?.reloadUsers();
      window.Dashboard?.reloadTasks();
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Wiring ----------
  document.addEventListener("click", (e) => {
    const t = e.target;
    if (t.closest("[data-action='new-user']")) return openDialog();
    const edit = t.closest("[data-user-edit]");
    if (edit) return openDialog(users.find((u) => u.id === Number(edit.dataset.userEdit)));
    const del = t.closest("[data-user-delete]");
    if (del && !del.disabled) return openDelete(users.find((u) => u.id === Number(del.dataset.userDelete)));
  });

  $("#role-filters").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-role-filter]");
    if (!btn) return;
    $$("#role-filters .filter").forEach((f) => f.classList.toggle("active", f === btn));
    roleFilter = btn.dataset.roleFilter;
    renderRows();
  });

  $("#search").addEventListener("input", (e) => {
    query = e.target.value.trim().toLowerCase();
    renderRows();
  });

  $("#user-form").addEventListener("submit", save);
  $("#user-confirm-delete").addEventListener("click", confirmDelete);

  document.addEventListener("view:show", (e) => {
    if (e.detail === "users") load();
  });

  // Know who "me" is (to mark "You" and block self-delete), and show the user count early
  me = Auth.user();
  renderPermissions();
  if (Auth.hasScope("users:manage")) load();
})();
