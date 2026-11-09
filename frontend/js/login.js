(() => {
  // Already signed in? Go straight to the right dashboard.
  const existing = Auth.user();
  if (existing) window.location.href = `/${existing.role}.html`;

  let portal = "admin";
  const tabs = document.querySelectorAll(".tab");
  const form = document.getElementById("login-form");
  const errorEl = document.getElementById("error");
  const submit = document.getElementById("submit");

  tabs.forEach((tab) =>
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      portal = tab.dataset.portal;
      submit.textContent = `Sign in as ${portal === "admin" ? "Admin" : "User"}`;
      errorEl.hidden = true;
    })
  );

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.hidden = true;

    const username = form.username.value.trim();
    const password = form.password.value;
    if (!username || !password) {
      errorEl.textContent = "Please enter your username and password.";
      errorEl.hidden = false;
      return;
    }

    submit.disabled = true;
    try {
      const user = await Auth.login(username, password, portal);
      window.location.href = `/${user.role}.html`;
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
})();
