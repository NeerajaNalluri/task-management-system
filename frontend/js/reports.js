// Admin "Reports" view (needs the reports:read scope).
// Charts are plain HTML bars; hover any bar segment for exact numbers.

(() => {
  const { $, icon, esc, STATUS_LABEL, CATEGORY_LABEL, parseDate, fmtDate, initials, cap, toast, api } = UI;
  if (!$("[data-view-panel='reports']")) return; // only on admin.html

  const STATUSES = ["todo", "in_progress", "done"];
  const pct = (n, total) => (total ? Math.round((n / total) * 100) : 0);

  // ---------- Tooltip (one shared element) ----------
  const tip = document.createElement("div");
  tip.className = "chart-tip";
  tip.hidden = true;
  document.body.appendChild(tip);

  document.addEventListener("pointermove", (e) => {
    const target = e.target.closest?.("[data-tip]");
    if (!target) return void (tip.hidden = true);
    tip.innerHTML = target.dataset.tip;
    tip.hidden = false;
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = Math.max(8, e.clientY - tip.offsetHeight - 12);
    tip.style.transform = `translate(${x}px, ${y}px)`;
  });

  // A stacked bar: segments sized by count, 2px gaps, rounded ends
  function stackedBar(parts, scaleTotal, label) {
    const total = parts.reduce((n, p) => n + p.value, 0);
    const width = scaleTotal ? (total / scaleTotal) * 100 : 0;
    const segs = parts
      .filter((p) => p.value > 0)
      .map(
        (p) =>
          `<span class="seg ${p.key}" style="flex:${p.value}" data-tip="<b>${esc(label)}</b><br>${p.name}: ${p.value} (${pct(p.value, total)}%)"></span>`
      )
      .join("");
    return `<div class="sbar-track"><div class="sbar" style="width:${width}%">${segs}</div></div>`;
  }

  const legend = () =>
    `<ul class="chart-legend">${STATUSES.map((s) => `<li><span class="dot ${s}"></span>${STATUS_LABEL[s]}</li>`).join("")}</ul>`;

  // ---------- Sections ----------
  function renderStats(t) {
    const cards = [
      { label: "Completion rate", value: `${t.completion_rate}%`, icon: "target", tone: "done" },
      { label: "Overdue", value: t.overdue, icon: "alert", tone: t.overdue ? "danger" : "todo" },
      { label: "Due in 7 days", value: t.due_this_week, icon: "calendar", tone: "progress" },
      { label: "Unassigned", value: t.unassigned, icon: "users", tone: "accent" },
    ];
    $("#report-stats").innerHTML = cards
      .map(
        (c) => `<div class="stat">
          <div class="stat-icon tone-${c.tone}">${icon(c.icon)}</div>
          <div><div class="stat-value">${c.value}</div><div class="stat-label">${c.label}</div></div>
        </div>`
      )
      .join("");
  }

  function renderStatus(t) {
    const parts = STATUSES.map((s) => ({ key: s, name: STATUS_LABEL[s], value: t[s] }));
    $("#report-status").innerHTML = t.total
      ? `<div class="big-number">${t.total}<span>tasks in total</span></div>
         ${stackedBar(parts, t.total, "All tasks")}
         <ul class="status-list">
           ${parts
             .map(
               (p) => `<li><span class="dot ${p.key}"></span>${p.name}<b>${p.value}</b><span class="muted">${pct(p.value, t.total)}%</span></li>`
             )
             .join("")}
         </ul>`
      : `<p class="empty">No tasks yet.</p>`;
  }

  function renderPriority(rows) {
    const totals = rows.map((r) => r.todo + r.in_progress + r.done);
    const max = Math.max(1, ...totals);
    $("#report-priority").innerHTML =
      legend() +
      `<div class="hbars">${rows
        .map((r, i) => {
          const parts = STATUSES.map((s) => ({ key: s, name: STATUS_LABEL[s], value: r[s] }));
          return `<div class="hbar-row">
            <span class="hbar-label"><span class="priority ${r.priority}">${icon("flag")} ${cap(r.priority)}</span></span>
            ${stackedBar(parts, max, `${cap(r.priority)} priority`)}
            <span class="hbar-value">${totals[i]}</span>
          </div>`;
        })
        .join("")}</div>`;
  }

  function renderCategory(rows) {
    const totals = rows.map((r) => r.todo + r.in_progress + r.done);
    const max = Math.max(1, ...totals);
    $("#report-category").innerHTML =
      legend() +
      `<div class="hbars">${rows
        .map((r, i) => {
          const parts = STATUSES.map((s) => ({ key: s, name: STATUS_LABEL[s], value: r[s] }));
          const name = CATEGORY_LABEL[r.category] || r.category;
          return `<div class="hbar-row wide">
            <span class="hbar-label"><span class="tag">${esc(name)}</span></span>
            ${totals[i] ? stackedBar(parts, max, name) : `<span class="muted small-note">No tasks</span>`}
            <span class="hbar-value">${totals[i]}</span>
          </div>`;
        })
        .join("")}</div>`;
  }

  function renderPeople(people) {
    if (!people.length) {
      $("#report-people").innerHTML = `<p class="empty">No tasks yet.</p>`;
      return;
    }
    const max = Math.max(1, ...people.map((p) => p.total));
    $("#report-people").innerHTML = `
      <div class="card-body" style="padding-bottom:0">${legend()}</div>
      <table>
        <thead><tr>
          <th>Person</th><th class="hide-sm" style="width:38%">Workload</th>
          <th>To do</th><th>In progress</th><th>Done</th><th>Overdue</th><th>Total</th>
        </tr></thead>
        <tbody>${people
          .map((p) => {
            const parts = STATUSES.map((s) => ({ key: s, name: STATUS_LABEL[s], value: p[s] }));
            const unassigned = p.username === "Unassigned";
            return `<tr>
              <td>${
                unassigned
                  ? `<span class="unassigned">Unassigned</span>`
                  : `<span class="assignee"><span class="avatar">${esc(initials(p.username))}</span>${esc(p.username)}</span>`
              }</td>
              <td class="hide-sm">${stackedBar(parts, max, p.username)}</td>
              <td>${p.todo}</td><td>${p.in_progress}</td><td>${p.done}</td>
              <td>${p.overdue ? `<span class="due overdue">${p.overdue}</span>` : "0"}</td>
              <td><b>${p.total}</b></td>
            </tr>`;
          })
          .join("")}</tbody>
      </table>`;
  }

  function renderOverdue(list) {
    if (!list.length) {
      $("#report-overdue").innerHTML = `<div class="empty-state">${icon("check")}<p><b>Nothing overdue.</b><br>Every open task is on schedule.</p></div>`;
      return;
    }
    const today = new Date(); today.setHours(0, 0, 0, 0);
    $("#report-overdue").innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Task</th><th class="hide-sm">Assignee</th><th>Status</th><th>Due</th><th>Late by</th></tr></thead>
      <tbody>${list
        .map((t) => {
          const due = parseDate(t.due_date);
          const days = Math.round((today - due) / 86400000);
          return `<tr>
            <td><div class="task-title">${esc(t.title)}</div></td>
            <td class="hide-sm">${t.assignee ? esc(t.assignee) : '<span class="unassigned">Unassigned</span>'}</td>
            <td><span class="chip ${t.status}">${STATUS_LABEL[t.status]}</span></td>
            <td><span class="due overdue">${fmtDate(due)}</span></td>
            <td>${days} day${days === 1 ? "" : "s"}</td>
          </tr>`;
        })
        .join("")}</tbody></table></div>`;
  }

  async function load() {
    try {
      const data = await api("GET", "/api/reports/summary");
      renderStats(data.totals);
      renderStatus(data.totals);
      renderPriority(data.by_priority);
      renderCategory(data.by_category);
      renderPeople(data.by_assignee);
      renderOverdue(data.overdue);
      $("#report-subtitle").textContent = `A live summary of every task · updated ${new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
    } catch (err) {
      toast(err.message);
    }
  }

  $("#report-refresh").addEventListener("click", async () => {
    await load();
    toast("Report refreshed");
  });

  document.addEventListener("view:show", (e) => {
    if (e.detail === "reports") load();
  });
})();
