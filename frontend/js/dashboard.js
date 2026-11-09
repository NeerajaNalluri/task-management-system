// Shared logic for admin.html and user.html.
// The page's <body data-role="..."> decides which features are shown.
// Every API call goes through Auth.request(), which attaches the Bearer token.

(() => {
  const ROLE = document.body.dataset.role; // "admin" or "user"
  const IS_ADMIN = ROLE === "admin";
  const { $, $$, icon, paintIcons, esc, STATUS_LABEL, CATEGORY_LABEL, today, parseDate, fmtDate, initials, isOverdue, cap, toast, api } = UI;

  // ---------- State ----------
  let tasks = [];
  let users = [];
  let filter = "all";
  let query = "";

  async function loadTasks() {
    try {
      const data = await api("GET", "/api/tasks");
      tasks = data.map((t) => ({ ...t, due: parseDate(t.due_date) }));
    } catch (err) {
      toast(err.message);
    }
    renderAll();
  }

  function renderAll() {
    renderStats();
    renderTable();
    renderProgress();
    renderDeadlines();
  }

  // ---------- Header / profile ----------
  function renderProfile(user) {
    const hour = new Date().getHours();
    const part = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
    $("[data-greeting]").textContent = `Good ${part}, ${user.username}`;
    $$("[data-username]").forEach((el) => (el.textContent = user.username));
    $$("[data-initials]").forEach((el) => (el.textContent = initials(user.username)));
  }

  // ---------- Stats ----------
  function renderStats() {
    const count = (s) => tasks.filter((t) => t.status === s).length;
    const cards = [
      { label: "Total tasks", value: tasks.length, icon: "layers", tone: "accent" },
      { label: "To do", value: count("todo"), icon: "circle", tone: "todo" },
      { label: "In progress", value: count("in_progress"), icon: "clock", tone: "progress" },
      { label: "Completed", value: count("done"), icon: "check", tone: "done" },
    ];
    $("#stats").innerHTML = cards
      .map(
        (c) => `<div class="stat">
          <div class="stat-icon tone-${c.tone}">${icon(c.icon)}</div>
          <div><div class="stat-value">${c.value}</div><div class="stat-label">${c.label}</div></div>
        </div>`
      )
      .join("");
    $$("[data-count='all']").forEach((el) => (el.textContent = tasks.length));
  }

  // ---------- Task table ----------
  function renderTable() {
    const cols = IS_ADMIN ? 6 : 5;
    const rows = tasks
      .filter((t) => filter === "all" || t.status === filter)
      .filter((t) => !query || `${t.title} ${t.description} ${t.assignee || ""} ${CATEGORY_LABEL[t.category] || ""}`.toLowerCase().includes(query));

    if (!rows.length) {
      const msg = tasks.length ? "No tasks match." : IS_ADMIN ? "No tasks yet. Click “New task” to add one." : "No tasks yet.";
      $("#task-rows").innerHTML = `<tr><td colspan="${cols}" class="empty">${msg}</td></tr>`;
      return;
    }

    $("#task-rows").innerHTML = rows
      .map(
        (t) => `<tr>
          <td>
            <div class="task-title">${esc(t.title)} <span class="tag cat-${esc(t.category)}">${esc(CATEGORY_LABEL[t.category] || t.category)}</span></div>
            ${t.description ? `<div class="task-desc">${esc(t.description)}</div>` : ""}
          </td>
          <td class="hide-sm">${
            t.assignee
              ? `<span class="assignee"><span class="avatar">${esc(initials(t.assignee))}</span>${esc(t.assignee)}</span>`
              : `<span class="unassigned">Unassigned</span>`
          }</td>
          <td><span class="chip ${t.status}">${STATUS_LABEL[t.status]}</span></td>
          <td class="hide-sm"><span class="priority ${t.priority}">${icon("flag")} ${cap(t.priority)}</span></td>
          <td class="hide-sm"><span class="due ${isOverdue(t) ? "overdue" : ""}">${t.due ? fmtDate(t.due) : "—"}${isOverdue(t) ? " · overdue" : ""}</span></td>
          ${
            IS_ADMIN
              ? `<td class="actions">
                  <button class="icon-btn" title="Edit" data-edit="${t.id}">${icon("edit")}</button>
                  <button class="icon-btn danger" title="Delete" data-delete="${t.id}">${icon("trash")}</button>
                </td>`
              : ""
          }
        </tr>`
      )
      .join("");
  }

  // ---------- Admin: progress ring ----------
  function renderProgress() {
    const el = $("#progress");
    if (!el) return;
    const count = (s) => tasks.filter((t) => t.status === s).length;
    const pct = tasks.length ? Math.round((count("done") / tasks.length) * 100) : 0;
    el.innerHTML = `<div class="ring-wrap">
        <div class="ring" style="--pct:${pct}"><span>${pct}%</span></div>
        <ul class="legend">
          <li><span class="dot" style="background:var(--done)"></span>Completed <b>${count("done")}</b></li>
          <li><span class="dot" style="background:var(--progress)"></span>In progress <b>${count("in_progress")}</b></li>
          <li><span class="dot" style="background:var(--todo)"></span>To do <b>${count("todo")}</b></li>
          <li><span class="dot" style="background:var(--danger)"></span>Overdue <b>${tasks.filter(isOverdue).length}</b></li>
        </ul>
      </div>`;
  }

  // ---------- User: upcoming deadlines ----------
  function renderDeadlines() {
    const el = $("#deadlines");
    if (!el) return;
    const upcoming = tasks.filter((t) => t.status !== "done" && t.due).sort((a, b) => a.due - b.due).slice(0, 4);
    el.innerHTML =
      upcoming
        .map(
          (t) => `<li>
          <div class="date-box"><b>${t.due.getDate()}</b><small>${t.due.toLocaleDateString(undefined, { month: "short" })}</small></div>
          <div><div class="t">${esc(t.title)}</div><div class="s">${STATUS_LABEL[t.status]}${isOverdue(t) ? " · <span class='due overdue'>overdue</span>" : ""}</div></div>
        </li>`
        )
        .join("") || `<li class="muted">Nothing due. Nice!</li>`;
  }

  // ---------- Admin: create / edit dialog ----------
  let editingId = null;

  async function loadUsers() {
    try {
      users = await api("GET", "/api/users");
    } catch {
      users = [];
    }
    $("#f-assignee").innerHTML =
      `<option value="">Unassigned</option>` +
      users.map((u) => `<option value="${u.id}">${esc(u.username)} (${u.role})</option>`).join("");
  }

  function openTaskDialog(task = null) {
    editingId = task ? task.id : null;
    const form = $("#task-form");
    form.reset();
    $("#form-error").hidden = true;
    $("#dialog-title").textContent = task ? "Edit task" : "New task";
    $("#save-btn").textContent = task ? "Save changes" : "Create task";

    if (task) {
      form.title.value = task.title;
      form.description.value = task.description || "";
      form.status.value = task.status;
      form.priority.value = task.priority;
      form.category.value = task.category || "general";
      form.due_date.value = task.due_date || "";
      form.assigned_to.value = task.assigned_to ?? "";
    }
    $("#task-dialog").showModal();
    form.title.focus();
  }

  async function saveTask(e) {
    e.preventDefault();
    const form = e.target;
    const errorEl = $("#form-error");
    const payload = {
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      status: form.status.value,
      priority: form.priority.value,
      category: form.category.value,
      due_date: form.due_date.value || null,
      assigned_to: form.assigned_to.value ? Number(form.assigned_to.value) : null,
    };
    if (!payload.title) {
      errorEl.textContent = "Please enter a title.";
      errorEl.hidden = false;
      form.title.focus();
      return;
    }

    const btn = $("#save-btn");
    btn.disabled = true;
    try {
      if (editingId) {
        await api("PUT", `/api/tasks/${editingId}`, payload);
        toast("Task updated");
      } else {
        await api("POST", "/api/tasks", payload);
        toast("Task created");
      }
      $("#task-dialog").close();
      await loadTasks();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Admin: delete ----------
  let deletingId = null;

  function openDeleteDialog(task) {
    deletingId = task.id;
    $("#confirm-text").textContent = `“${task.title}” will be permanently deleted.`;
    $("#confirm-dialog").showModal();
  }

  async function confirmDelete() {
    const btn = $("#confirm-delete");
    btn.disabled = true;
    try {
      await api("DELETE", `/api/tasks/${deletingId}`);
      toast("Task deleted");
      $("#confirm-dialog").close();
      await loadTasks();
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Views (admin page has Dashboard, Users, Reports) ----------
  // A hash like #users or #reports switches view; any other hash (#tasks, #deadlines-card)
  // stays on the dashboard and scrolls to that section.
  const VIEWS = ["dashboard", "users", "reports"];
  const SEARCH_HINT = { dashboard: "Search tasks…", users: "Search users…", reports: "Search tasks…" };
  let currentView = null;

  function route() {
    const hash = location.hash.slice(1);
    const view = VIEWS.includes(hash) ? hash : "dashboard";

    $$("[data-view-panel]").forEach((p) => (p.hidden = p.dataset.viewPanel !== view));
    $$(".nav-item").forEach((a) => {
      const href = a.getAttribute("href");
      const active = hash && !VIEWS.includes(hash) ? href === `#${hash}` : a.dataset.view === view;
      a.classList.toggle("active", active);
    });

    if (view !== currentView) {
      const search = $("#search");
      search.placeholder = SEARCH_HINT[view];
      if (search.value) { search.value = ""; search.dispatchEvent(new Event("input")); }
      $(".search").style.visibility = view === "reports" ? "hidden" : "";
      currentView = view;
      document.dispatchEvent(new CustomEvent("view:show", { detail: view }));
    }

    if (hash && !VIEWS.includes(hash)) document.getElementById(hash)?.scrollIntoView({ behavior: "smooth" });
    else window.scrollTo(0, 0);
  }

  // ---------- Wiring ----------
  function bindUI() {
    window.addEventListener("hashchange", route);
    $$("[data-logout]").forEach((b) => b.addEventListener("click", Auth.logout));

    $("#filters").addEventListener("click", (e) => {
      const btn = e.target.closest(".filter");
      if (!btn) return;
      $$(".filter").forEach((f) => f.classList.toggle("active", f === btn));
      filter = btn.dataset.filter;
      renderTable();
    });

    $("#search").addEventListener("input", (e) => {
      query = e.target.value.trim().toLowerCase();
      renderTable();
    });

    const sidebar = $("#sidebar"), backdrop = $("#backdrop");
    const toggle = (open) => { sidebar.classList.toggle("open", open); backdrop.classList.toggle("show", open); };
    $("#menu-btn").addEventListener("click", () => toggle(true));
    backdrop.addEventListener("click", () => toggle(false));

    document.addEventListener("click", (e) => {
      const target = e.target;
      if (target.closest(".nav-item")) toggle(false); // close mobile menu after navigating

      if (target.closest("[data-soon]")) {
        e.preventDefault();
        toast("Coming in a later step");
        return;
      }
      if (!IS_ADMIN) return;

      if (target.closest("[data-action='new']")) {
        e.preventDefault();
        if (currentView !== "dashboard") location.hash = "dashboard";
        openTaskDialog();
      }
      const editBtn = target.closest("[data-edit]");
      if (editBtn) openTaskDialog(tasks.find((t) => t.id === Number(editBtn.dataset.edit)));
      const delBtn = target.closest("[data-delete]");
      if (delBtn) openDeleteDialog(tasks.find((t) => t.id === Number(delBtn.dataset.delete)));
      if (target.closest("[data-close]")) target.closest("dialog").close();
    });

    if (IS_ADMIN) {
      $("#task-form").addEventListener("submit", saveTask);
      $("#confirm-delete").addEventListener("click", confirmDelete);
    }
  }

  async function init() {
    paintIcons();
    $("#task-rows").innerHTML = `<tr><td colspan="${IS_ADMIN ? 6 : 5}" class="empty">Loading tasks…</td></tr>`;

    const user = await Auth.guard(ROLE); // redirects to login if the token is missing/invalid
    if (!user) return;

    renderProfile(user);
    bindUI();
    if (IS_ADMIN) loadUsers();
    route();
    await loadTasks();
  }

  // Lets users.js refresh tasks/assignee list after changing users
  window.Dashboard = { reloadTasks: loadTasks, reloadUsers: () => IS_ADMIN && loadUsers() };

  init();
})();
