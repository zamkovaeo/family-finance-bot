const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const state = {
  telegramId: null,
  txType: "expense",
  categories: { expense: [], income: [] },
  selectedCategory: null,
  analytics: null,
  history: [],
  members: [],
};

const colors = ["#18c08f", "#ffad32", "#ff5b5b", "#48a5ff", "#a777ff", "#f05d9b", "#47d7c5"];

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];

function money(value) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽`;
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatDateISO(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function currentMonthStartISO() {
  const date = new Date();
  return formatDateISO(new Date(date.getFullYear(), date.getMonth(), 1));
}

function currentMonthEndISO() {
  const date = new Date();
  return formatDateISO(new Date(date.getFullYear(), date.getMonth() + 1, 0));
}

function daysAgoISO(days) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return formatDateISO(date);
}

function nextMonthISO() {
  const date = new Date();
  date.setMonth(date.getMonth() + 1, 1);
  return date.toISOString().slice(0, 7);
}

function showToast(text) {
  const toast = qs("#toast");
  toast.textContent = text;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Ошибка запроса");
  }
  return response.json();
}

async function bootstrap() {
  const user = tg?.initDataUnsafe?.user;
  if (user?.id) {
    state.telegramId = user.id;
    await api("/miniapp/bootstrap", {
      method: "POST",
      body: JSON.stringify({
        telegram_id: user.id,
        username: user.username,
        first_name: user.first_name,
      }),
    });
  } else {
    qs("#dev-login").classList.remove("hidden");
    const saved = localStorage.getItem("devTelegramId");
    if (saved) state.telegramId = Number(saved);
  }

  qs("#tx-date").value = todayISO();
  qs("#history-from").value = currentMonthStartISO();
  qs("#history-to").value = currentMonthEndISO();
  qs("#history-scope").value = "";
  qs("#history-member").value = "";
  qs("#history-type").value = "";
  qs("#budget-month").value = nextMonthISO();

  bindEvents();
  if (state.telegramId) await loadAll();
}

function bindEvents() {
  qsa("[data-tab]").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
  qsa("[data-type]").forEach((button) => button.addEventListener("click", () => setTxType(button.dataset.type)));
  qs("#save-transaction").addEventListener("click", saveTransaction);
  qs("#save-budget-plan").addEventListener("click", saveBudgetPlan);
  qs("#save-goal").addEventListener("click", saveGoal);
  qs("#budget-month").addEventListener("change", loadBudgetTemplate);
  qs("#apply-history-filters").addEventListener("click", loadHistory);
  ["#history-from", "#history-to", "#history-category", "#history-scope", "#history-member", "#history-type"].forEach((selector) =>
    qs(selector).addEventListener("change", loadHistory),
  );
  qs("#refresh-button").addEventListener("click", loadAll);
  qs("#dev-login-button").addEventListener("click", async () => {
    const value = qs("#dev-telegram-id").value.trim();
    if (!value) return;
    state.telegramId = Number(value);
    localStorage.setItem("devTelegramId", value);
    await api("/miniapp/bootstrap", {
      method: "POST",
      body: JSON.stringify({ telegram_id: state.telegramId, first_name: "Dev" }),
    });
    qs("#dev-login").classList.add("hidden");
    await loadAll();
  });
}

function switchTab(tab) {
  qsa(".screen").forEach((screen) => screen.classList.remove("active"));
  qsa(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.tab === tab));
  qs(`#screen-${tab}`)?.classList.add("active");
  qs("#screen-title").textContent = {
    dashboard: "Бюджет",
    operation: "Операция",
    budget: "План месяца",
    history: "История",
    analytics: "Аналитика",
    goals: "Цели",
  }[tab];
}

function setTxType(type) {
  state.txType = type;
  qsa("[data-type]").forEach((button) => button.classList.toggle("active", button.dataset.type === type));
  renderCategoryPicker();
}

async function loadAll() {
  if (!state.telegramId) return;
  const [categories, members, budget, analytics, goals] = await Promise.all([
    api(`/miniapp/categories/${state.telegramId}`),
    api(`/miniapp/family-members/${state.telegramId}`),
    api(`/budget/${state.telegramId}`),
    api(`/analytics/${state.telegramId}`),
    api(`/goals/${state.telegramId}`),
  ]);
  state.categories = categories;
  state.members = members.items || [];
  state.analytics = analytics;
  renderHistoryCategoryFilter();
  renderHistoryMemberFilter();
  renderCategoryPicker();
  renderBudget(budget.items);
  renderAnalytics(analytics);
  renderGoals(goals.items);
  await loadHistory();
  await loadBudgetTemplate();
}

function renderHistoryCategoryFilter() {
  const categorySelect = qs("#history-category");
  const selected = categorySelect.value;
  const categories = [...(state.categories.expense || []), ...(state.categories.income || [])];
  const seen = new Set();
  const options = [`<option value="">Все категории</option>`];
  categories.forEach((item) => {
    if (seen.has(item.name)) return;
    seen.add(item.name);
    options.push(`<option value="${item.name}">${item.emoji} ${item.name}</option>`);
  });
  categorySelect.innerHTML = options.join("");
  categorySelect.value = categories.some((item) => item.name === selected) ? selected : "";
}

function renderHistoryMemberFilter() {
  const memberSelect = qs("#history-member");
  const selected = memberSelect.value;
  const options = [`<option value="">Все участники</option>`];
  state.members.forEach((member) => {
    const label = member.is_current ? `${member.name} (я)` : member.name;
    options.push(`<option value="${member.id}">${label}</option>`);
  });
  memberSelect.innerHTML = options.join("");
  memberSelect.value = state.members.some((member) => member.id === selected) ? selected : "";
}

function renderCategoryPicker() {
  const list = state.categories[state.txType] || [];
  if (!state.selectedCategory || !list.some((item) => item.name === state.selectedCategory)) {
    state.selectedCategory = list[0]?.name || null;
  }
  qs("#category-picker").innerHTML = list
    .map(
      (item) =>
        `<button class="chip ${item.name === state.selectedCategory ? "active" : ""}" data-category="${item.name}">${item.emoji} ${item.name}</button>`,
    )
    .join("");
  qsa("[data-category]").forEach((button) =>
    button.addEventListener("click", () => {
      state.selectedCategory = button.dataset.category;
      renderCategoryPicker();
    }),
  );
}

function renderBudget(items) {
  const list = qs("#budget-list");
  if (!items.length) {
    list.innerHTML = `<p class="muted">Лимиты пока не заданы. Откройте вкладку “План”.</p>`;
    return;
  }
  list.innerHTML = items
    .map((item) => {
      const percent = Math.max(0, Math.min(100, item.percent || 0));
      return `<div class="budget-row">
        <div class="row-title"><strong>${item.category}</strong><span>${Math.round(percent)}%</span></div>
        <div class="progress"><span style="width:${percent}%"></span></div>
        <div class="row-title muted"><span>${money(item.spent)} из ${money(item.limit)}</span><span>${money(item.left)}</span></div>
      </div>`;
    })
    .join("");
}

function renderAnalytics(data) {
  qs("#balance-value").textContent = data.summary.balance || "0 ₽";
  qs("#expense-value").textContent = data.summary.expense || "0 ₽";
  renderDonut(data.categories || []);
  renderDailyBars(data.categories || []);
  renderMonthBars(data.months || []);
}

function renderDonut(categories) {
  const svg = qs("#category-donut");
  const total = categories.reduce((sum, item) => sum + Number(item.amount), 0);
  if (!total) {
    svg.innerHTML = `<circle cx="60" cy="60" r="38" fill="none" stroke="#233b47" stroke-width="18" />`;
    qs("#category-legend").innerHTML = `<p class="muted">Расходов пока нет</p>`;
    return;
  }
  let offset = 25;
  svg.innerHTML = categories
    .map((item, index) => {
      const value = (Number(item.amount) / total) * 100;
      const circle = `<circle cx="60" cy="60" r="38" fill="none" stroke="${colors[index % colors.length]}" stroke-width="18" stroke-dasharray="${value} ${100 - value}" stroke-dashoffset="${offset}" pathLength="100" />`;
      offset -= value;
      return circle;
    })
    .join("");
  svg.innerHTML += `<circle cx="60" cy="60" r="26" fill="#10212b" /><text x="60" y="57" text-anchor="middle" fill="#f5fbff" font-size="12">${money(total)}</text><text x="60" y="72" text-anchor="middle" fill="#90a7b2" font-size="8">всего</text>`;
  qs("#category-legend").innerHTML = categories
    .slice(0, 7)
    .map(
      (item, index) =>
        `<div class="legend-item"><span><i class="legend-swatch" style="background:${colors[index % colors.length]}"></i>${item.name}</span><span>${money(item.amount)}</span></div>`,
    )
    .join("");
}

function renderDailyBars(categories) {
  const svg = qs("#daily-bars");
  const values = categories.slice(0, 10).map((item) => Number(item.amount));
  const max = Math.max(...values, 1);
  svg.innerHTML = values
    .map((value, index) => {
      const height = (value / max) * 120;
      const x = 14 + index * 30;
      return `<rect x="${x}" y="${140 - height}" width="14" height="${height}" rx="5" fill="${colors[index % colors.length]}"></rect>`;
    })
    .join("");
}

function renderMonthBars(months) {
  const svg = qs("#month-bars");
  const max = Math.max(...months.map((item) => Number(item.income) + Number(item.expense)), 1);
  svg.innerHTML = months
    .map((item, index) => {
      const x = 20 + index * 48;
      const incomeHeight = (Number(item.income) / max) * 125;
      const expenseHeight = (Number(item.expense) / max) * 125;
      return `<rect x="${x}" y="${145 - incomeHeight}" width="24" height="${incomeHeight}" rx="4" fill="#18c08f"></rect>
        <rect x="${x}" y="${145 - incomeHeight - expenseHeight}" width="24" height="${expenseHeight}" rx="4" fill="#ff5b5b"></rect>
        <text x="${x + 12}" y="164" text-anchor="middle" fill="#90a7b2" font-size="9">${item.month.slice(0, 2)}</text>`;
    })
    .join("");
}

async function saveTransaction() {
  const amount = Number(qs("#tx-amount").value.replace(",", "."));
  if (!amount || !state.selectedCategory) {
    showToast("Заполните сумму и категорию");
    return;
  }
  await api("/miniapp/transactions", {
    method: "POST",
    body: JSON.stringify({
      telegram_id: state.telegramId,
      amount,
      type: state.txType,
      category: state.selectedCategory,
      date: new Date(`${qs("#tx-date").value}T12:00:00`).toISOString(),
      comment: qs("#tx-comment").value.trim() || state.selectedCategory,
      tag: qs("#tx-tag").value.trim() || null,
      is_personal: qs("#tx-personal").checked,
    }),
  });
  qs("#tx-amount").value = "";
  qs("#tx-comment").value = "";
  qs("#tx-tag").value = "";
  showToast("Операция сохранена");
  await loadAll();
  switchTab("dashboard");
}

async function loadHistory() {
  if (!state.telegramId) return;
  const params = new URLSearchParams();
  const from = qs("#history-from").value;
  const to = qs("#history-to").value;
  const category = qs("#history-category").value;
  const scope = qs("#history-scope").value;
  const memberId = qs("#history-member").value;
  const txType = qs("#history-type").value;
  if (from) params.set("date_from", new Date(`${from}T00:00:00`).toISOString());
  if (to) params.set("date_to", new Date(`${to}T23:59:59`).toISOString());
  if (category) params.set("category", category);
  if (scope) params.set("scope", scope);
  if (memberId) params.set("member_id", memberId);
  if (txType) params.set("tx_type", txType);
  const data = await api(`/miniapp/transactions/${state.telegramId}?${params.toString()}`);
  state.history = data.items || [];
  qs("#history-income").textContent = money(data.summary.income);
  qs("#history-expense").textContent = money(data.summary.expense);
  qs("#history-balance").textContent = money(data.summary.balance);
  renderHistory();
}

function renderHistory() {
  const list = qs("#history-list");
  if (!state.history.length) {
    list.innerHTML = `<p class="muted">За выбранный период операций нет</p>`;
    return;
  }
  let currentDay = "";
  list.innerHTML = state.history
    .map((tx) => {
      const date = new Date(tx.date);
      const day = date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
      const header = day !== currentDay ? `<div class="history-day">${day}</div>` : "";
      currentDay = day;
      const isIncome = tx.type === "income";
      const sign = isIncome ? "+" : "-";
      const scope = tx.is_personal ? "Личное" : "Семейное";
      const user = tx.user ? ` · ${tx.user}` : "";
      const tag = tx.tag ? ` · #${tx.tag}` : "";
      return `${header}<div class="history-item">
        <div class="history-icon">${tx.emoji}</div>
        <div class="history-main">
          <div class="row-title"><strong>${tx.comment || tx.category}</strong><span class="${isIncome ? "income" : "expense"}">${sign}${money(tx.amount)}</span></div>
          <div class="history-meta">${tx.category} · ${scope}${user}${tag}</div>
        </div>
      </div>`;
    })
    .join("");
}

async function loadBudgetTemplate() {
  if (!state.telegramId) return;
  const month = qs("#budget-month").value || nextMonthISO();
  const data = await api(`/miniapp/budget-template/${state.telegramId}?month=${month}`);
  qs("#budget-editor").innerHTML = data.items
    .map(
      (item) => `<div class="budget-edit-row">
        <span>${item.emoji} ${item.category}</span>
        <input data-budget-category="${item.category}" inputmode="decimal" value="${Number(item.amount) || ""}" />
      </div>`,
    )
    .join("");
  qsa("[data-budget-category]").forEach((input) => input.addEventListener("input", updateBudgetTotal));
  updateBudgetTotal();
}

function updateBudgetTotal() {
  const total = qsa("[data-budget-category]").reduce((sum, input) => sum + Number(input.value.replace(",", ".") || 0), 0);
  qs("#budget-total").textContent = money(total);
}

async function saveBudgetPlan() {
  const month = qs("#budget-month").value;
  const items = qsa("[data-budget-category]")
    .map((input) => ({ category: input.dataset.budgetCategory, amount: Number(input.value.replace(",", ".") || 0) }))
    .filter((item) => item.amount > 0);
  if (!month || !items.length) {
    showToast("Укажите месяц и хотя бы одну сумму");
    return;
  }
  const total = items.reduce((sum, item) => sum + item.amount, 0);
  if (!confirm(`Сохранить ${items.length} категорий на ${money(total)}?`)) return;
  await api("/miniapp/budget-plan", {
    method: "POST",
    body: JSON.stringify({
      telegram_id: state.telegramId,
      month: new Date(`${month}-01T12:00:00`).toISOString(),
      items,
    }),
  });
  showToast("План сохранен");
  await loadAll();
}

function renderGoals(items) {
  const list = qs("#goals-list");
  if (!items.length) {
    list.innerHTML = `<p class="muted">Целей пока нет</p>`;
    return;
  }
  list.innerHTML = items
    .map((goal) => {
      const percent = Math.min(100, (Number(goal.current_amount) / Number(goal.target_amount || 1)) * 100);
      return `<div class="goal-row">
        <div class="row-title"><strong>🎯 ${goal.title}</strong><span>${Math.round(percent)}%</span></div>
        <div class="progress"><span style="width:${percent}%"></span></div>
        <div class="muted">${money(goal.current_amount)} из ${money(goal.target_amount)}</div>
      </div>`;
    })
    .join("");
}

async function saveGoal() {
  const title = qs("#goal-title").value.trim();
  const amount = Number(qs("#goal-amount").value.replace(",", "."));
  if (!title || !amount) {
    showToast("Заполните название и сумму цели");
    return;
  }
  await api("/goals", {
    method: "POST",
    body: JSON.stringify({ telegram_id: state.telegramId, title, target_amount: amount }),
  });
  qs("#goal-title").value = "";
  qs("#goal-amount").value = "";
  showToast("Цель добавлена");
  await loadAll();
}

bootstrap().catch((error) => showToast(error.message));
