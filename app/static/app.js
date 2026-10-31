/* 大雪深埋 DXSM · AI 考研私人教练前端 — 纯原生 JS,无构建 */
"use strict";

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const esc = s => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");
const SUBJECTS = { math: "数学", cs408: "408", english: "英语", all: "通用", politics: "政治" };
const SUBJECT_TAG = { math: "", cs408: "green", english: "amber", all: "gray", politics: "purple" };
const STATUS_TXT = { not_started: "未学习", learning: "学习中", initial: "初步掌握",
  consolidating: "需要巩固", mostly: "基本掌握", mastered: "稳定掌握", reviewing: "初步掌握" };
const STATUS_COLOR = { not_started: "#8A93A0", learning: "#7FA3D0", initial: "#4F7B6A",
  consolidating: "#A36B1F", mostly: "#4F7B6A", mastered: "#2E5C4D", reviewing: "#4F7B6A" };
const STATUS_ORDER = ["not_started", "learning", "initial", "consolidating", "mostly", "mastered"];
const QTYPES = {
  math: ["概念", "计算", "证明", "综合应用"],
  cs408: ["概念", "计算", "综合"],
  english: ["定位错误", "逻辑理解错误", "词义误判", "选项辨析错误"],
};
const ERROR_REASONS = ["概念不清", "公式或定理使用错误", "计算失误", "推导不严谨",
  "建模或思路错误", "审题错误", "方法不熟练", "时间分配不合理", "知识遗忘", "暂时无法判断"];
const GRADES = [["again", "忘了"], ["hard", "勉强"], ["good", "会了"], ["easy", "轻松"]];
const LETTERS = ["A", "B", "C", "D", "E", "F"];
const WP_STATUS = { confirmed: ["有数据支持", "green"], suspected: ["待验证", "amber"],
  conflict: ["与练习矛盾", "purple"], unverified: ["证据不足", "gray"] };

async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) {
    const err = await res.json().catch(() => ({}));
    if (err.setup_required && currentView !== "setup") location.hash = "#setup";
    else if (err.auth_required && currentView !== "login") location.hash = "#login";
    throw new Error(err.error || "需要登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ("请求失败 " + res.status));
  return data;
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toast._tm);
  toast._tm = setTimeout(() => t.classList.remove("show"), 2400);
}
function todayStr(offset = 0) {
  const d = new Date(); d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}
function shiftDate(ds, days) {
  const d = new Date(ds + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}
function md(src) {
  let s = esc(src || "");
  s = s.replace(/^#{1,3} (.*)$/gm, "<h3>$1</h3>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/^- (.*)$/gm, "<li>$1</li>");
  s = s.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>");
  s = s.replace(/\n{2,}/g, "<br><br>").replace(/\n/g, "<br>");
  return s;
}
function typeset(el) {
  if (window.renderMathInElement) {
    renderMathInElement(el, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
      ],
      throwOnError: false,
    });
  }
}
function openModal(html) {
  $("#modal").innerHTML = html;
  $("#modal-mask").classList.add("show");
  $("#modal-mask").scrollTop = 0;
  typeset($("#modal"));
}
function closeModal() { $("#modal-mask").classList.remove("show"); }
document.addEventListener("click", e => { if (e.target.id === "modal-mask") closeModal(); });

/* ================= 主题 ================= */
function applyThemeToggle() {
  const btn = $("#theme-toggle");
  if (!btn) return;
  const cur = document.documentElement.getAttribute("data-theme");
  btn.textContent = cur === "dark" ? "☀️" : "🌙";
  btn.onclick = () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("dx-theme", next);
    btn.textContent = next === "dark" ? "☀️" : "🌙";
  };
}

/* ================= 路由 ================= */
const ROUTES = {};
let currentView = "home";
function navigate() {
  const parts = (location.hash.replace("#", "") || "home").split("/");
  const view = parts[0];
  currentView = view;
  $$(".nav-set a").forEach(a => a.classList.toggle("active", a.dataset.view === view));
  const fn = ROUTES[view] || ROUTES.home;
  $("#view").innerHTML = '<div class="muted" style="padding:40px 0">加载中…</div>';
  window.scrollTo(0, 0);
  // 页面进入动效:重触发 CSS 动画(轻量,不阻塞操作)
  const v = $("#view");
  v.classList.remove("page-enter");
  void v.offsetWidth;
  v.classList.add("page-enter");
  Promise.resolve(fn(parts.slice(1).join("/"))).catch(err => {
    $("#view").innerHTML = '<div class="card" style="color:var(--red)">加载失败:' + esc(err.message) +
      '<br><span class="muted">请确认服务已启动:在个人平台目录运行 <code>python run.py</code></span></div>';
  });
  if (view !== "login" && view !== "setup") refreshDueBadge();
}
window.addEventListener("hashchange", navigate);

async function refreshDueBadge() {
  try {
    const s = await api("/practice/session");
    const n = s.due_mistakes.length + s.due_vocab.length;
    const el = $("#nav-due");
    el.textContent = n ? "待刷 " + n : "已清空 ✓";
    el.classList.toggle("zero", !n);
  } catch (e) { /* 未登录/离线时静默 */ }
}

/* ================= 登录 / 初始化 ================= */
ROUTES.login = async () => {
  $("#view").innerHTML = '<div class="quiz-wrap" style="max-width:420px;margin-top:9vh">'
    + '<div class="card quiz-card" style="text-align:center">'
    + '<div style="font-size:40px">❄️</div><h2 style="font-family:var(--font-serif);margin:8px 0 2px">大雪深埋</h2>'
    + '<p class="muted">DXSM · 登录后继续你的备考</p>'
    + '<label style="text-align:left">用户名</label><input id="login-user" value="" style="width:100%;padding:11px">'
    + '<label style="text-align:left">密码</label><input id="login-pass" type="password" style="width:100%;padding:11px">'
    + '<div class="toolbar" style="justify-content:center;margin-top:16px"><button class="primary" id="login-btn" style="padding:11px 40px">登录</button></div>'
    + '<p class="muted" id="login-err" style="color:var(--red)"></p></div></div>';
  const go = async () => {
    try {
      await api("/login", { method: "POST", body: {
        username: $("#login-user").value.trim(), password: $("#login-pass").value } });
      location.hash = "#home"; navigate();
    } catch (e) { $("#login-err").textContent = e.message; }
  };
  $("#login-btn").onclick = go;
  $("#login-pass").onkeydown = e => { if (e.key === "Enter") go(); };
  $("#login-user").focus();
};

ROUTES.setup = async () => {
  $("#view").innerHTML = '<div class="quiz-wrap" style="max-width:440px;margin-top:8vh">'
    + '<div class="card quiz-card" style="text-align:center">'
    + '<div style="font-size:40px">🏔️</div><h2 style="font-family:var(--font-serif);margin:8px 0 2px">大雪深埋</h2>'
    + '<p class="muted">首次使用:创建管理员账号。此账号将保护你的全部学习数据。</p>'
    + '<label style="text-align:left">用户名</label><input id="su-user" value="" style="width:100%;padding:11px">'
    + '<label style="text-align:left">密码(至少 6 位)</label><input id="su-pass" type="password" style="width:100%;padding:11px">'
    + '<div class="toolbar" style="justify-content:center;margin-top:16px"><button class="primary" id="su-btn" style="padding:11px 40px">创建并进入</button></div>'
    + '<p class="muted" id="su-err" style="color:var(--red)"></p></div></div>';
  const go = async () => {
    try {
      await api("/setup", { method: "POST", body: {
        username: $("#su-user").value.trim(), password: $("#su-pass").value } });
      location.hash = "#home"; navigate();
    } catch (e) { $("#su-err").textContent = e.message; }
  };
  $("#su-btn").onclick = go;
  $("#su-pass").onkeydown = e => { if (e.key === "Enter") go(); };
};

/* ================= 今日作战室 ================= */
ROUTES.home = async () => {
  const [session, prof, plan, goals, motivation, catalog, settings, unis, timeline] = await Promise.all([
    api("/practice/session"), api("/profile"), api("/plan/day/" + todayStr()),
    api("/goals"), api("/motivation/daily"), api("/catalog"), api("/settings"),
    api("/universities"), api("/growth/timeline"),
  ]);
  const phase = session.exam_phase;
  const due = session.due_mistakes.length + session.due_vocab.length;
  const topWeak = (prof.weak_points || []).slice(0, 4);
  const verified = (prof.weak_points || []).filter(w => w.status === "confirmed").length;
  const doneToday = (plan.tasks || []).filter(t => t.status === "done").length;
  const nextTask = (plan.tasks || []).find(t => t.status === "pending");
  const inst = goals.institution;

  // 连续学习天数:从真实活动日期倒推
  const activeDays = new Set(timeline.map(d => d.date).filter(Boolean));
  let streak = 0;
  for (let i = 0; ; i++) {
    const ds = todayStr(-i);
    if (activeDays.has(ds)) streak++;
    else if (i > 0 || !activeDays.has(todayStr())) break;
    else break;
  }
  const targetUni = goals.institution
    ? unis.find(u => u.name === goals.institution) : (unis[0] || null);
  const week = (prof.trend_14d || []).slice(-7);
  const weekTotal = week.reduce((a, t) => a + t.total, 0);
  const weekCorrect = week.reduce((a, t) => a + t.correct, 0);
  const weekAcc = weekTotal ? Math.round(100 * weekCorrect / weekTotal) : null;
  let html = `
  <section class="hero">
    <div class="hero-badge"><span class="dot"></span>${esc(goals.institution || "目标院校待设定")} · ${phase ? esc(phase.phase) + " · 距考试 " + phase.days_left + " 天" : "备考阶段未设(确认考试日期后自动划分)"}</div>
    <h1>${due ? "今天有 <span class='h1-accent'>" + due + " 项</span>到期待复测" : "今天适合推进薄弱专项"}</h1>
    <p class="hero-desc"><span id="hero-quote">${motivation.quote.text}</span>
      ${motivation.growth_note ? "<br><span style='color:#E5C88F'>🏆 " + esc(motivation.growth_note) + "</span>" : ""}</p>
    <div class="hero-actions">
      <a class="hero-cta" href="#study/train">🎯 每日训练(20 题)
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
      <a class="hero-ghost" href="#study/practice">间隔刷题(${due} 到期)</a>
      <a class="hero-ghost" href="#study/mistakes">📷 拍照录错题</a>
      <a class="hero-ghost" href="#coach">与教练反思</a>
    </div>
  </section>
  <div class="stats-band stagger">
    <div class="stat-cell"><div class="stat-num">${due}</div><div class="stat-label">今日到期(错题+生词)</div></div>
    <div class="stat-cell"><div class="stat-num">${doneToday}</div><div class="stat-label">今日已完成任务</div></div>
    <div class="stat-cell"><div class="stat-num">${streak}<span style="font-size:14px"> 天</span></div><div class="stat-label">连续学习天数${streak === 0 ? "(今天开始)" : ""}</div></div>
    <div class="stat-cell"><div class="stat-num">${Object.values(prof.subjects).reduce((a, s) => a + (s.minutes || 0), 0)}<span style="font-size:14px"> 分</span></div><div class="stat-label">累计有效学习时长</div></div>
  </div>
  ${targetUni ? `<div class="target-hero" style="margin:-20px 0 20px">
    <div class="th-img">${uniImg(targetUni, "fallback-svg")}</div>
    <div class="th-body">
      <h3 style="margin:0 0 6px;font-family:var(--font-serif)">${goals.institution ? "🎯 " + esc(targetUni.name) : "🏫 候选:" + esc(targetUni.name)}
        <span class="tag ${targetUni.completeness >= 60 ? "green" : "amber"}">资料完整度 ${targetUni.completeness}%</span></h3>
      <div class="muted" style="font-size:13px">${esc(targetUni.city || "")} · ${esc(targetUni.cs_school || "院系待补")}
        ${targetUni.uses_408 === true ? ' · <span class="tag green">408</span>' : ""}
        ${targetUni.last_verified ? ' · <span class="tag green">核验 ' + esc(targetUni.last_verified.slice(0, 10)) + "</span>" : ' · <span class="tag amber">招生数据待核实</span>'}</div>
      <div class="toolbar" style="margin:10px 0 0">
        <a class="btn" href="#intel/schools">院校资料库(${unis.length} 所) →</a>
        ${verified ? '<span class="muted">薄弱点 ' + verified + ' 个(下方有证据链)</span>' : ""}</div>
    </div></div>` : ""}
  <div class="card"><h2>四科状态(默认 11408 方案,可在个人中心调整)</h2>
    <div class="row2" style="grid-template-columns:repeat(4,1fr)">${["math", "cs408", "english", "politics"].map(sub => {
      const track = Object.values(catalog.tracks || {}).find(t => t.subject === sub);
      const p = track && track.progress ? track.progress : { pct: 0, started: 0, knowledge: 0 };
      const acc = (prof.subjects[sub] || {}).accuracy;
      const enabled = sub === "politics" ? (settings.subjects.politics || {}).enabled !== false && (settings.subjects.politics || {}).enabled : true;
      const polOff = sub === "politics" && !(settings.subjects.politics || {}).enabled;
      return `<div class="stat-cell" style="padding:14px 16px"><b>${SUBJECTS[sub]}</b>
        ${polOff ? '<span class="tag gray">未启用</span>' : ""}
        <div class="progress-track" style="margin:8px 0 4px"><div class="progress-fill" style="width:${p.pct}%"></div></div>
        <div class="muted">知识点进度 ${p.pct}%(${p.started}/${p.knowledge})· 正确率 ${acc == null ? "—" : acc + "%"}</div></div>`;
    }).join("")}</div></div>
  <div class="card donut-wrap"><svg class="donut" width="74" height="74" viewBox="0 0 74 74" role="img" aria-label="今日任务完成进度">
      <circle class="bg" cx="37" cy="37" r="30"></circle>
      <circle class="fg" cx="37" cy="37" r="30" stroke-dasharray="${(2 * Math.PI * 30).toFixed(1)}" stroke-dashoffset="${(2 * Math.PI * 30 * (1 - (plan.tasks.length ? doneToday / plan.tasks.length : 0))).toFixed(1)}"></circle>
    </svg>
    <div><div class="donut-label">${plan.tasks.length ? Math.round(100 * doneToday / plan.tasks.length) : 0}%</div>
    <div class="stat-label">今日任务完成进度(${doneToday}/${plan.tasks.length})</div></div></div>`;

  if (nextTask) {
    html += `<div class="card" style="border-left:3px solid var(--gold)">
      <h2>🎯 下一项最值得完成的任务</h2>
      <div style="font-size:15px"><b>${esc(nextTask.title)}</b> <span class="tag gray">≈${nextTask.est_minutes} 分钟</span></div>
      ${nextTask.reason ? '<div class="muted" style="margin-top:4px">💡 ' + esc(nextTask.reason) + "</div>" : ""}
      ${nextTask.standard ? '<div style="font-size:13px;color:var(--green);margin-top:4px">✔ 完成标准:' + esc(nextTask.standard) + "</div>" : ""}
      <div class="toolbar" style="margin:10px 0 0"><a class="btn primary" href="#study/practice">去做</a> <a class="btn" href="#plan">查看全部计划</a></div></div>`;
  }

  html += `<div class="row2">
    <div class="card"><h2>今日作战清单</h2>
      <div class="toolbar" style="margin-bottom:6px"><button class="primary" id="home-gen">生成 / 刷新</button>
      <span class="muted">已完成 ${doneToday} / ${(plan.tasks || []).length}</span></div>
      <div id="home-tasks">${renderTaskList(plan.tasks, true) || '<span class="muted">点击生成任务,或直接去刷题处理到期内容。</span>'}</div></div>
    <div class="card"><h2>最薄弱的地方</h2>`;
  html += topWeak.length ? topWeak.map(w => {
    const st = WP_STATUS[w.status] || WP_STATUS.unverified;
    return `<div class="wp-card"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
      <b>${esc(w.name)}</b><span class="tag ${st[1]}">${st[0]}</span></div>
      <div class="muted">${esc(w.judgment)}${w.trend ? " · " + esc(w.trend) : ""}</div>
      <div class="act">${esc(w.recommended_action || "")}</div></div>`;
  }).join("") : '<span class="muted">暂无判断 —— 录入错题并复测后,系统基于证据给出薄弱点,不凭空贴标签。</span>';
  html += `</div></div>
  <section class="radar-zone" id="home-radar"><div class="section-label">RADAR · 今日考研雷达</div>
    <div class="muted" style="margin:8px 0 14px">近期真实考研动态 + 基于你真实学习记录的行动建议。内容来自公开检索与官方公告,每条带来源与时间;<a href="#intel/hot">进入热点雷达 →</a></div>
    <div class="radar-grid" id="radar-cards"><div class="muted">雷达加载中…</div></div></section>
  <div class="row2">
  <div class="card"><h2>🕘 最近学习记录</h2><div id="home-recent">加载中…</div></div>
  <div class="card"><h2>📊 本周学习趋势</h2>${weekTrend(prof.trend_14d || [])}
    <p class="muted" style="margin-bottom:0">近 7 天做题 ${weekTotal} 题${weekTotal ? " · 正确率 " + weekAcc + "%" : " · 做第一组题后这里会有真实趋势"}</p></div></div>
  <div class="card"><h2>建议依据</h2><div style="font-size:13.5px">
    · 到期错题 ${session.due_mistakes.length} 条按遗忘曲线安排<br>
    ${(prof.error_patterns || []).slice(0, 2).map(p => "· 近期高频错误模式:「" + esc(p.reason) + "」×" + p.count + "<br>").join("")}
    ${(prof.data_gaps || []).slice(0, 2).map(g => "<span class='muted'>· " + esc(g) + "</span><br>").join("")}
    <a href='#profile'>完整画像 →</a> <a href='#growth'>成长时间线 →</a></div></div>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  renderHomeRadar();
  $("#home-gen").onclick = async () => {
    await api("/plan/generate", { method: "POST", body: { date: todayStr() } });
    toast("已生成"); ROUTES.home();
  };
  bindTaskButtons(ROUTES.home);
  // 最近学习记录(真实数据;空态引导)
  api("/growth/timeline").then(tl => {
    const el = $("#home-recent");
    if (!el) return;
    const evs = tl.slice(0, 3);
    el.innerHTML = evs.length
      ? evs.map(d => `<div class="task"><span class="title"><b>${esc(d.date)}</b> · ${esc(d.events[0] || "")}${d.events.length > 1 ? ' <span class="muted">等 ' + d.events.length + " 条</span>" : ""}</span></div>`).join("")
        + '<a class="btn" href="#growth" style="margin-top:8px">全部记录 →</a>'
      : '<div class="state" style="padding:18px"><span>还没有学习记录 —— 完成第一组刷题或写第一条反思后,这里会显示真实的最近动态。</span></div>';
  });
};

/* ================= 任务渲染(共享) ================= */
const KIND_NAME = { review: "复习", practice: "练习", study: "新知", weekly_review: "复盘", verify: "验证" };
function renderTaskList(tasks, withActions) {
  if (!tasks || !tasks.length) return "";
  return tasks.map(t => {
    const done = t.status === "done", skip = t.status === "skipped";
    return `<div class="task ${done ? "done" : ""}" data-task="${t.id}">
      <span class="tag ${SUBJECT_TAG[t.subject]}">${SUBJECTS[t.subject] || t.subject}</span>
      <span class="tag gray">${KIND_NAME[t.kind] || t.kind}</span>
      <span class="title">${esc(t.title)} <span class="muted">≈${t.est_minutes} 分钟${skip ? " · 已跳过" : ""}</span>
        ${t.reason ? '<span class="why">💡 ' + esc(t.reason) + "</span>" : ""}
        ${t.goal && withActions ? '<span class="std">🎯 ' + esc(t.goal) + (t.standard ? " | ✔ " + esc(t.standard) : "") + "</span>" : ""}</span>
      ${withActions ? `<span class="btns">
        <button data-act="done" ${done ? 'class="primary"' : ""}>完成</button>
        <button data-act="skip" ${skip ? 'class="primary"' : ""}>跳过</button>
        <button data-act="move">顺延</button></span>` : ""}</div>`;
  }).join("");
}
function bindTaskButtons(reload) {
  $$(".task button[data-act]").forEach(b => b.onclick = async e => {
    e.stopPropagation();
    const id = b.closest(".task").dataset.task;
    await api("/plan/task/" + id, { method: "POST", body: { action: b.dataset.act } });
    reload();
  });
}

/* ================= 学习中心(刷题/错题/生词/知识库) ================= */
let studyTab = "practice";
ROUTES.study = async (sub) => {
  if (sub) studyTab = sub;
  const names = { train: "🎯每日训练", practice: "间隔刷题", mistakes: "错题本", vocab: "生词", bank: "题库", knowledge: "知识库" };
  let html = `<div class="page-head"><div>
    <div class="section-label">STUDY CENTER</div><h1>学习中心</h1></div></div>
  <div class="tabs">${Object.entries(names).map(([k, n]) =>
    `<button data-t="${k}" ${studyTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="study-body"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  $$(".tabs button").forEach(b => b.onclick = () => { studyTab = b.dataset.t; ROUTES.study(studyTab); });
  const body = $("#study-body");
  if (studyTab === "train") await renderTrain(body);
  else if (studyTab === "practice") await renderPractice(body);
  else if (studyTab === "mistakes") await renderMistakes(body);
  else if (studyTab === "vocab") await renderVocab(body);
  else if (studyTab === "bank") await renderBank(body);
  else await renderKnowledge(body);
};

/* ---- 每日训练(学习中心第一 Tab) ---- */
async function renderTrain(host) {
  const t = await api("/train/daily");
  const items = t.items || [];
  const totalQ = Object.values(t.quotas).reduce((a, b) => a + b, 0);
  const shortMsg = Object.entries(t.shortage).map(([s, n]) =>
    SUBJECTS[s] + " 缺 " + n + " 题").join("、");
  let html = `<div class="toolbar">
    <b style="font-size:16px">${esc(t.date)} 每日训练</b>
    <span class="tag gray">配额 ${Object.entries(t.quotas).filter(([,v])=>v>0).map(([k,v])=>SUBJECTS[k]+" "+v).join(" / ")}</span>
    <span class="muted">已答 ${t.done}/${items.length}${t.done ? " · 对 " + t.correct : ""}</span>
    <button id="tr-regen" title="重新抽题(换一批)">↻ 换一批</button>
    <a class="btn" href="#account">设置题量</a></div>
  ${shortMsg ? '<div class="hintbox">⚠ 题库不足:' + esc(shortMsg) + ' —— 剩余科目将少于配额,系统不会用重复题凑数。可在「题库」页录入或导入更多题目。</div>' : ""}
  ${items.length === 0 ? '<div class="card state"><div class="big">🎯</div><b>今日训练清单为空</b><span>所有科目配额为 0 或题库为空。去「设置题量」或「题库」页补充。</span></div>' : '<div id="tr-list"></div>'}`;
  host.innerHTML = html;
  typeset(host);
  $("#tr-regen").onclick = async () => {
    // 换一批:清空当日清单重新生成(已答记录保留在 answers 中,不会丢)
    await api("/train/daily?force=1");
    toast("已重新抽题"); renderTrain(host);
  };
  const list = $("#tr-list");
  const state = { idx: items.findIndex(i => !i.answered), start: Date.now() };
  if (state.idx < 0) state.idx = items.length; // 全部已答
  function render() {
    if (state.idx >= items.length) return finishView();
    const q = items[state.idx];
    const isChoice = (q.options || []).length >= 2;
    let inner = `<div class="quiz-top"><b>每日训练</b>
      <div class="progress-track"><div class="progress-fill" style="width:${Math.round(state.idx / items.length * 100)}%"></div></div>
      <span class="muted">${state.idx + 1} / ${items.length}</span></div>
      <div class="card quiz-card"><div><span class="tag ${SUBJECT_TAG[q.subject]}">${SUBJECTS[q.subject]}</span>
      ${q.ai_generated ? '<span class="tag purple">AI 生成题</span>' : '<span class="tag gray">' + esc(q.source_type) + "</span>"}
      <span class="tag gray">难度 ${q.difficulty}/5</span></div>
      <div class="q-text">${md(q.question_md)}</div>`;
    if (isChoice) {
      inner += '<div class="options">' + q.options.map((o, i) =>
        `<div class="option" data-letter="${LETTERS[i]}"><span class="letter">${LETTERS[i]}</span><span>${md(o)}</span></div>`).join("") + "</div>";
    } else {
      inner += '<div class="toolbar" style="margin-top:14px"><button class="primary" id="tr-reveal">对答案(先自己写)</button></div>';
    }
    inner += '<div id="tr-after"></div></div>';
    list.innerHTML = inner;
    typeset(list);
    let picked = null, revealed = false;
    $$(".option").forEach(el => el.onclick = () => {
      if (revealed) return;
      picked = el.dataset.letter;
      $$(".option").forEach(x => x.classList.remove("selected"));
      el.classList.add("selected");
    });
    const rev = $("#tr-reveal");
    if (rev) rev.onclick = () => { revealed = true; submit(null, true); };
    if (isChoice) {
      list.querySelector(".quiz-card").insertAdjacentHTML("beforeend",
        '<div class="toolbar" style="margin-top:14px"><button class="primary" id="tr-submit" disabled>提交</button></div>');
      $$(".option").forEach(el => el.onclick = () => {
        if (revealed) return;
        picked = el.dataset.letter;
        $$(".option").forEach(x => x.classList.remove("selected"));
        el.classList.add("selected");
        $("#tr-submit").disabled = false;
      });
      $("#tr-submit").onclick = () => { if (picked) { revealed = true; submit(picked, false); } };
    }
    async function submit(pick, selfMode) {
      const seconds = Math.round((Date.now() - state.start) / 1000);
      state.start = Date.now();
      let correct;
      if (selfMode) {
        // 大题自评:先展示解析再自评
        $("#tr-after").innerHTML = `<div class="explain"><h4>参考解析</h4><div>${md(q.solution_md || "(无解析)")}</div></div>
          <div class="grade-row"><button data-c="1" class="good">做对了</button><button data-c="0" class="again">没做对</button></div>`;
        typeset($("#tr-after"));
        $$("#tr-after .grade-row button").forEach(b => b.onclick = () =>
          finalize(b.dataset.c === "1", pick, seconds, selfMode));
        return;
      }
      const r = await api("/train/answer", { method: "POST", body: {
        qid: q.id, picked: pick, seconds } });
      correct = r.correct;
      // 高亮
      $$(".option").forEach(el => {
        el.classList.add("disabled");
        if (el.dataset.letter === q.answer) el.classList.add("correct");
        else if (el.dataset.letter === pick) el.classList.add("wrong");
      });
      $("#tr-submit").parentElement.style.display = "none";
      if (correct) {
        $("#tr-after").innerHTML = `<div class="explain"><h4>✓ 回答正确</h4><div>${md(q.solution_md || "")}</div></div>
          <div class="toolbar" style="margin-top:12px"><button class="primary" id="tr-next">下一题 →</button></div>`;
      } else {
        $("#tr-after").innerHTML = `<div class="explain"><h4>✗ 正确答案:${esc(q.answer)}</h4><div>${md(q.solution_md || "")}</div></div>
          <p style="font-size:12.5px;margin:8px 0 4px;color:var(--text-2)">错因标记(会写入错题本,影响复习安排):</p>
          <div class="grade-row">
            <button data-tag="概念不清" class="again">概念不清</button>
            <button data-tag="计算失误" class="hard">计算失误</button>
            <button data-tag="粗心" class="hard">粗心</button>
            <button data-tag="不会做" class="again">不会做</button></div>`;
      }
      typeset($("#tr-after"));
      if (correct) {
        $("#tr-next").onclick = () => { state.idx++; render(); };
      } else {
        $$("#tr-after .grade-row button[data-tag]").forEach(b => b.onclick = async () => {
          await api("/train/answer", { method: "POST", body: {
            qid: q.id, picked: pick, seconds, error_tag: b.dataset.tag } });
          toast("已记入错题本:" + b.dataset.tag);
          state.idx++; render();
        });
      }
    }
    async function finalize(selfCorrect, pick, seconds) {
      await api("/train/answer", { method: "POST", body: {
        qid: q.id, picked: pick || "自评", seconds,
        self_correct: selfCorrect, error_tag: selfCorrect ? "" : "不会做" } });
      state.idx++; render();
    }
  }
  async function finishView() {
    await api("/train/finish", { method: "POST" }).catch(() => {});
    const t2 = await api("/train/daily");
    let html = `<div class="card quiz-card" style="text-align:center;padding:40px 26px">
      <div style="font-size:42px">🏁</div><h2>今日训练完成</h2>
      <p class="muted">共 ${t2.done} 题 · 正确 ${t2.correct}(${t2.done ? Math.round(100 * t2.correct / t2.done) : 0}%)· 成绩已计入统计,错题已进入错题本复习队列</p>
      <div class="toolbar" style="justify-content:center;margin-top:12px">
        <a class="btn primary" href="#growth">看成长记录</a>
        <a class="btn" href="#study/mistakes">复习错题本</a>
        <a class="btn" href="#home">回作战室</a></div></div>`;
    list.innerHTML = html;
    refreshDueBadge();
  }
  render();
}

/* ---- 刷题 ---- */
async function renderPractice(host) {
  const s = await api("/practice/session");
  const queue = [...s.due_mistakes.map(m => ({ kind: "mistake", item: m })),
                 ...s.due_vocab.map(v => ({ kind: "vocab", item: v }))];
  const state = { queue, idx: 0, detail: [], sessionStart: Date.now(),
    cardStart: 0, revealed: false, picked: null, submitted: false, hintUsed: false };

  function shell(inner) {
    const pct = state.queue.length ? Math.round(state.idx / state.queue.length * 100) : 0;
    return `<div class="quiz-wrap">
      <div class="quiz-top"><b style="font-size:16px">今日刷题</b>
        <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
        <span class="muted">${state.idx + 1} / ${state.queue.length}</span></div>
      ${inner}
      <div class="quiz-foot">本轮答对 ${state.detail.filter(d => d.correct).length} / ${state.detail.length} · 完成后自动记入统计与间隔复习</div></div>`;
  }
  function render() {
    if (state.idx >= state.queue.length) { finishView(); return; }
    state.cardStart = Date.now();
    state.revealed = state.picked = state.submitted = state.hintUsed = null;
    const cur = state.queue[state.idx];
    const item = cur.item;
    const isChoice = cur.kind === "mistake" && Array.isArray(item.options) && item.options.length >= 2;
    let inner = '<div class="card quiz-card">';
    inner += `<div>${cur.kind === "vocab"
      ? '<span class="tag amber">英语</span><span class="tag gray">' + (item.kind === "word" ? "单词" : "长难句") + "</span>"
        + (item.lapses ? '<span class="tag red">已忘 ' + item.lapses + " 次</span>" : "")
      : '<span class="tag ' + SUBJECT_TAG[item.subject] + '">' + SUBJECTS[item.subject] + "</span>" +
        (item.qtype ? '<span class="tag gray">' + esc(item.qtype) + "</span>" : "") +
        '<span class="tag gray">第 ' + ((item.lapses || 0) + 1) + " 轮</span>" +
        (item.error_reason ? '<span class="tag amber">上次原因:' + esc(item.error_reason) + "</span>" : "")}</div>`;
    if (item.image) inner += `<img class="q-img" src="/api/images/${esc(item.image)}" onclick="window.open('/api/images/${esc(item.image)}')">`;
    inner += cur.kind === "vocab"
      ? `<div class="q-text" style="font-size:20px;font-weight:700">${esc(item.text)}</div>`
        + (item.context_md ? `<p class="muted">原文:${esc(item.context_md)}</p>` : "")
      : `<div class="q-text">${md(item.question_md)}</div>`;
    if (isChoice) {
      inner += '<div class="options">' + item.options.map((opt, i) => {
        let cls = "option";
        if (state.submitted) {
          cls += " disabled";
          if (LETTERS[i] === item.answer) cls += " correct";
          else if (LETTERS[i] === state.picked) cls += " wrong";
        } else if (state.picked === LETTERS[i]) cls += " selected";
        return `<div class="${cls}" data-letter="${LETTERS[i]}"><span class="letter">${LETTERS[i]}</span><span>${md(opt)}</span></div>`;
      }).join("") + "</div>";
      inner += state.submitted ? "" :
        `<div class="toolbar" style="margin-top:14px"><button class="primary" id="q-submit" ${state.picked ? "" : "disabled"}>提交答案</button></div>`;
    } else {
      inner += state.revealed ? "" : '<div class="toolbar" style="margin-top:18px"><button class="primary" id="reveal">显示答案(先自己独立做)</button></div>';
    }
    const showExplain = cur.kind === "mistake" ? (state.submitted || (state.revealed && !isChoice)) : state.revealed;
    if (showExplain) {
      inner += `<div class="explain"><h4>${isChoice ? (state.picked === item.answer ? "✓ 回答正确" : "✗ 正确答案:" + esc(item.answer || "?")) : "解析"}</h4>
        <div>${md(cur.kind === "mistake" ? (item.solution_md || item.correct_answer_md) : item.meaning_md)}</div>
        ${cur.kind === "mistake" && item.my_answer_md ? '<div class="mine"><b style="font-size:12.5px">当时的做法</b><div>' + md(item.my_answer_md) + "</div></div>" : ""}
        <p class="q-source" style="margin-bottom:0">错误原因:${esc(item.error_reason || "—")} · 来源:${esc(item.source || "—")}</p></div>
      <label style="margin:10px 0 0;font-weight:400"><input type="checkbox" id="q-hint" ${state.hintUsed ? "checked" : ""}> 本题看了提示/解析才做出来(计入提示依赖)</label>
      <div class="grade-row">${GRADES.map(([g, label]) => `<button data-g="${g}" class="${g}">${label}</button>`).join("")}</div>`;
    }
    inner += "</div>";
    host.innerHTML = shell(inner);
    typeset(host);
    $$(".option").forEach(el => el.onclick = () => { if (state.submitted) return; state.picked = el.dataset.letter; render(); });
    const submit = $("#q-submit");
    if (submit) submit.onclick = () => { if (state.picked) { state.submitted = true; render(); } };
    const reveal = $("#reveal");
    if (reveal) reveal.onclick = () => { state.revealed = true; render(); };
    const hint = $("#q-hint");
    if (hint) hint.onchange = () => state.hintUsed = hint.checked;
    $$(".grade-row button[data-g]").forEach(b => b.onclick = () => grade(b.dataset.g));
  }
  async function grade(g) {
    const cur = state.queue[state.idx];
    const dur = Math.round((Date.now() - state.cardStart) / 1000);
    const correct = g !== "again" && (cur.kind !== "mistake" || !Array.isArray(cur.item.options)
      || state.picked === cur.item.answer);
    try {
      await api(`/${cur.kind === "vocab" ? "vocab" : "mistakes"}/${cur.item.id}/review`,
        { method: "POST", body: { result: g, duration_sec: dur, hint_used: !!state.hintUsed } });
    } catch (e) { toast("评分失败:" + e.message); }
    state.detail.push({ ref: cur.item.id, subject: cur.item.subject, kind: cur.kind,
      correct, knowledge_ids: cur.item.knowledge_ids || [], grade: g });
    state.idx++;
    render();
  }
  async function finishView() {
    const durMin = Math.max(1, Math.round((Date.now() - state.sessionStart) / 60000));
    const bySub = {};
    state.detail.forEach(d => {
      if (d.kind !== "mistake") return;
      bySub[d.subject] = bySub[d.subject] || { total: 0, correct: 0, kids: new Set(), items: [] };
      bySub[d.subject].total++;
      if (d.correct) bySub[d.subject].correct++;
      (d.knowledge_ids || []).forEach(i => bySub[d.subject].kids.add(i));
      bySub[d.subject].items.push({ ref: d.ref, correct: d.correct, knowledge_ids: d.knowledge_ids || [] });
    });
    let inner = '<div class="card quiz-card" style="text-align:center;padding:42px 30px">'
      + '<div style="font-size:42px">🎉</div><h2 style="margin:10px 0 4px">本轮完成</h2>'
      + `<p class="muted">用时约 ${durMin} 分钟 · 共 ${state.detail.length} 项 · 答对 ${state.detail.filter(d => d.correct).length} 项</p>`;
    const clientId = "sess-" + state.sessionStart;
    for (const [sub, v] of Object.entries(bySub)) {
      try {
        await api("/records", { method: "POST", body: {
          subject: sub, session_type: "mistake_review", total: v.total, correct: v.correct,
          duration_min: durMin, knowledge_ids: [...v.kids], detail: v.items,
          client_id: clientId + "-" + sub } });
        inner += `<p class="muted">已记录:${SUBJECTS[sub]} ${v.correct}/${v.total}</p>`;
      } catch (e) { toast("记录失败:" + e.message); }
    }
    inner += '<div class="toolbar" style="justify-content:center;margin-top:16px">'
      + '<a class="btn primary" style="padding:9px 22px" href="#coach">写 30 秒今日反思 →</a>'
      + '<a class="btn" style="padding:9px 22px" href="#growth">查看成长记录</a></div></div>';
    host.innerHTML = shell(inner);
    refreshDueBadge();
  }
  if (!queue.length) {
    host.innerHTML = `<div class="quiz-wrap"><div class="card quiz-card state">
      <div class="big">✅</div><b>今日到期内容已清空</b>
      <span>没有到期的错题和生词。去「错题」拍照录入,去「AI 教练」写反思,或在「计划」安排专项。</span>
      <div class="toolbar" style="justify-content:center;margin-top:8px">
        <a class="btn primary" style="padding:9px 22px" href="#study/mistakes">录错题</a>
        <a class="btn" style="padding:9px 22px" href="#coach">写反思</a></div></div></div>`;
    return;
  }
  render();
}

/* ---- 错题本 ---- */
let mkFilter = { subject: "", q: "", due: "" };
async function renderMistakes(host) {
  const params = new URLSearchParams();
  if (mkFilter.subject) params.set("subject", mkFilter.subject);
  if (mkFilter.q) params.set("q", mkFilter.q);
  if (mkFilter.due) params.set("due", mkFilter.due);
  const items = await api("/mistakes?" + params);
  let html = `<div class="toolbar">
    <button class="primary" id="mk-add">📷 拍照 / 录入错题</button>
    <select id="mk-subject"><option value="">全部科目</option>
      ${Object.entries(SUBJECTS).slice(0, 3).map(([v, n]) => `<option value="${v}" ${mkFilter.subject === v ? "selected" : ""}>${n}</option>`).join("")}</select>
    <select id="mk-due"><option value="">全部</option>
      <option value="1" ${mkFilter.due === "1" ? "selected" : ""}>仅到期</option>
      <option value="0" ${mkFilter.due === "0" ? "selected" : ""}>未到期</option></select>
    <input id="mk-q" placeholder="搜索题面 / 原因 / 解析" value="${esc(mkFilter.q)}" style="width:200px"></div><div id="mk-list">`;
  if (!items.length) html += '<div class="card state"><div class="big">📷</div><b>还没有错题</b><span>纸质错题直接拍照录入,系统保存原图 —— 手写推导和批注同样是复习材料。</span></div>';
  for (const m of items) {
    const due = !m.next_review || new Date(m.next_review) <= new Date();
    html += `<div class="item" data-id="${m.id}">
      <div class="head">${m.image ? `<img class="thumb" src="/api/images/${esc(m.image)}" loading="lazy">` : ""}
      <div style="flex:1;min-width:0"><b>${esc((m.question_md || "(仅图片)").split("\n")[0].slice(0, 60))}</b>
      ${m.seed ? '<span class="tag gray" title="系统自带示例,可在详情删除">示例</span>' : ""}
      ${m.needs_confirmation ? '<span class="tag orange">需确认</span>' : ""}
      <div class="sub">原因:${esc(m.error_reason || "—")} · 已忘 ${m.lapses || 0} 次 · ${due ? "<span style='color:var(--red)'>已到期</span>" : m.next_review}</div></div>
      <span><span class="tag ${SUBJECT_TAG[m.subject]}">${SUBJECTS[m.subject]}</span>
      ${m.qtype ? '<span class="tag gray">' + esc(m.qtype) + "</span>" : ""}</span></div></div>`;
  }
  html += "</div>";
  host.innerHTML = html;
  typeset(host);
  $("#mk-add").onclick = () => mkForm();
  $("#mk-subject").onchange = e => { mkFilter.subject = e.target.value; renderMistakes(host); };
  $("#mk-due").onchange = e => { mkFilter.due = e.target.value; renderMistakes(host); };
  $("#mk-q").onchange = e => { mkFilter.q = e.target.value.trim(); renderMistakes(host); };
  $$("#mk-list .item").forEach(el => el.onclick = () => showMk(el.dataset.id, host));
}

async function showMk(id, host) {
  const m = await api("/mistakes/" + id);
  const isChoice = Array.isArray(m.options) && m.options.length >= 2;
  openModal(`<h2>错题详情</h2>
    <div style="margin-bottom:8px"><span class="tag ${SUBJECT_TAG[m.subject]}">${SUBJECTS[m.subject]}</span>
    ${m.qtype ? '<span class="tag gray">' + esc(m.qtype) + "</span>" : ""}
    ${m.needs_confirmation ? '<span class="tag orange">AI 结果需确认</span>' : ""}
    ${m.confidence != null ? '<span class="tag gray">置信度 ' + Math.round(m.confidence * 100) + "%</span>" : ""}</div>
    ${m.image ? `<img class="q-img" src="/api/images/${esc(m.image)}" onclick="window.open('/api/images/${esc(m.image)}')">` : ""}
    <div class="q-text">${md(m.question_md)}</div>
    ${isChoice ? '<div class="options">' + m.options.map((o, i) =>
      `<div class="option disabled ${LETTERS[i] === m.answer ? "correct" : ""}"><span class="letter">${LETTERS[i]}</span><span>${md(o)}</span></div>`).join("") + "</div>" : ""}
    <div class="explain" style="display:none" id="mk-explain">
      <h4>解析</h4><div>${md(m.solution_md || m.correct_answer_md)}</div>
      ${m.my_answer_md ? '<div class="mine"><b style="font-size:12.5px">当时的做法</b><div>' + md(m.my_answer_md) + "</div></div>" : ""}
      <p class="q-source" style="margin-bottom:0">错误原因:${esc(m.error_reason || "—")} · 来源:${esc(m.source || "—")} · 已忘 ${m.lapses || 0} 次 · 下次:${esc(m.next_review || "待定")}</p>
      ${(m.reviews || []).length ? '<p class="q-source" style="margin-bottom:0">复测历史:' + m.reviews.map(r =>
        r.date + " " + ({ again: "✗忘了", hard: "△勉强", good: "✓会了", easy: "✓轻松" }[r.result] || r.result)
        + (r.hint_used ? "(看提示)" : "")).join(" → ") + "</p>" : ""}
    </div>
    <div class="toolbar" style="margin-top:14px"><button class="primary" id="mk-reveal">显示解析</button></div>
    <div class="grade-row" style="display:none" id="mk-grades">${GRADES.map(([g, label]) => `<button data-g="${g}" class="${g}">${label}</button>`).join("")}</div>
    <div class="toolbar" style="margin-top:12px;display:none" id="mk-after">
      <button id="mk-edit">编辑 / 校对</button><button id="mk-archive">归档</button><button id="mk-del" class="again">删除</button>
      <a class="btn" style="margin-left:auto" href="#" onclick="closeModal();return false">关闭</a></div>`);
  const reveal = () => {
    $("#mk-explain").style.display = "block";
    $("#mk-grades").style.display = "flex";
    $("#mk-after").style.display = "flex";
    $("#mk-reveal").parentElement.style.display = "none";
    $$("#mk-grades button[data-g]").forEach(b => b.onclick = async () => {
      await api("/mistakes/" + id + "/review", { method: "POST", body: { result: b.dataset.g } });
      toast("已评分,下次复习时间已更新"); closeModal();
      if (host) renderMistakes(host); else ROUTES.study("mistakes");
    });
  };
  $("#mk-reveal").onclick = reveal;
  $("#mk-edit").onclick = () => mkForm(m, host);
  $("#mk-archive").onclick = async () => {
    await api("/mistakes/" + id, { method: "PUT", body: { archived: true } });
    toast("已归档"); closeModal(); if (host) renderMistakes(host); else ROUTES.study("mistakes");
  };
  $("#mk-del").onclick = async () => {
    if (!confirm("彻底删除该错题?")) return;
    await api("/mistakes/" + id, { method: "DELETE" });
    toast("已删除"); closeModal(); if (host) renderMistakes(host); else ROUTES.study("mistakes");
  };
}

async function mkForm(existing, host) {
  const m = existing || { subject: "math", qtype: "", question_md: "", my_answer_md: "",
    correct_answer_md: "", solution_md: "", error_reason: "", source: "", difficulty: 3,
    knowledge_ids: [], options: [], answer: "", image: "", needs_confirmation: false };
  const kps = await api("/knowledge?subject=" + m.subject);
  const opts = m.options && m.options.length ? m.options : ["", "", "", ""];
  openModal(`<h2>${existing ? "编辑 / 校对" : "拍照录入"}错题</h2>
    <div class="form-grid">
      <div class="full">
        <label>题目图片(拍照 / 截图;保存原图,手写推导一并保留)</label>
        <div id="up-zone" class="upload-zone"><span class="big">📷</span>
          点击拍照或选择图片<span class="muted" style="display:block">(支持连续用同一张图建多道题)</span></div>
        <input type="file" id="up-file" accept="image/*" capture="environment" style="display:none">
        <div id="up-preview"></div></div>
      <div class="full"><div id="ai-box"></div></div>
      <div><label>科目</label><select id="m-subject">
        ${Object.entries(SUBJECTS).slice(0, 3).map(([v, n]) => `<option value="${v}" ${m.subject === v ? "selected" : ""}>${n}</option>`).join("")}</select></div>
      <div><label>题型</label><select id="m-qtype"><option value="">(不选)</option>
        ${(QTYPES[m.subject] || []).map(t => `<option ${m.qtype === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="full"><label>题面文字(支持 LaTeX;AI 识别后请务必校对)</label><textarea id="m-q">${esc(m.question_md)}</textarea></div>
      <div class="full"><label>选项(选择题填 2-4 项,大题可留空)</label>
        ${opts.map((o, i) => `<div style="display:flex;gap:8px;margin-bottom:6px"><span style="width:26px;height:26px;flex-shrink:0;border-radius:8px;background:var(--bg-inset);display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:12px">${LETTERS[i]}</span>
        <input class="m-opt" data-i="${i}" value="${esc(o)}" style="flex:1"></div>`).join("")}</div>
      <div><label>正确答案(选择题填字母)</label><input id="m-ans" value="${esc(m.answer || "")}" style="width:100%"></div>
      <div><label>难度(1-5)</label><input id="m-diff" type="number" min="1" max="5" value="${m.difficulty}" style="width:100%"></div>
      <div class="full"><label>我当时的做法 / 原始解题过程</label><textarea id="m-my">${esc(m.my_answer_md)}</textarea></div>
      <div class="full"><label>正确思路 / 解法(逐步,可核验)</label><textarea id="m-sol" style="min-height:100px">${esc(m.solution_md)}</textarea></div>
      <div><label>错误原因</label><select id="m-reason">${["(不选)", ...ERROR_REASONS].map(t =>
        `<option ${(m.error_reason || "(不选)") === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div><label>来源(教材 / 练习册 / 试卷)</label><input id="m-source" value="${esc(m.source)}" style="width:100%"></div>
      <div class="full"><label>关联知识点</label><select id="m-kps" multiple size="4" style="width:100%">
        ${kps.map(k => `<option value="${k.id}" ${(m.knowledge_ids || []).includes(k.id) ? "selected" : ""}>${esc(k.name)}</option>`).join("")}</select></div>
    </div>
    <p><button class="primary" id="m-save">保存</button> <button id="m-cancel">取消</button>
    <span class="muted" id="m-imgstate"></span></p>`);

  let curImage = m.image || "";
  const refreshImgState = () => {
    $("#m-imgstate").textContent = curImage ? "(将关联图片 " + curImage + ")" : "";
    if (curImage) {
      $("#up-preview").innerHTML = `<div class="img-preview-wrap"><img id="up-img" src="/api/images/${esc(curImage)}"></div>
        <div class="img-tools"><button type="button" id="up-rot">旋转 90°</button>
        <button type="button" id="up-ai" class="primary">🤖 AI 识别此图</button>
        <input id="ai-hint" placeholder="给 AI 的补充说明(可选)" style="flex:1;min-width:160px"></div>`;
      $("#up-rot").onclick = () => rotateAndUpload();
      $("#up-ai").onclick = () => runAI();
    } else $("#up-preview").innerHTML = "";
  };
  async function uploadBlob(blob, name) {
    const fd = new FormData();
    fd.append("file", blob, name || "photo.jpg");
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "上传失败");
    curImage = data.file; refreshImgState();
    if (data.warning) toast(data.warning);
  }
  function rotateAndUpload() {
    const img = $("#up-img");
    if (!img) return;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = img.naturalHeight; canvas.height = img.naturalWidth;
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate(Math.PI / 2);
    ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
    canvas.toBlob(b => uploadBlob(b, "rotated.jpg"), "image/jpeg", 0.92);
  }
  $("#up-zone").onclick = () => $("#up-file").click();
  $("#up-file").onchange = async () => {
    const f = $("#up-file").files[0];
    if (!f) return;
    try { await uploadBlob(f, f.name); } catch (e) { toast(e.message); }
    $("#up-file").value = "";
  };
  refreshImgState();
  async function runAI() {
    if (!curImage) return toast("请先上传图片");
    $("#ai-box").innerHTML = '<div class="infobox">🤖 正在识别(本地视觉模型,首次加载约 10-30 秒)…</div>';
    try {
      const r = await api("/ai/recognize", { method: "POST",
        body: { file: curImage, hint: ($("#ai-hint") || {}).value || "" } });
      renderAI(r);
    } catch (e) { $("#ai-box").innerHTML = '<div class="hintbox">识别失败:' + esc(e.message) + "</div>"; }
  }
  function renderAI(r) {
    if (!r.ai_available) {
      $("#ai-box").innerHTML = '<div class="hintbox"><b>AI 未就绪:</b>' + esc(r.error || "") + "</div>";
      return;
    }
    if (!r.ok) { $("#ai-box").innerHTML = '<div class="hintbox"><b>识别失败:</b>' + esc(r.error || "") + " 可重试或手填。</div>"; return; }
    const d = r.data;
    if (d.question_text) $("#m-q").value = d.question_text;
    if (d.subject && SUBJECTS[d.subject]) $("#m-subject").value = d.subject;
    if (d.qtype) { const sel = $("#m-qtype"); if ([...sel.options].some(o => o.value === d.qtype)) sel.value = d.qtype; }
    if (d.difficulty) $("#m-diff").value = d.difficulty;
    if (d.error_reason) { const sel = $("#m-reason"); if ([...sel.options].some(o => o.value === d.error_reason)) sel.value = d.error_reason; }
    if (d.solution_draft && d.solution_draft !== "看不清,需补充" && !$("#m-sol").value) $("#m-sol").value = d.solution_draft;
    if (d.user_work_seen && !$("#m-my").value) $("#m-my").value = d.user_work_seen;
    const names = d.knowledge_names || [];
    if (names.length) [...$("#m-kps").options].forEach(o => {
      if (names.some(n => o.textContent.includes(n) || n.includes(o.textContent))) o.selected = true;
    });
    $("#ai-box").innerHTML = `<div class="${d.confidence < 0.6 ? "hintbox" : "infobox"}">
      <b>🤖 AI 识别完成</b> <span class="tag ${d.confidence < 0.6 ? "orange" : "green"}">置信度 ${Math.round(d.confidence * 100)}%</span>
      <span class="tag orange">需人工校对</span>
      ${d.notes ? '<div style="margin-top:4px">⚠ ' + esc(d.notes) + "</div>" : ""}
      ${names.length ? '<div>识别知识点:' + names.map(esc).join("、") + "(已尝试关联)</div>" : ""}
      <div class="muted">已填入表单,请逐项核对 —— 公式和手写内容可能识别错误。</div></div>`;
    typeset($("#ai-box"));
  }
  $("#m-cancel").onclick = closeModal;
  $("#m-save").onclick = async () => {
    const body = {
      subject: $("#m-subject").value, qtype: $("#m-qtype").value,
      question_md: $("#m-q").value, my_answer_md: $("#m-my").value,
      solution_md: $("#m-sol").value, error_reason: $("#m-reason").value === "(不选)" ? "" : $("#m-reason").value,
      source: $("#m-source").value, difficulty: +$("#m-diff").value || 3,
      knowledge_ids: [...$("#m-kps").selectedOptions].map(o => o.value),
      options: $$(".m-opt").map(i => i.value.trim()).filter(Boolean),
      answer: ($("#m-ans").value || "").trim().toUpperCase(),
      image: curImage, needs_confirmation: false,
    };
    if (!body.question_md.trim() && !body.image) return toast("题面和图片至少要有一样");
    if (body.options.length >= 2 && !/^[A-F]$/.test(body.answer)) return toast("选择题答案请填字母 A-F");
    try {
      if (existing) await api("/mistakes/" + existing.id, { method: "PUT", body });
      else await api("/mistakes", { method: "POST", body });
      if (!existing && curImage) {
        openModal(`<h2>已保存 ✓</h2><p>这张图片还可以继续建题(一张图多道题很常见)。</p>
          <p><button class="primary" id="again-same">用这张图继续建下一题</button>
          <button onclick="closeModal()">完成</button></p>`);
        $("#again-same").onclick = () => mkForm({ ...m, image: curImage, question_md: "",
          my_answer_md: "", solution_md: "", knowledge_ids: [], options: [], answer: "" }, host);
        return;
      }
      closeModal(); toast("已保存,进入间隔复习循环");
      if (host) renderMistakes(host); else ROUTES.study("mistakes");
    } catch (e) { toast(e.message); }
  };
}

/* ---- 生词 ---- */
async function renderVocab(host) {
  const items = await api("/vocab");
  let html = `<div class="toolbar"><button class="primary" id="vb-add">+ 添加</button></div><div class="card">`;
  if (!items.length) html += '<div class="state"><div class="big">🔤</div><b>暂无条目</b><span>阅读中遇到生词/长难句就记一条,系统按间隔复习安排。</span></div>';
  for (const v of items) {
    const due = !v.next_review || new Date(v.next_review) <= new Date();
    html += `<div class="item" data-id="${v.id}"><div class="head">
      <b>${esc(v.text)}</b><span><span class="tag gray">${v.kind === "word" ? "单词" : "长难句"}</span>
      <span class="tag ${due ? "red" : "green"}">${due ? "已到期" : v.next_review}</span></span></div>
      <div class="sub">${esc((v.meaning_md || "").slice(0, 80))}</div></div>`;
  }
  html += "</div>";
  host.innerHTML = html;
  typeset(host);
  $("#vb-add").onclick = vbForm;
  $$(".item", host).forEach(el => el.onclick = () => vbReview(el.dataset.id, host));
}
function vbForm() {
  openModal(`<h2>添加生词 / 长难句</h2>
    <div class="form-grid">
      <div><label>类型</label><select id="v-kind"><option value="word">单词</option><option value="sentence">长难句</option></select></div>
      <div><label>出处</label><input id="v-source" style="width:100%"></div>
      <div class="full"><label>词 / 句</label><input id="v-text" style="width:100%"></div>
      <div class="full"><label>原文语境</label><textarea id="v-ctx"></textarea></div>
      <div class="full"><label>释义 / 句子分析(以词典或解析为准)</label><textarea id="v-mean"></textarea></div>
    </div>
    <p><button class="primary" id="v-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
  $("#v-save").onclick = async () => {
    if (!$("#v-text").value.trim()) return toast("必填词/句");
    await api("/vocab", { method: "POST", body: {
      kind: $("#v-kind").value, text: $("#v-text").value,
      context_md: $("#v-ctx").value, meaning_md: $("#v-mean").value,
      source: $("#v-source").value } });
    closeModal(); toast("已添加"); ROUTES.study("vocab");
  };
}
function vbReview(id, host) {
  api("/vocab").then(items => {
    const v = items.find(x => x.id === id);
    if (!v) return;
    openModal(`<h2>${esc(v.text)}</h2>
      ${v.context_md ? '<p class="muted">原文:' + esc(v.context_md) + "</p>" : ""}
      <div>${md(v.meaning_md)}</div>
      <p class="muted">出处:${esc(v.source || "—")} · 已忘 ${v.lapses || 0} 次 · 下次:${esc(v.next_review || "待定")}</p>
      <div class="grade-row">${GRADES.map(([g, label]) => `<button data-g="${g}" class="${g}">${label}</button>`).join("")}</div>
      <div class="toolbar" style="margin-top:12px"><button id="v-del" class="again">删除</button>
      <a class="btn" style="margin-left:auto" href="#" onclick="closeModal();return false">关闭</a></div>`);
    $$("#modal .grade-row button[data-g]").forEach(b => b.onclick = async () => {
      await api("/vocab/" + id + "/review", { method: "POST", body: { result: b.dataset.g } });
      toast("已评分"); closeModal(); if (host) renderVocab(host); else ROUTES.study("vocab");
    });
    $("#v-del").onclick = async () => { await api("/vocab/" + id, { method: "DELETE" }); closeModal(); if (host) renderVocab(host); else ROUTES.study("vocab"); };
  });
}

/* ---- 知识库 ---- */
let kpFilter = { subject: "", q: "", chapter: "" };
/* ---- 题库 Tab(插入 renderKnowledge 之前) ---- */
async function renderBank(host) {
  const page0 = host.dataset.qpage || 1;
  const qp = new URLSearchParams();
  if (host.dataset.subject) qp.set("subject", host.dataset.subject);
  qp.set("page", page0); qp.set("per", 50);
  const [pager, stats] = await Promise.all([
    api("/questions?" + qp), api("/data-quality")]);
  const items = pager.items;
  const byType = {};
  for (const q of items) byType[q.source_type] = (byType[q.source_type] || 0) + 1;
  let html = `<div class="toolbar">
    <button class="primary" id="qb-add">+ 录入题目</button>
    <button id="qb-import">批量导入(JSON)</button>
    <button id="qb-practice" ${items.length ? "" : "disabled"}>🎯 抽题练习</button>
    <select id="qb-subject"><option value="">全部科目</option>
      ${Object.entries(SUBJECTS).slice(0, 4).map(([v, n]) => `<option value="${v}">${n}</option>`).join("")}</select>
    <span class="muted">共 ${items.length} 题 · ${Object.entries(byType).map(([t, n]) => esc(t) + " " + n).join(" / ") || "空"}</span></div>
  <div class="infobox">版权规则:真题必须声明授权依据或标「来源不明-待核验」;AI 生成题自动标注 <span class="tag purple">AI 生成</span>,永不冒充真题;题干哈希去重。</div>`;
  if (!items.length) html += '<div class="card state"><div class="big">📋</div><b>题库为空</b><span>手动录入或导入 JSON;也可以在 AI 教练页让教练生成变式题(自动标注 AI 生成)。</span></div>';
  html += '<div id="qb-list">';
  for (const q of items.slice(0, 100)) {
    html += `<div class="item" data-id="${q.id}">
      <div class="head"><div style="min-width:0"><b>${esc(q.question_md.split("\n")[0].slice(0, 64))}</b>
        <div class="sub">${SUBJECTS[q.subject]}${q.year ? " · " + q.year + " 年" : ""} · ${esc(q.qtype || "未分类")} · 难度 ${q.difficulty}/5
        · ${esc(q.source_desc || q.source_type)}</div></div>
        <span><span class="tag ${q.source_type.includes("AI") ? "purple" : q.source_type === "真题" ? "amber" : "gray"}">${esc(q.source_type)}</span>
        ${q.ai_generated ? '<span class="tag purple">AI 生成</span>' : ""}
        ${q.copyright_status === "来源不明-待核验" ? '<span class="tag red">待核验</span>' : ""}</span></div></div>`;
  }
  html += "</div>";
  // 分页条
  if (pager.pages > 1) {
    html += `<div class="toolbar" style="justify-content:center;margin-top:12px">
      <button id="qb-prev" ${pager.page > 1 ? "" : "disabled"}>← 上一页</button>
      <span class="muted">第 ${pager.page} / ${pager.pages} 页 · 共 ${pager.total} 题</span>
      <button id="qb-next" ${pager.page < pager.pages ? "" : "disabled"}>下一页 →</button></div>`;
  }
  host.innerHTML = html;
  typeset(host);
  const pnav = d => () => { host.dataset.qpage = (pager.page + d); renderBank(host); };
  if ($("#qb-prev")) { $("#qb-prev").onclick = pnav(-1); $("#qb-next").onclick = pnav(1); }
  $("#qb-subject").onchange = e => { host.dataset.subject = e.target.value; host.dataset.qpage = 1; renderBank(host); };
  $$("#qb-list .item").forEach(el => el.onclick = () => showQb(el.dataset.id, host));
  $("#qb-add").onclick = () => qbForm(host);
  $("#qb-import").onclick = () => qbImport(host);
  $("#qb-practice").onclick = () => bankPractice(host);
}

async function showQb(id, host) {
  const q = (await api("/questions")).find(x => x.id === id);
  if (!q) return;
  const isChoice = (q.options || []).length >= 2;
  openModal(`<h2>题目详情</h2>
    <div style="margin-bottom:8px"><span class="tag ${SUBJECT_TAG[q.subject]}">${SUBJECTS[q.subject]}</span>
    ${q.year ? '<span class="tag gray">' + q.year + " 年</span>" : ""}
    <span class="tag ${q.source_type.includes("AI") ? "purple" : "gray"}">${esc(q.source_type)}</span>
    ${q.ai_generated ? '<span class="tag purple">AI 生成练习题</span>' : ""}
    <span class="tag ${q.copyright_status === "来源不明-待核验" ? "red" : "green"}">${esc(q.copyright_status)}</span></div>
    <div class="q-text">${md(q.question_md)}</div>
    ${isChoice ? '<div class="options">' + q.options.map((o, i) =>
      `<div class="option disabled ${LETTERS[i] === q.answer ? "correct" : ""}"><span class="letter">${LETTERS[i]}</span><span>${md(o)}</span></div>`).join("") + "</div>"
      : `<p><b>答案:</b>${esc(q.answer || "(见解析)")}</p>`}
    ${q.solution_md ? '<div class="explain"><h4>解析</h4><div>' + md(q.solution_md) + "</div></div>" : '<p class="muted">暂无解析</p>'}
    <p class="muted">来源:${esc(q.source_desc || "—")} · 录入 ${esc((q.created || "").slice(0, 10))}</p>
    <div class="toolbar" style="margin-top:10px"><button class="again" id="qb-del">删除</button>
    <a class="btn" style="margin-left:auto" href="#" onclick="closeModal();return false">关闭</a></div>`);
  $("#qb-del").onclick = async () => {
    if (!confirm("删除该题?")) return;
    await api("/questions/" + q.id, { method: "DELETE" });
    closeModal(); renderBank(host);
  };
}

function qbForm(host) {
  openModal(`<h2>录入题目</h2>
    <p class="muted">真题请写明来源与年份;版权状态二选一:已获授权 / 来源不明-待核验。</p>
    <div class="form-grid">
      <div><label>科目</label><select id="q-subject">
        ${Object.entries(SUBJECTS).slice(0, 4).map(([v, n]) => `<option value="${v}">${n}</option>`).join("")}</select></div>
      <div><label>类型</label><select id="q-type">${["真题", "模拟题", "教材例题", "AI 生成练习题", "自录题"]
        .map(t => `<option>${t}</option>`).join("")}</select></div>
      <div><label>年份(真题/模拟填)</label><input id="q-year" type="number" placeholder="如 2024" style="width:100%"></div>
      <div><label>题型(概念/计算/…)</label><input id="q-qtype" style="width:100%"></div>
      <div class="full"><label>题干(支持 LaTeX)</label><textarea id="q-text"></textarea></div>
      <div class="full"><label>选项(每行一项,2-4 项;大题留空)</label><textarea id="q-opts" placeholder="选项A&#10;选项B&#10;选项C&#10;选项D"></textarea></div>
      <div><label>答案(选择题字母)</label><input id="q-ans" style="width:100%"></div>
      <div><label>难度 1-5</label><input id="q-diff" type="number" min="1" max="5" value="3" style="width:100%"></div>
      <div class="full"><label>解析</label><textarea id="q-sol"></textarea></div>
      <div class="full"><label>来源描述(书名页码/网址/AI 模型名)</label><input id="q-src" style="width:100%"></div>
      <div class="full"><label>版权状态</label><select id="q-copy" style="width:100%">
        <option>合法使用(授权/开放许可)</option>
        <option>来源不明-待核验</option>
        <option>AI 原创</option>
        <option>自述/本人记录</option></select></div>
    </div>
    <p><button class="primary" id="q-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
  $("#q-save").onclick = async () => {
    const opts = $("#q-opts").value.split("\n").map(s => s.trim()).filter(Boolean);
    const body = {
      subject: $("#q-subject").value, source_type: $("#q-type").value,
      year: $("#q-year").value || null, qtype: $("#q-qtype").value,
      question_md: $("#q-text").value, options: opts,
      answer: $("#q-ans").value, solution_md: $("#q-sol").value,
      source_desc: $("#q-src").value, copyright_status: $("#q-copy").value,
      difficulty: +$("#q-diff").value || 3,
    };
    try {
      await api("/questions", { method: "POST", body });
      closeModal(); toast("已录入"); renderBank(host);
    } catch (e) { toast(e.message); }
  };
}

function qbImport(host) {
  openModal(`<h2>批量导入(JSON)</h2>
    <p class="muted">格式:[{subject, source_type, year, question_md, options[], answer, solution_md, source_desc, copyright_status}]。
    逐条校验+哈希去重,无效条目跳过并报告。上限 500 题/次。</p>
    <textarea id="qi-json" style="min-height:180px" placeholder='[{"subject":"cs408","source_type":"自录题","question_md":"TCP 三次握手第几步最容易考?","options":["第一步","第二步","第三步"],"answer":"C","solution_md":"…","source_desc":"王道计网 第5章"}]'></textarea>
    <p><button class="primary" id="qi-go">导入</button> <button onclick="closeModal()">取消</button></p>
    <div id="qi-result"></div>`);
  $("#qi-go").onclick = async () => {
    let items;
    try { items = JSON.parse($("#qi-json").value); }
    catch (e) { return toast("JSON 解析失败:" + e.message); }
    try {
      const r = await api("/questions/import", { method: "POST", body: { items } });
      $("#qi-result").innerHTML = `<div class="infobox">新增 <b>${r.added}</b> · 重复 ${r.duplicates.length} · 无效 ${r.invalid.length}
        ${r.ai_generated_count ? " · 其中 AI 生成 " + r.ai_generated_count + " 题" : ""}</div>`
        + (r.invalid.length ? '<div class="hintbox">无效明细:' + r.invalid.map(i =>
            "#" + i.index + " " + esc(i.error)).join("<br>") + "</div>" : "");
      toast("导入完成:新增 " + r.added);
      setTimeout(() => renderBank(host), 800);
    } catch (e) { toast(e.message); }
  };
}

/* 题库抽题练习:复用刷题交互,写入练习记录 */
async function bankPractice(host) {
  const pool = await api("/questions/practice?n=5" + (host.dataset.subject ? "&subject=" + host.dataset.subject : ""));
  if (!pool.length) return toast("题库为空");
  const state = { idx: 0, detail: [], start: Date.now(), picked: null, submitted: false };
  function render() {
    if (state.idx >= pool.length) return finish();
    const q = pool[state.idx];
    const isChoice = (q.options || []).length >= 2;
    let inner = `<div class="quiz-top"><b>题库练习</b><span class="muted">${state.idx + 1} / ${pool.length}</span></div>
      <div class="card quiz-card"><div><span class="tag ${SUBJECT_TAG[q.subject]}">${SUBJECTS[q.subject]}</span>
      ${q.year ? '<span class="tag gray">' + q.year + " 年</span>" : ""}
      <span class="tag ${q.ai_generated ? "purple" : "gray"}">${esc(q.source_type)}</span>
      ${q.ai_generated ? '<span class="tag purple">AI 生成</span>' : ""}</div>
      <div class="q-text">${md(q.question_md)}</div>`;
    if (isChoice) {
      inner += '<div class="options">' + q.options.map((o, i) => {
        let cls = "option";
        if (state.submitted) {
          cls += " disabled";
          if (LETTERS[i] === q.answer) cls += " correct";
          else if (LETTERS[i] === state.picked) cls += " wrong";
        } else if (state.picked === LETTERS[i]) cls += " selected";
        return `<div class="${cls}" data-letter="${LETTERS[i]}"><span class="letter">${LETTERS[i]}</span><span>${md(o)}</span></div>`;
      }).join("") + "</div>";
    } else {
      inner += '<div class="toolbar" style="margin-top:14px"><button class="primary" id="bp-reveal">对答案(先自己写)</button></div>';
    }
    if (state.submitted || state.revealed) {
      const correct = isChoice ? state.picked === q.answer : null;
      inner += `<div class="explain"><h4>${correct === null ? "参考解析" : correct ? "✓ 回答正确" : "✗ 正确答案:" + esc(q.answer)}</h4>
        <div>${md(q.solution_md || "(暂无解析)")}</div></div>
        <div class="grade-row">${GRADES.map(([g, lb]) => `<button data-g="${g}" class="${g}">${lb}</button>`).join("")}</div>`;
    } else if (isChoice) {
      inner += '<div class="toolbar" style="margin-top:14px"><button class="primary" id="bp-submit" ' + (state.picked ? "" : "disabled") + '>提交</button></div>';
    }
    inner += "</div>";
    host.innerHTML = inner;
    typeset(host);
    $$(".option").forEach(el => el.onclick = () => { if (!state.submitted) { state.picked = el.dataset.letter; render(); } });
    const sub = $("#bp-submit");
    if (sub) sub.onclick = () => { state.submitted = true; render(); };
    const rev = $("#bp-reveal");
    if (rev) rev.onclick = () => { state.revealed = true; render(); };
    $$(".grade-row button[data-g]").forEach(b => b.onclick = async () => {
      const q2 = pool[state.idx];
      const correct = isChoice ? state.picked === q2.answer : b.dataset.g !== "again";
      state.detail.push({ ref: q2.id, subject: q2.subject, correct,
        knowledge_ids: q2.knowledge_ids || [] });
      // 每题即时落库(幂等键防重复提交),中途离开不丢成绩
      try {
        await api("/records", { method: "POST", body: {
          subject: q2.subject, session_type: "bank_practice",
          total: 1, correct: correct ? 1 : 0, duration_min: null,
          knowledge_ids: q2.knowledge_ids || [],
          detail: [{ ref: q2.id, correct, knowledge_ids: q2.knowledge_ids || [] }],
          client_id: "qb-" + state.start + "-" + state.idx } });
      } catch (e) { toast("记录保存失败:" + e.message); }
      state.idx++; state.picked = null; state.submitted = false; state.revealed = false;
      render();
    });
  }
  async function finish() {
    const dur = Math.max(1, Math.round((Date.now() - state.start) / 60000));
    const bySub = {};
    state.detail.forEach(d => {
      bySub[d.subject] = bySub[d.subject] || { t: 0, c: 0 };
      bySub[d.subject].t++; if (d.correct) bySub[d.subject].c++;
    });
    let html = '<div class="card quiz-card" style="text-align:center;padding:40px 26px"><div style="font-size:40px">🎉</div><h2>题库练习完成</h2>'
      + `<p class="muted">用时 ${dur} 分钟 · ${state.detail.filter(d => d.correct).length}/${state.detail.length} 正确(每题已即时记入统计)</p>`;
    for (const [sub, v] of Object.entries(bySub)) {
      html += `<p class="muted">${SUBJECTS[sub]} ${v.c}/${v.t}</p>`;
    }
    html += '<div class="toolbar" style="justify-content:center;margin-top:10px"><a class="btn primary" href="#growth">看成长记录</a></div></div>';
    host.innerHTML = html;
  }
  render();
}

async function renderKnowledge(host) {
  const params = new URLSearchParams();
  if (kpFilter.subject) params.set("subject", kpFilter.subject);
  if (kpFilter.q) params.set("q", kpFilter.q);
  if (kpFilter.chapter) params.set("chapter_id", kpFilter.chapter);
  const [items, catalog, graph] = await Promise.all([
    api("/knowledge?" + params), api("/catalog"), api("/graph")]);
  const chapters = [];
  for (const t of Object.values(catalog.tracks || {}))
    (t.chapters || []).forEach(c => chapters.push({ ...c, subject: t.subject }));
  let html = `<div class="toolbar">
    <button class="primary" id="kp-add">+ 新建知识点</button>
    <select id="kp-subject"><option value="">全部科目</option>
      ${Object.entries(SUBJECTS).slice(0, 4).map(([v, n]) => `<option value="${v}" ${kpFilter.subject === v ? "selected" : ""}>${n}</option>`).join("")}</select>
    <select id="kp-chapter"><option value="">全部章节</option>
      ${chapters.map(c => `<option value="${c.id}" ${kpFilter.chapter === c.id ? "selected" : ""}>${SUBJECTS[c.subject]} · ${esc(c.name)}</option>`).join("")}</select>
    <input id="kp-q" placeholder="搜索" value="${esc(kpFilter.q)}" style="width:180px"></div>
  <div class="row2"><div id="kp-list">`;
  if (!items.length) html += '<div class="card state"><div class="big">📚</div><b>没有匹配的知识点</b><span>知识点是画像与计划的基础。</span></div>';
  for (const k of items) {
    html += `<div class="item" data-id="${k.id}">
      <div class="head"><b>${esc(k.name)}</b>
        <span><span class="tag ${SUBJECT_TAG[k.subject]}">${SUBJECTS[k.subject]}</span><span class="tag gray">${STATUS_TXT[k.status] || k.status}</span></span></div>
      <div class="sub">${esc((k.tags || []).join(" · ")) || "&nbsp;"}</div></div>`;
  }
  html += '</div><div id="kp-detail" class="card" style="align-self:start"><span class="muted">点击左侧知识点查看详情</span></div></div>';
  html += '<div class="card"><h2>知识点关联图</h2><div id="graph-box">' + drawGraph(graph) + "</div></div>";
  host.innerHTML = html;
  typeset(host);
  $("#kp-add").onclick = () => kpForm();
  $("#kp-subject").onchange = e => { kpFilter.subject = e.target.value; renderKnowledge(host); };
  $("#kp-chapter").onchange = e => { kpFilter.chapter = e.target.value; renderKnowledge(host); };
  $("#kp-q").onchange = e => { kpFilter.q = e.target.value.trim(); renderKnowledge(host); };
  $$("#kp-list .item").forEach(el => el.onclick = () => showKp(el.dataset.id, host));
}
async function showKp(id, host) {
  const k = await api("/knowledge/" + id);
  let html = `<div class="head"><h2 style="margin:0 0 8px">${esc(k.name)}</h2>
    <span><button id="kp-edit">编辑</button> <button id="kp-del" class="again">删除</button></span></div>
    <div style="margin-bottom:12px"><span class="tag ${SUBJECT_TAG[k.subject]}">${SUBJECTS[k.subject]}</span>
    <span class="tag gray">${STATUS_TXT[k.status] || k.status}</span>
    ${(k.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join("")}
    ${k.seed ? '<span class="tag orange">示例可删</span>' : ""}</div>
    <p class="muted">依据:${esc(k.source || "—")}</p><div>${md(k.content_md)}</div>`;
  for (const f of k.formulas || [])
    html += `<h3>公式</h3><div>$${f.latex}$</div><p class="muted">适用条件:${esc(f.condition || "—")}<br>常见误用:${esc(f.misuse || "—")}</p>`;
  for (const c of k.comparisons || []) html += `<h3>对比:${esc(c.with || "")}</h3>` + compareTable(c.table || {});
  html += `<h3>掌握状态</h3><div class="toolbar" style="margin-bottom:0">
    ${STATUS_ORDER.map(v => `<button data-st="${v}" ${k.status === v ? 'class="primary"' : ""}>${STATUS_TXT[v]}</button>`).join("")}</div>`;
  const box = $("#kp-detail");
  box.innerHTML = html;
  typeset(box);
  $("#kp-edit").onclick = () => kpForm(k, host);
  $("#kp-del").onclick = async () => {
    if (!confirm("确定删除知识点「" + k.name + "」?")) return;
    await api("/knowledge/" + k.id, { method: "DELETE" });
    toast("已删除"); renderKnowledge(host);
  };
  $$("#kp-detail button[data-st]").forEach(b => b.onclick = async () => {
    await api("/knowledge/" + k.id, { method: "PUT", body: { status: b.dataset.st } });
    toast("状态已更新"); showKp(k.id, host);
  });
}
function compareTable(table) {
  const rows = Object.entries(table);
  if (!rows.length) return "";
  const width = Math.max(...rows.map(([, v]) => (v || []).length));
  let html = '<table class="data" style="margin-top:8px"><tr><th>维度</th>'
    + Array.from({ length: width }, (_, i) => "<th>对象 " + (i + 1) + "</th>").join("") + "</tr>";
  for (const [dim, vals] of rows)
    html += "<tr><td><b>" + esc(dim) + "</b></td>" + Array.from({ length: width },
      (_, i) => "<td>" + esc((vals || [])[i] || "—") + "</td>").join("") + "</tr>";
  return html + "</table>";
}
function drawGraph(graph) {
  const nodes = graph.nodes || [], edges = graph.edges || [];
  if (!nodes.length) return '<span class="muted">暂无知识点</span>';
  const depth = {};
  nodes.forEach(n => depth[n.id] = 0);
  for (let i = 0; i < nodes.length + 2; i++)
    for (const e of edges)
      if (depth[e.to] < depth[e.from] + 1) depth[e.to] = depth[e.from] + 1;
  const colMap = {};
  nodes.forEach(n => (colMap[depth[n.id]] = colMap[depth[n.id]] || []).push(n));
  const NW = 136, NH = 46, GAP = 14, COLGAP = 196;
  const maxRows = Math.max(...Object.values(colMap).map(c => c.length));
  const W = Math.max(...Object.keys(colMap).map(Number)) * COLGAP + NW + 20;
  const H = maxRows * (NH + GAP) + 20;
  const pos = {};
  let svg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">`;
  for (const [col, list] of Object.entries(colMap)) {
    list.forEach((n, i) => {
      const x = col * COLGAP + 10, y = i * (NH + GAP) + 10;
      pos[n.id] = { x: x + NW / 2, y: y + NH / 2 };
      svg += `<g class="kp-node ${n.status === "mastered" ? "mastered" : ""}">
        <rect x="${x}" y="${y}" width="${NW}" height="${NH}" rx="10" stroke-width="1.5"></rect>
        <text x="${x + 10}" y="${y + 20}">${esc(n.name.slice(0, 9))}</text>
        <text x="${x + 10}" y="${y + 36}" fill="#8A93A0">${SUBJECTS[n.subject] || ""} · ${esc((STATUS_TXT[n.status] || "").slice(0, 3))}</text></g>`;
    });
  }
  for (const e of edges) {
    const a = pos[e.from], b = pos[e.to];
    if (a && b) svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="var(--border)" stroke-width="1.5"/>`;
  }
  return svg + "</svg>";
}
async function kpForm(existing, host) {
  const catalog = await api("/catalog");
  const chapters = [];
  for (const t of Object.values(catalog.tracks || {}))
    (t.chapters || []).forEach(c => chapters.push({ ...c, subject: t.subject }));
  const k = existing || { subject: "math", chapter_id: "", name: "", content_md: "", source: "", tags: [], prerequisites: [] };
  openModal(`<h2>${existing ? "编辑" : "新建"}知识点</h2>
    <div class="form-grid">
      <div><label>科目</label><select id="f-subject">
        ${Object.entries(SUBJECTS).slice(0, 4).map(([v, n]) => `<option value="${v}" ${k.subject === v ? "selected" : ""}>${n}</option>`).join("")}</select></div>
      <div><label>章节</label><select id="f-chapter"><option value="">(未选)</option>
        ${chapters.map(c => `<option value="${c.id}" ${k.chapter_id === c.id ? "selected" : ""}>${SUBJECTS[c.subject]} · ${esc(c.name)}</option>`).join("")}</select></div>
      <div><label>名称</label><input id="f-name" value="${esc(k.name)}" style="width:100%"></div>
      <div><label>标签(逗号分隔)</label><input id="f-tags" value="${esc((k.tags || []).join(","))}" style="width:100%"></div>
      <div class="full"><label>正文</label><textarea id="f-content" style="min-height:110px">${esc(k.content_md)}</textarea></div>
      <div class="full"><label>出处 / 依据</label><input id="f-source" value="${esc(k.source)}" style="width:100%"></div>
      <div class="full"><label>前置知识点 ID(逗号分隔)</label><input id="f-pre" value="${esc((k.prerequisites || []).join(","))}" style="width:100%"></div>
    </div>
    <p><button class="primary" id="f-save">保存</button> <button id="f-cancel">取消</button></p>`);
  $("#f-cancel").onclick = closeModal;
  $("#f-save").onclick = async () => {
    const body = {
      subject: $("#f-subject").value, chapter_id: $("#f-chapter").value,
      name: $("#f-name").value.trim(), content_md: $("#f-content").value,
      source: $("#f-source").value,
      tags: $("#f-tags").value.split(",").map(s => s.trim()).filter(Boolean),
      prerequisites: $("#f-pre").value.split(",").map(s => s.trim()).filter(Boolean),
    };
    if (!body.name) return toast("名称必填");
    try {
      if (existing) await api("/knowledge/" + existing.id, { method: "PUT", body });
      else await api("/knowledge", { method: "POST", body });
      closeModal(); toast("已保存"); renderKnowledge(host);
    } catch (e) { toast(e.message); }
  };
}

/* ================= AI 教练 ================= */
ROUTES.coach = async () => {
  const [status, history, reflections] = await Promise.all([
    api("/ai/status"), api("/coach/history"), api("/reflections?limit=5"),
  ]);
  let html = `<div class="page-head"><div>
    <div class="section-label">AI COACH</div><h1>AI 教练</h1></div></div>`;
  if (!status.available) {
    html += `<div class="hintbox"><b>AI 未就绪。</b>${esc(status.hint || "")}
      <br><a href="#account">去设置 →</a>&nbsp;<span class="muted">配置前:反思使用规则解析(明确标注),数据照常保存。</span></div>`;
  } else {
    html += `<div class="infobox">🤖 ${status.mode === "local" ? "本地模型" : "云端模型"} <b>${esc(status.model || "(未选)")}</b>${status.mode === "local" ? " · Ollama 运行中 · 数据不出机器" : ""} · 回答基于你的真实错题/练习/反思(检索式上下文),区分「有数据支持」与「待验证」。</div>`;
  }
  html += `<div class="row2">
    <div class="card"><h2>💬 与教练对话</h2>
      <div class="chat-box" id="chat-box">${history.map(renderMsg).join("") || '<span class="muted">问点什么,比如:"总结我最近一周最明显的三个问题"</span>'}</div>
      <div class="chat-input"><textarea id="chat-text" placeholder="向教练提问…(Enter 发送)"></textarea>
      <button class="primary" id="chat-send">发送</button></div></div>
    <div class="card"><h2>📝 快速反思(30 秒)</h2>
      <textarea id="ref-text" style="min-height:90px" placeholder="今天学了什么、卡在哪、感觉如何…"></textarea>
      <div class="toolbar" style="margin:10px 0 0">
        <button id="ref-voice" title="语音输入(Chrome/Edge)">🎤 语音</button>
        <button class="primary" id="ref-extract">提取结构化记录</button>
        <span class="muted" id="ref-voice-state"></span></div>
      <div id="ref-confirm"></div>
      <h2 style="margin-top:20px">最近的反思</h2>
      <div id="ref-list">${reflections.map(r => {
        const ex = r.extracted || {};
        return `<div class="item" style="cursor:default"><b>${esc(r.date)}</b>
          <span class="tag ${ex.source === "ai" ? "purple" : "gray"}">${ex.source === "ai" ? "AI 提取" : "规则提取"}</span>
          <div class="sub">${esc(ex.content || r.raw_text.slice(0, 60))}</div></div>`;
      }).join("") || '<span class="muted">还没有反思记录</span>'}</div></div></div>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  $("#chat-send").onclick = sendChat;
  $("#chat-text").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } };
  let streamAbort = null;
  async function sendChat() {
    const box = $("#chat-text");
    const msg = box.value.trim();
    if (!msg) return;
    box.value = "";
    $("#chat-box").insertAdjacentHTML("beforeend", renderMsg({ role: "user", content: msg, date: "刚刚" }));
    // 真实状态:检索中 → 生成中(字数)→ 完成(耗时)/失败
    $("#chat-box").insertAdjacentHTML("beforeend",
      '<div class="msg assistant" id="chat-live"><span class="muted" id="chat-state">🔍 检索你的学习记录…</span><div id="chat-delta"></div></div>');
    $("#chat-box").scrollTop = 1e9;
    const ctrl = new AbortController();
    streamAbort = ctrl;
    const sendBtn = $("#chat-send");
    const oldLabel = sendBtn.textContent;
    sendBtn.textContent = "停止";
    sendBtn.onclick = () => ctrl.abort();
    let acc = "";
    try {
      const res = await fetch("/api/coach/chat/stream", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }), signal: ctrl.signal });
      if (!res.ok) throw new Error("请求失败 " + res.status);
      const ct = res.headers.get("Content-Type") || "";
      if (ct.startsWith("application/json")) {  // 注意:x-ndjson 含 json 字样,必须精确匹配
        // AI 不可用:返回单个 JSON 错误
        const j = await res.json();
        throw new Error(j.error || "AI 不可用");
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder("utf-8");
      $("#chat-state").textContent = "✍️ 生成中";
      let buf = "";
      let proposal = null, elapsed = null, finalReply = null;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, idx).trim();
          buf = buf.slice(idx + 1);
          if (!line) continue;
          const j = JSON.parse(line);
          if (j.delta) {
            acc += j.delta;
            $("#chat-delta").textContent = acc;
            $("#chat-state").textContent = "✍️ 生成中 · " + acc.length + " 字";
            $("#chat-box").scrollTop = 1e9;
          }
          if (j.done) { proposal = j.proposal; elapsed = j.elapsed; finalReply = j.reply; }
          if (j.error) throw new Error(j.error);
        }
      }
      $("#chat-live").remove();
      $("#chat-box").insertAdjacentHTML("beforeend", renderMsg({
        role: "assistant", content: finalReply || acc || "(空回复,可重试)",
        date: "刚刚 · " + (elapsed || "?") + "s" }));
      // 工具提案:必须用户点击确认才执行
      if (proposal && proposal.tools && proposal.tools.length) {
        const chips = proposal.tools.map((t, i) => {
          const label = t.tool === "create_task"
            ? "创建任务:" + (t.title || "") + " ≈" + (t.est_minutes || 20) + " 分钟"
            : "创建里程碑:" + (t.title || "");
          return `<button class="btn" data-pi="${i}">✓ ${esc(label)}</button>`;
        }).join(" ");
        const wrapId = "propose-" + Date.now();
        $("#chat-box").insertAdjacentHTML("beforeend",
          `<div class="msg assistant system" id="${wrapId}">💡 教练提议以下操作(点击确认才会执行):<div class="toolbar" style="margin:6px 0 0">${chips}</div></div>`);
        $("#chat-box").scrollTop = 1e9;
        $$("#" + wrapId + " button[data-pi]").forEach(b => b.onclick = async () => {
          b.disabled = true;
          try {
            await api("/tools/execute", { method: "POST", body: {
              tool: proposal.tools[+b.dataset.pi].tool, args: proposal.tools[+b.dataset.pi] } });
            b.textContent = "✓ 已创建";
            toast("已按教练提案创建");
          } catch (e) { b.textContent = "✗ " + e.message; }
        });
      }
    } catch (e) {
      $("#chat-live") && $("#chat-live").remove();
      const aborted = e.name === "AbortError";
      if (acc) {
        $("#chat-box").insertAdjacentHTML("beforeend", renderMsg({
          role: "assistant", content: acc + (aborted ? "\n[已停止]" : ""), date: "刚刚" }));
        if (aborted) toast("已停止生成");
      } else {
        $("#chat-box").insertAdjacentHTML("beforeend", renderMsg({
          role: "assistant", content: "[系统] " + (aborted ? "已取消" : e.message), date: "刚刚", system: true }));
      }
    }
    sendBtn.textContent = oldLabel;
    sendBtn.onclick = sendChat;
    streamAbort = null;
    $("#chat-box").scrollTop = 1e9;
  }
  // 语音输入(Web Speech API,不可用时按钮禁用)
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const vb = $("#ref-voice");
  if (!SR) { vb.disabled = true; vb.title = "当前浏览器不支持语音识别"; }
  else {
    let rec = null;
    vb.onclick = () => {
      if (rec) { rec.stop(); return; }
      rec = new SR();
      rec.lang = "zh-CN";
      rec.onresult = e => {
        $("#ref-text").value = ($("#ref-text").value + " " + e.results[0][0].transcript).trim();
      };
      rec.onend = () => { rec = null; $("#ref-voice-state").textContent = ""; vb.textContent = "🎤 语音"; };
      rec.onerror = () => { $("#ref-voice-state").textContent = "语音识别不可用"; rec = null; };
      $("#ref-voice-state").textContent = "🎤 听写中…再点一次结束";
      rec.start();
    };
  }
  $("#ref-extract").onclick = async () => {
    const text = $("#ref-text").value.trim();
    if (!text) return toast("先写点内容");
    $("#ref-confirm").innerHTML = '<div class="infobox">解析中…</div>';
    const r = await api("/reflections/extract", { method: "POST", body: { text } });
    const ex = r.extracted || {};
    const srcTag = ex.source === "ai" ? "AI 提取" : "规则解析(未调用 AI)";
    $("#ref-confirm").innerHTML = `<div class="card" style="box-shadow:none;border:1px solid var(--border)">
      <div style="margin-bottom:6px"><span class="tag ${ex.source === "ai" ? "purple" : "gray"}">${srcTag}</span>
      ${r.ai_error ? '<span class="tag red">AI 出错,已回退规则解析</span>' : ""}</div>
      ${ex.notes ? '<div class="muted" style="margin-bottom:8px">' + esc(ex.notes) + "</div>" : ""}
      <div class="conf-list">
        <div class="conf-item"><b style="width:64px">科目</b><input id="c-subjects" value="${esc((ex.subjects || []).join(","))}" style="flex:1"></div>
        <div class="conf-item"><b style="width:64px">学了什么</b><input id="c-content" value="${esc(ex.content || "")}" style="flex:1"></div>
        <div class="conf-item"><b style="width:64px">用时(分)</b><input id="c-minutes" type="number" value="${ex.minutes || ""}" style="width:90px"></div>
        <div class="conf-item"><b style="width:64px">薄弱点</b><input id="c-weak" value="${esc((ex.weak_points || []).join(" ; "))}" style="flex:1"></div>
        <div class="conf-item"><b style="width:64px">困难</b><input id="c-diff" value="${esc((ex.difficulties || []).join(" ; "))}" style="flex:1"></div>
        <div class="conf-item"><b style="width:64px">状态</b><input id="c-mood" value="${esc(ex.mood || "")}" style="width:140px"></div>
        <div class="conf-item"><b style="width:64px">下一步</b><input id="c-plan" value="${esc(ex.next_plan || "")}" style="flex:1"></div>
      </div>
      <div class="toolbar" style="margin:12px 0 0"><button class="primary" id="c-save">确认保存</button>
      <button id="c-cancel">放弃</button></div></div>`;
    $("#c-cancel").onclick = () => $("#ref-confirm").innerHTML = "";
    $("#c-save").onclick = async () => {
      const split = s => (s || "").split(/[;；,，]/).map(x => x.trim()).filter(Boolean);
      const extracted = { ...ex,
        subjects: split($("#c-subjects").value), content: $("#c-content").value,
        minutes: +$("#c-minutes").value || null,
        weak_points: split($("#c-weak").value), difficulties: split($("#c-diff").value),
        mood: $("#c-mood").value, next_plan: $("#c-plan").value };
      await api("/reflections", { method: "POST", body: { raw_text: text, extracted, confirmed: true } });
      toast("反思已保存,将计入画像");
      ROUTES.coach();
    };
  };
};
function renderMsg(m) {
  return `<div class="msg ${m.role}${m.system ? " system" : ""}">${m.content.replace(/</g, "&lt;").replace(/\n/g, "<br>")}
    <span class="when">${esc((m.date || "").replace("T", " ").slice(0, 16))}</span></div>`;
}

/* ================= 成长(时间线/激励/里程碑) ================= */
let growthTab = "timeline";
ROUTES.growth = async (sub) => {
  if (sub) growthTab = sub;
  const names = { timeline: "时间线与热力图", motivation: "经验库与激励", milestones: "里程碑" };
  let html = `<div class="page-head"><div>
    <div class="section-label">GROWTH</div><h1>成长记录</h1></div></div>
  <div class="tabs">${Object.entries(names).map(([k, n]) =>
    `<button data-t="${k}" ${growthTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="growth-body"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  $$(".tabs button").forEach(b => b.onclick = () => { growthTab = b.dataset.t; ROUTES.growth(growthTab); });
  const body = $("#growth-body");
  if (growthTab === "timeline") await renderTimeline(body);
  else if (growthTab === "motivation") await renderMotivation(body);
  else await renderMilestones(body);
};

async function renderTimeline(host) {
  const [tl, hm, mot] = await Promise.all([
    api("/growth/timeline"), api("/growth/heatmap"), api("/motivation/daily")]);
  let html = `<div class="row2"><div class="card"><h2>📅 学习热力图(近半年)</h2>`;
  if (!hm.weeks.flat().some(c => c.count)) html += '<div class="state"><div class="big">🌱</div><span>记录会随每一天的练习、反思、复测逐渐填满。成长不只看连续打卡 —— 偶尔中断后回来,这里依然欢迎你。</span></div>';
  html += `<div class="heatmap">${hm.weeks.map(wk =>
    '<div class="wk">' + wk.map(c => {
      const lv = c.count === 0 ? "" : c.count <= 2 ? "l1" : c.count <= 5 ? "l2" : "l3";
      return `<div class="cell ${lv} ${c.future ? "future" : ""}" title="${c.date}:${c.count} 项"></div>`;
    }).join("") + "</div>").join("")}</div>
    <div class="status-legend" style="margin-top:8px"><span><i style="background:var(--bg-inset)"></i>0</span>
    <span><i style="background:var(--green-bg)"></i>1-2</span><span><i style="background:rgba(79,123,106,0.45)"></i>3-5</span>
    <span><i style="background:var(--green)"></i>6+</span></div></div>
  <div class="card"><h2>今日一句 · ${esc({ rational: "理性教练", gentle: "温和陪伴", sprint: "高强度冲刺" }[mot.style] || mot.style)}</h2>
    <p style="font-family:var(--font-serif);font-size:17px;line-height:1.8">「${esc(mot.quote.text)}」</p>
    <p class="muted" style="margin-bottom:0">—— ${esc(mot.quote.author)}(${esc(mot.quote.source)})</p>
    ${mot.growth_note ? '<div class="infobox" style="margin:12px 0 0">🏆 ' + esc(mot.growth_note) + "</div>" : ""}
    <p class="muted" style="margin:10px 0 0">激励风格可在 <a href="#account">个人中心</a> 调整;系统不使用打卡惩罚,中断后的回归同样值得记录。</p></div></div>
  <div class="card"><h2>成长时间线</h2><div class="timeline">`;
  if (!tl.length) html += '<div class="state"><div class="big">🕰️</div><span>完成任务、写反思、复测错题 —— 它们都会出现在这里。</span></div>';
  for (const d of tl.slice(0, 60)) {
    html += `<div class="tl-day"><div class="tl-date">${esc(d.date)}
      <span class="muted" style="font-weight:400">· ${d.events.length} 条 · 做题 ${d.questions}</span></div>
      ${d.events.map(e => '<div class="tl-ev">' + esc(e) + "</div>").join("")}</div>`;
  }
  html += "</div></div>";
  host.innerHTML = html;
  typeset(host);
}

async function renderMotivation(host) {
  const items = await api("/motivations");
  let html = `<div class="toolbar"><button class="primary" id="mo-add">+ 添加内容</button>
    <span class="muted">经验文章、激励语句、你自己的复盘故事;每条注明作者与来源,禁止虚构他人案例。</span></div>
  <div class="row2"><div>`;
  if (!items.length) html += '<div class="card state"><div class="big">📖</div><b>经验库还是空的</b><span>记录你自己的复盘与感悟;引用他人内容务必注明出处与授权。</span></div>';
  for (const m of items) {
    html += `<div class="item" style="cursor:default"><div class="head"><b>${esc(m.title || (m.type === "story" ? "复盘故事" : "激励语句"))}</b>
      <button class="again" data-del="${m.id}">删除</button></div>
      <div style="font-size:14px;margin-top:6px">${md(m.text)}</div>
      <div class="sub">作者:${esc(m.author || "—")} · 来源:${esc(m.source_url || "自述")} · 授权:${esc(m.license || "自述")}</div></div>`;
  }
  html += "</div><div>";
  html += '<div class="card"><h2>内容规范</h2><div style="font-size:13px" class="muted">'
    + "· 每条内容保存标题、作者、来源链接、类型与授权状态<br>"
    + "· 不得编造真实人物的录取结果或经历<br>"
    + "· 引用他人内容请注明来源;无法确认授权的只留链接</div></div></div></div>";
  host.innerHTML = html;
  typeset(host);
  $$("#growth-body button[data-del]").forEach(b => b.onclick = async () => {
    await api("/motivations/" + b.dataset.del, { method: "DELETE" });
    renderMotivation(host);
  });
  $("#mo-add").onclick = () => {
    openModal(`<h2>添加经验 / 激励内容</h2>
    <div class="form-grid">
      <div><label>类型</label><select id="mo-type"><option value="quote">激励语句</option><option value="story">复盘故事 / 经验</option></select></div>
      <div><label>标题</label><input id="mo-title" style="width:100%"></div>
      <div class="full"><label>正文</label><textarea id="mo-text"></textarea></div>
      <div><label>作者</label><input id="mo-author" style="width:100%"></div>
      <div><label>来源链接(自述可留空)</label><input id="mo-url" style="width:100%"></div>
      <div class="full"><label>授权 / 许可(引用他人内容必填)</label><input id="mo-license" placeholder="如:CC BY 4.0 / 已获授权 / 公共领域" style="width:100%"></div>
    </div>
    <p><button class="primary" id="mo-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
    $("#mo-save").onclick = async () => {
      if (!$("#mo-text").value.trim()) return toast("正文必填");
      await api("/motivations", { method: "POST", body: {
        type: $("#mo-type").value, title: $("#mo-title").value, text: $("#mo-text").value,
        author: $("#mo-author").value, source_url: $("#mo-url").value,
        license: $("#mo-license").value } });
      closeModal(); toast("已保存"); renderMotivation(host);
    };
  };
}

async function renderMilestones(host) {
  const goals = await api("/goals");
  let html = `<div class="toolbar"><button class="primary" id="ms-add">+ 添加里程碑</button></div>`;
  const ms = goals.milestones || [];
  if (!ms.length) html += '<div class="card state"><div class="big">🏆</div><b>还没有里程碑</b><span>把备考拆成几个可庆祝的节点:完成基础篇、第一套模考、真题二刷…</span></div>';
  else html += '<div class="card">' + ms.map(m => `<div class="task ${m.done ? "done" : ""}">
    <span class="tag ${m.done ? "green" : "gray"}">${m.done ? "已达成" + (m.done_date ? " " + m.done_date : "") : "进行中"}</span>
    <span class="title">${esc(m.title)}${m.target_date ? ' <span class="muted">目标 ' + m.target_date + "</span>" : ""}</span>
    <span class="btns">${m.done ? "" : `<button data-done="${m.id}">标记达成</button>`}</span></div>`).join("") + "</div>";
  if (goals.institution) html += `<div class="card"><h2>目标院校</h2><p style="margin:0 0 6px"><b>${esc(goals.institution)}</b>${goals.program ? " · " + esc(goals.program) : ""}</p>
    ${(goals.official_links || []).map(l => `<a href="${esc(l)}" target="_blank" rel="noopener">${esc(l)}</a>`).join("<br>")}
    <p class="muted" style="margin-bottom:0">在「情报站 → 梦校」中维护招生信息并核验。</p></div>`;
  host.innerHTML = html;
  $("#ms-add").onclick = () => openModal(`<h2>添加里程碑</h2>
    <label>标题</label><input id="ms-title" style="width:100%">
    <label>目标日期(可选)</label><input id="ms-date" type="date" style="width:100%">
    <p><button class="primary" id="ms-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
  $("#ms-save").onclick = async () => {
    if (!$("#ms-title").value.trim()) return toast("标题必填");
    await api("/goals/milestones", { method: "POST", body: {
      title: $("#ms-title").value, target_date: $("#ms-date").value || null } });
    closeModal(); renderMilestones(host);
  };
  $$("button[data-done]", host).forEach(b => b.onclick = async () => {
    await api("/goals/milestones/" + b.dataset.done, { method: "PUT", body: {
      done: true, done_date: todayStr() } });
    toast("🏆 里程碑达成,已记入时间线"); renderMilestones(host);
  });
}

/* ================= 情报站 ================= */
let intelTab = "search";
ROUTES.intel = async (sub) => {
  if (sub) intelTab = sub;
  const names = { hot: "热点雷达", search: "搜索", sources: "来源清单", schools: "梦校与目标", exp: "经验与方法", quality: "数据质量" };
  let html = `<div class="page-head"><div>
    <div class="section-label">INTELLIGENCE</div><h1>考研情报站</h1></div></div>
  <div class="tabs">${Object.entries(names).map(([k, n]) =>
    `<button data-t="${k}" ${intelTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="intel-body"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  $$(".tabs button").forEach(b => b.onclick = () => { intelTab = b.dataset.t; ROUTES.intel(intelTab); });
  const body = $("#intel-body");
  if (intelTab === "search") await renderSearch(body);
  else if (intelTab === "sources") await renderSources(body);
  else if (intelTab === "exp") await renderExperience(body);
  else if (intelTab === "quality") await renderQuality(body);
  else if (intelTab === "hot") await renderHot(body);
  else await renderSchools(body);
};

/* ================= 热点雷达(V3.1) ================= */
const RADAR_CTYPES = { hot: "A·近期热点", exp: "B·真实经验", method: "C·学习方法",
  policy: "D·招生政策", mindset: "E·情绪压力", ai: "F·AI原创", warn: "G·警惕营销", expired: "H·已过期" };
const VERIFY_LABEL = { verified_page: "已核验原文", snippet_only: "仅摘要·日期未核验", user_submitted: "用户提交·待核验", api: "官方API元数据" };
let radarCats = {}, radarLevs = {};

async function renderHot(host) {
  const q = new URLSearchParams(location.hash.split("?")[1] || "");
  let bucket = q.get("bucket") || "7";
  let ctype = q.get("ctype") || "";
  let hotCat = "";
  host.innerHTML = `<div class="infobox" id="hot-status">加载中…</div>
    <div class="toolbar" style="flex-wrap:wrap;gap:8px">
      <select id="hot-bucket">${["7", "30", "90", "all"].map(b =>
        `<option value="${b}" ${bucket === b ? "selected" : ""}>${{ "7": "最近 7 天", "30": "最近 30 天", "90": "最近 90 天", all: "全部" }[b]}</option>`).join("")}</select>
      <select id="hot-ctype"><option value="">全部类型</option>${Object.entries(RADAR_CTYPES).map(([k, n]) =>
        `<option value="${k}" ${ctype === k ? "selected" : ""}>${n}</option>`).join("")}</select>
      <select id="hot-cat"><option value="">全部分类</option></select>
      <button class="primary" id="hot-refresh">⟳ 刷新近期热点</button>
      <button id="hot-submit">＋ 提交链接</button>
      <button id="hot-fav">★ 收藏</button>
      <button id="hot-cfg">⚙ 数据源</button>
    </div>
    <div id="hot-list"></div>`;
  $("#hot-bucket").onchange = e => { bucket = e.target.value; loadList(); };
  $("#hot-ctype").onchange = e => { ctype = e.target.value; loadList(); };
  api("/radar?bucket=all").then(d => {
    const sel = $("#hot-cat");
    if (sel && d.categories) sel.innerHTML = '<option value="">全部分类</option>' +
      Object.entries(d.categories).map(([k, n]) => `<option value="${k}">${n}</option>`).join("");
  }).catch(() => {});
  $("#hot-cat").onchange = e => { hotCat = e.target.value; loadList(); };
  $("#hot-refresh").onclick = doRefresh;
  $("#hot-submit").onclick = submitModal;
  $("#hot-fav").onclick = () => { location.hash = "#intel/hot?bucket=all"; bucket = "all"; ctype = ""; loadList("favorite=1"); };
  $("#hot-cfg").onclick = cfgModal;

  async function loadList(extra) {
    const p = new URLSearchParams();
    if (bucket !== "all" && !extra) p.set("bucket", bucket);
    if (ctype) p.set("ctype", ctype);
    if (hotCat) p.set("category", hotCat);
    if (extra) extra.split("&").forEach(kv => { const [k2, v2] = kv.split("="); if (v2) p.set(k2, v2); });
    const d = await api("/radar?" + p.toString());
    const st = d.status || {};
    $("#hot-status").innerHTML = `
      <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
        <span class="sysdot ok"></span>上次成功检索:${st.last_success ? esc(st.last_success.replace("T", " ")) : "从未"}
        ${st.failure_reason ? `<span class="tag red">上次失败:${esc(st.failure_reason)}</span>` : ""}
      </div>
      <div class="muted" style="margin-top:6px;font-size:12px">
        通道:DuckDuckGo 公开搜索 + 研招网官方列表 + 用户提交链接。抖音/小红书无公开检索接口,不做自动抓取(不绕过登录/反爬),可用「提交链接」收录公开内容。
        ${st.last_stats ? `上次:查询 ${st.last_stats.queried} 组·候选 ${st.last_stats.candidates}·新增 ${st.last_stats.added}·重复 ${st.last_stats.duplicates}·过滤 ${st.last_stats.rejected}` : ""}</div>`;
    radarCats = d.categories || {}; radarLevs = d.levels || {};
    $("#hot-list").innerHTML = d.items.length ? d.items.map(itemCard).join("")
      : `<div class="card"><div class="muted" style="padding:20px;text-align:center">
          ${bucket === "7" ? "最近 7 天暂无已核验发布时间的内容。可放宽到 30 天,或点击「刷新近期热点」检索。" : "暂无内容,点击「刷新近期热点」开始第一次检索。"}</div></div>`;
    $$(".hot-item").forEach(card => {
      const it = d.items.find(x => x.id === card.dataset.id);
      if (it) card._url = it.url;
    });
    bindCards();
  }

  async function doRefresh() {
    const btn = $("#hot-refresh");
    btn.disabled = true; btn.textContent = "检索中…(最长约 90 秒,勿关页面)";
    try {
      const r = await api("/radar/refresh", { method: "POST" });
      const s = r.stats;
      toast(r.ok ? `检索完成:新增 ${s.added} 条(7天内 ${s.bucket_7d},30天 ${s.bucket_30d},90天 ${s.bucket_90d})`
        : "检索失败:" + (r.failure_reason || "网络不可用"), r.ok ? "ok" : "err");
      if (!r.ok) toast("已保留上次成功的数据,不会显示伪造热点", "err");
    } catch (e) { toast("刷新失败:" + e.message, "err"); }
    btn.disabled = false; btn.textContent = "⟳ 刷新近期热点";
    loadList();
  }

  function itemCard(i) {
    const sc = (i.score || {}).total ?? "—";
    const dateBadges = [
      i.published_at ? `发布 ${esc(i.published_at)}` : "发布时间未核验",
      VERIFY_LABEL[i.verify_status] || i.verify_status,
      i.ctype === "warn" ? '<span class="tag red">营销嫌疑·仅供警惕</span>' : ""
    ].filter(Boolean).map(t => `<span class="tag ${i.published_at ? "gray" : "amber"}">${t}</span>`).join(" ");
    return `<div class="card hot-item" data-id="${i.id}" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
        <b style="cursor:pointer" class="hot-title">${esc(i.title)}</b>
        <span class="score-pill" title="${esc((i.score || {}).rationale || "")}">${sc}<small>/100</small></span>
      </div>
      <div class="muted" style="font-size:13px;margin:6px 0">${esc(i.summary || "(无摘要)")}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <span class="tag blue">${RADAR_CTYPES[i.ctype] || i.ctype}</span>
        ${i.category ? `<span class="tag gray">${esc(radarCats[i.category] || i.category)}</span>` : ""}
        <span class="tag ${i.source_level === "S" ? "green" : i.source_level === "AI" ? "blue" : "gray"}" title="数据可信度等级">${esc(radarLevs[i.source_level] || "来源未定")}</span>
        <span class="tag gray">${esc(i.platform)}</span>
        ${i.subject && i.subject !== "general" ? `<span class="tag gray">${SUBJECTS[i.subject] || i.subject}</span>` : ""}
        ${dateBadges}</div>
      <div class="hot-actions">
        <button data-act="open" class="btn">原文 ↗</button>
        <button data-act="useful">👍 有用</button>
        <button data-act="not_useful">👎 没帮助</button>
        <button data-act="practiced">✅ 已实践</button>
        <button data-act="favorite">${i.favorite ? "★ 已藏" : "☆ 收藏"}</button>
        <button data-act="hide">🚫 隐藏</button>
        <button data-act="dislike_type" title="降低此类内容的推荐权重">不再推荐此类</button>
        <button data-act="reverify">核验</button>
      </div>
      ${(i.feedback && (i.feedback.useful || i.feedback.not_useful || i.feedback.practiced)) ?
        `<div class="muted" style="font-size:12px;margin-top:6px">反馈:👍${i.feedback.useful || 0} 👎${i.feedback.not_useful || 0}${i.feedback.practiced ? " · 已实践(欢迎回头记录效果)" : ""}</div>` : ""}
    </div>`;
  }

  function bindCards() {
    $$(".hot-item").forEach(card => {
      const id = card.dataset.id;
      card.querySelector(".hot-title").onclick = () => { if (card._url) window.open(card._url, "_blank"); };
      card.querySelectorAll("button[data-act]").forEach(b => {
        if (b.dataset.act === "open") {
          b.onclick = () => { if (card._url) window.open(card._url, "_blank"); };
          return;
        }
        b.onclick = async () => {
          const act = b.dataset.act;
          if (act === "reverify") {
            b.disabled = true; b.textContent = "核验中…";
            try { const r = await api("/radar/reverify", { method: "POST", body: JSON.stringify({ id }) });
              toast(r.message, r.ok ? "ok" : "err"); loadList(); } catch (e) { toast(e.message, "err"); b.disabled = false; b.textContent = "核验"; }
            return;
          }
          try { await api("/radar/feedback", { method: "POST", body: JSON.stringify({ id, action: act }) });
            toast("已记录,会影响后续推荐", "ok"); loadList(); } catch (e) { toast(e.message, "err"); }
        };
      });
    });
  }

  function submitModal() {
    openModal(`<h2>提交公开内容链接</h2>
      <p class="muted" style="font-size:13px">适用于抖音/小红书/公众号等你看到的公开考研内容。系统只存链接与你的备注,不抓取登录内容。</p>
      <div><label>链接 *</label><input id="hs-url" placeholder="https://..."></div>
      <div><label>标题 *</label><input id="hs-title" placeholder="内容标题"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><label>平台</label><select id="hs-plat">${["自动识别", "抖音", "小红书", "B站", "知乎", "微信公众号", "微博", "其他"].map(p2 => `<option>${p2}</option>`).join("")}</select></div>
        <div><label>发布日期(选填)</label><input id="hs-date" placeholder="2026-10-20"></div></div>
      <div><label>备注(为什么值得关注)</label><textarea id="hs-note" rows="3"></textarea></div>
      <button class="primary" id="hs-go">提交</button>`);
    $("#hs-go").onclick = async () => {
      try {
        await api("/radar/submit", { method: "POST", body: JSON.stringify({
          url: $("#hs-url").value, title: $("#hs-title").value,
          platform: $("#hs-plat").value === "自动识别" ? "" : $("#hs-plat").value,
          published_at: $("#hs-date").value, note: $("#hs-note").value }) });
        toast("已入库(标记为用户提交·待核验)", "ok"); closeModal(); loadList();
      } catch (e) { toast(e.message, "err"); }
    };
  }

  function cfgModal() {
    api("/radar/settings").then(cfg => {
      openModal(`<h2>数据源与设置</h2>
        <div class="infobox">实际通道:${cfg.channels.map(esc).join("；")}。<br>限制:${esc(cfg.limits)}。</div>
        <div><label>HTTP 代理(检索通道用,留空=直连)</label><input id="hc-proxy" value="${esc(cfg.proxy || "")}" placeholder="http://127.0.0.1:7897"></div>
        <div><label>每次检索关键词组数(1-12)</label><input id="hc-n" type="number" min="1" max="12" value="${cfg.max_queries}"></div>
        <label style="display:flex;gap:8px;align-items:center;margin:10px 0"><input type="checkbox" id="hc-auto" ${cfg.auto_refresh ? "checked" : ""}> 定时自动刷新(每 6 小时,需本机服务常驻;默认关闭)</label>
        <button class="primary" id="hc-go">保存</button>`);
      $("#hc-go").onclick = async () => {
        try { await api("/radar/settings", { method: "POST", body: JSON.stringify({
            proxy: $("#hc-proxy").value, max_queries: $("#hc-n").value, auto_refresh: $("#hc-auto").checked }) });
          toast("已保存", "ok"); closeModal(); } catch (e) { toast(e.message, "err"); }
      };
    });
  }

  await loadList();
}

async function renderHomeRadar() {
  const host = $("#radar-cards");
  if (!host) return;
  let d;
  try { d = await api("/radar/home"); } catch (e) { host.innerHTML = `<div class="muted">雷达暂不可用:${esc(e.message)}</div>`; return; }
  const b = d.brief || {}, snap = d.snapshot || {}, obs = d.observation || {},
    top = d.top || { items: [], note: "" }, bd = d.breakdown, st = d.status || {};
  const genBadge = b.generator === "ai"
    ? `<span class="tag blue">AI 改写(${esc(b.model || "")})·事实来自真实数据</span>`
    : '<span class="tag gray">规则引擎·基于真实学习数据</span>';
  const NEED_NAMES = { baseline: "建立基线", shrink: "缩小任务", math_method: "数学方法",
    english_method: "英语方法", cs408_method: "408方法", advanced: "上强度",
    maintain: "保持节奏", restart: "重启恢复", key_stage: "关键阶段", mock_drop: "成绩波动" };
  const foundBlock = b.found
    ? `<a href="${esc(b.found.url)}" target="_blank" rel="noopener">${esc(b.found.title)}</a>
       <span class="tag gray" style="margin-left:6px">${esc(b.found.platform)}${b.found.published_at ? " · " + esc(b.found.published_at) : " · 日期未核验"} · 评分 ${b.found.score}</span>`
    : `<span class="muted">${esc(b.found_note || "近期无匹配内容")}</span>`;
  const bf = b.feedback || {};
  const briefCard = `
    <div class="card radar-card radar-brief">
      <h2>⚡ 今日行动建议${b.need ? `<span class="tag amber" style="margin-left:6px">${NEED_NAMES[b.need] || b.need}</span>` : ""}</h2>
      <div class="bf-row"><span class="bf-key">近期发现</span><div>${foundBlock}</div></div>
      <div class="bf-row"><span class="bf-key">为什么与你有关</span><div>${esc(b.why || "")}</div></div>
      <div class="bf-row"><span class="bf-key">今天能做什么</span><div class="bf-act">${esc(b.action || "")}</div></div>
      <div class="bf-row"><span class="bf-key">复盘指标</span><div class="muted">${esc(b.metric || "")}</div></div>
      <div class="hot-actions" style="margin-top:10px">
        <button id="bf-useful">👍 有用${bf.useful ? " " + bf.useful : ""}</button>
        <button id="bf-notuseful">👎 没帮助${bf.not_useful ? " " + bf.not_useful : ""}</button>
        <button id="bf-practiced">✅ 已实践</button>
        <button id="bf-regen">↻ 换一条</button></div>
      <div style="margin-top:8px">${genBadge}</div>
    </div>`;
  const topCard = `
    <div class="card radar-card">
      <h2>📡 今日考研雷达 <span class="muted" style="font-size:12px;font-weight:400">(${esc(top.note)})</span></h2>
      ${top.items.length ? top.items.slice(0, 5).map(i => `
        <div class="radar-li">
          <a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>
          <div class="muted" style="font-size:12px">${esc(i.platform)} · ${i.published_at ? "发布 " + esc(i.published_at) : "日期未核验"} · ${esc(RADAR_CTYPES[i.ctype] || i.ctype)} · 评分 ${((i.score || {}).total ?? "—")}</div>
        </div>`).join("")
      : `<div class="muted">还没有内容。${st.last_success ? "上次检索 " + esc(st.last_success.slice(0, 16).replace("T", " ")): "从未检索过"} → <a href="#intel/hot">去刷新</a></div>`}
    </div>`;
  const bdCard = bd ? `
    <div class="card radar-card">
      <h2>🔍 今日经验拆解</h2>
      <a href="${esc(bd.item.url)}" target="_blank" rel="noopener"><b>${esc(bd.item.title)}</b></a>
      <span class="tag gray" style="margin-left:6px">${esc(bd.item.platform)} · ${bd.item.published_at ? esc(bd.item.published_at) : "日期未核验"}</span>
      <div class="bf-row" style="margin-top:8px"><span class="bf-key">适用条件</span><div>${esc(bd.conditions)}</div></div>
      <div class="bf-row"><span class="bf-key">操作步骤</span><div>${esc(bd.steps)}</div></div>
      <div class="bf-row"><span class="bf-key">潜在局限</span><div class="muted">${esc(bd.limits)}</div></div>
      ${bd.generator === "ai" ? '<span class="tag blue">AI 按原文摘要提炼</span>' : '<span class="tag gray">规则拆解</span>'}
    </div>`
    : `<div class="card radar-card"><h2>🔍 今日经验拆解</h2><div class="muted">暂无可拆解的经验内容,先去 <a href="#intel/hot">刷新热点</a>。</div></div>`;
  const obsCard = `
    <div class="card radar-card">
      <h2>📈 本周备考观察</h2>
      ${(obs.topics || []).length ? obs.topics.map(t =>
        `<span class="tag blue">${esc(t.tag)} ×${t.count}</span>`).join(" ")
      : '<span class="muted">近 14 天暂无入库内容</span>'}
      ${(obs.my_tags || []).length ? `<div style="margin-top:8px;font-size:13px">你的高频错题标签:${obs.my_tags.map(([k, n]) =>
        `<span class="tag amber">${esc(k)} ×${n}</span>`).join(" ")}</div>` : ""}
      <div class="muted" style="font-size:12px;margin-top:8px">${esc((obs.sample || {}).note || "")}</div>
    </div>`;
  const t = snap.today || {}, w = snap.week || {};
  const meCard = `
    <div class="card radar-card">
      <h2>🧭 我的备考状态</h2>
      <div class="me-grid">
        <div><b>${t.done}/${t.total || 20}</b><span>今日训练</span></div>
        <div><b>${w.acc == null ? "—" : w.acc + "%"}</b><span>近7天正确率(${w.total || 0}题)</span></div>
        <div><b>${w.active_days || 0}</b><span>近7天活跃</span></div>
        <div><b>${snap.due_today || 0}</b><span>今日到期复测</span></div>
      </div>
      ${snap.has_records ? "" : '<div class="muted" style="margin-top:8px">学习记录不足,系统不会假装了解你的状态 —— 完成第一组训练后这里会变成真实数据。</div>'}
    </div>`;
  host.innerHTML = briefCard + topCard + bdCard + obsCard + meCard;
  // 语录降级为兜底:有真实行动建议时替换 hero 顶部文案
  const hq = $("#hero-quote");
  if (hq && b.action) hq.innerHTML = "⚡ " + esc(b.action) +
    ' <a href="#intel/hot" style="font-size:13px;white-space:nowrap">依据与来源 →</a>';
  const fb = async act => {
    try { await api("/radar/brief/feedback", { method: "POST", body: JSON.stringify({ action: act }) });
      toast("已记录,会影响后续建议", "ok"); } catch (e) { toast(e.message, "err"); }
  };
  $("#bf-useful").onclick = () => fb("useful");
  $("#bf-notuseful").onclick = () => fb("not_useful");
  $("#bf-practiced").onclick = () => fb("practiced");
  $("#bf-regen").onclick = async () => {
    try { await api("/radar/brief/regenerate", { method: "POST" }); renderHomeRadar(); }
    catch (e) { toast(e.message, "err"); }
  };
}

async function renderSearch(host) {
  let html = `<div class="infobox">搜索 GitHub 公开仓库(招生政策请以官方公告为准;AI 摘要不能替代原文)。</div>
  <div class="toolbar"><input id="gh-q" placeholder="搜索关键词,如:408 真题 / 考研数学" style="flex:1;min-width:200px">
  <button class="primary" id="gh-go">搜索</button></div><div id="gh-results"></div>
  <h2 style="margin-top:20px">搜索历史</h2><div id="gh-history" class="muted">加载中…</div>`;
  host.innerHTML = html;
  const loadHistory = async () => {
    const recs = await api("/search/records");
    $("#gh-history").innerHTML = recs.length
      ? recs.slice(0, 12).map(r => `<div class="task"><span class="title">${esc(r.q)}</span><span class="tag gray">${r.results} 条 · ${esc((r.date || "").slice(0, 10))}</span></div>`).join("")
      : "还没有搜索记录";
  };
  loadHistory();
  const go = async () => {
    const q = $("#gh-q").value.trim();
    if (!q) return;
    $("#gh-results").innerHTML = '<div class="muted">搜索中…</div>';
    try {
      const r = await api("/search/github?q=" + encodeURIComponent(q));
      $("#gh-results").innerHTML = !r.items.length
        ? '<div class="state"><span>没有结果</span></div>'
        : r.items.map(it => `<div class="item" style="cursor:default"><div class="head">
            <b><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.full_name)}</a></b>
            <span><span class="tag gray">★ ${it.stars ?? 0}</span>
            <span class="tag ${it.license && it.license !== "null" ? "green" : "orange"}">${it.license && it.license !== "null" ? it.license : "无许可证"}</span></span></div>
            <div class="sub">${esc(it.description || "无描述")} · 最近推送 ${esc((it.pushed_at || "").slice(0, 10))}</div></div>`).join("")
          + '<div class="muted" style="margin-top:8px">⚠ 无许可证的仓库不得复制内容入库;添加到来源清单后统一核验。</div>';
      loadHistory();
    } catch (e) {
      $("#gh-results").innerHTML = '<div class="hintbox">搜索失败:' + esc(e.message) + "</div>";
    }
  };
  $("#gh-go").onclick = go;
  $("#gh-q").onkeydown = e => { if (e.key === "Enter") go(); };
}

async function renderSources(host) {
  const items = await api("/sources");
  let html = `<div class="toolbar"><button class="primary" id="src-add">+ 添加来源</button>
    <span class="muted">无许可证 = 只留链接不导入内容</span></div>`;
  if (!items.length) html += '<div class="card state"><div class="big">🗂️</div><b>来源清单为空</b><span>把搜到的仓库/文章加入清单,逐个核验许可证与有效性。</span></div>';
  for (const s of items) {
    html += `<div class="item" style="cursor:default"><div class="head">
      <div style="min-width:0"><b><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a></b>
      <div class="sub">许可:${esc(s.license)} · 状态:${esc(s.status)}${s.notes ? " · " + esc(s.notes) : ""}</div>
      ${s.last_checked ? '<div class="sub">最近核验:' + esc(s.last_checked.slice(0, 16)) + " · " + esc(s.check_result || "") + "</div>" : ""}</div>
      <span class="btns"><button data-check="${s.id}">核验链接</button><button class="again" data-del="${s.id}">删除</button></span></div></div>`;
  }
  host.innerHTML = html;
  $("#src-add").onclick = () => openModal(`<h2>添加资料来源</h2>
    <label>URL</label><input id="src-url" style="width:100%" placeholder="https://github.com/...">
    <div class="form-grid">
      <div><label>名称</label><input id="src-name" style="width:100%"></div>
      <div><label>类型</label><select id="src-kind" style="width:100%"><option value="repo">GitHub 仓库</option><option value="article">文章</option><option value="official">官方公告</option></select></div>
      <div><label>许可证</label><input id="src-license" style="width:100%" placeholder="MIT / CC BY 4.0 / 无许可证"></div>
      <div><label>状态</label><select id="src-status" style="width:100%"><option>待核验</option><option>仅链接</option><option>可引用</option><option>已导入</option></select></div>
      <div class="full"><label>备注</label><input id="src-notes" style="width:100%"></div>
    </div>
    <p><button class="primary" id="src-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
  $("#src-save").onclick = async () => {
    if (!$("#src-url").value.trim()) return toast("URL 必填");
    await api("/sources", { method: "POST", body: {
      url: $("#src-url").value, name: $("#src-name").value, kind: $("#src-kind").value,
      license: $("#src-license").value, status: $("#src-status").value, notes: $("#src-notes").value } });
    closeModal(); renderSources(host);
  };
  $$("button[data-check]", host).forEach(b => b.onclick = async () => {
    b.textContent = "核验中…";
    try {
      const s = await api("/sources/" + b.dataset.check + "/check", { method: "POST" });
      b.textContent = s.check_result || "已核验";
    } catch (e) { b.textContent = "核验失败"; }
  });
  $$("button[data-del]", host).forEach(b => b.onclick = async () => {
    await api("/sources/" + b.dataset.del, { method: "DELETE" });
    renderSources(host);
  });
}

async function renderExperience(host) {
  const [items, cats] = [await api("/experience"),
    ["数学", "英语", "政治", "408", "择校", "复试", "调剂", "时间管理", "备考心态", "高效学习", "失败教训", "其他"]];
  let html = `<div class="toolbar">
    <button class="primary" id="exp-add">+ 添加经验/方法</button>
    <select id="exp-cat"><option value="">全部分类</option>
      ${cats.map(c => `<option>${c}</option>`).join("")}</select>
    <label style="margin:0"><input type="checkbox" id="exp-fav"> 只看收藏</label>
    <span class="muted">${items.length} 条 · 链接帖标注核验状态;单条经验≠普遍结论</span></div><div id="exp-list">`;
  if (!items.length) html += '<div class="card state"><div class="big">📖</div><b>经验库为空</b><span>手动添加公开文章链接(抖音/小红书/知乎等),或记录你自己的方法笔记——平台不会绕过平台限制去抓取。</span></div>';
  for (const p of items) {
    html += `<div class="item" style="cursor:default" data-id="${p.id}">
      <div class="head"><div style="min-width:0"><b>${p.favorite ? "⭐ " : ""}${esc(p.title)}</b>
        <div class="sub">${esc(p.platform || "自记")}${p.author ? " · " + esc(p.author) : ""}${p.published ? " · " + esc(p.published) : ""}
        ${p.url ? ' · <a href="' + esc(p.url) + '" target="_blank" rel="noopener">原文 ↗</a>' : ""}</div></div>
        <span>${p.source_type === "platform_original" ? '<span class="tag blue">平台原创·非真实博主经验</span>' : ""}
        <span class="tag ${p.verify_status.includes("可访问") || p.verify_status.includes("原创") ? "green" : p.verify_status.includes("无法") ? "red" : "amber"}">${esc(p.verify_status)}</span></span></div>
      <div style="font-size:13.5px;margin-top:6px">${esc(p.summary)}</div>
      ${(p.categories || []).map(c => '<span class="tag gray">' + esc(c) + "</span>").join(" ")}
      ${p.methods ? '<div class="sub" style="margin-top:4px">方法:' + esc(p.methods) + "</div>" : ""}
      <div class="toolbar" style="margin:8px 0 0;gap:6px">
        <button data-fav="${p.id}" class="${p.favorite ? "primary" : ""}">${p.favorite ? "已收藏" : "收藏"}</button>
        ${p.url ? '<button data-check="' + p.id + '">核验链接</button>' : ""}
        <button data-note="${p.id}">备注</button>
        <button class="again" data-del="${p.id}" style="margin-left:auto">删除</button></div></div>`;
  }
  html += "</div>";
  host.innerHTML = html;
  typeset(host);
  const refresh = () => renderExperience(host);
  $("#exp-cat").onchange = e => { host.dataset.cat = e.target.value; refresh(); };
  $("#exp-fav").onchange = e => { host.dataset.fav = e.target.checked ? "1" : ""; refresh(); };
  $$("button[data-fav]").forEach(b => b.onclick = async () => {
    const p = items.find(x => x.id === b.dataset.fav);
    await api("/experience/" + p.id, { method: "PUT", body: { favorite: !p.favorite } });
    refresh();
  });
  $$("button[data-check]").forEach(b => b.onclick = async () => {
    b.textContent = "核验中…";
    const p = await api("/experience/" + b.dataset.check + "/check", { method: "POST" });
    b.textContent = p.verify_status.slice(0, 14);
  });
  $$("button[data-note]").forEach(b => b.onclick = () => {
    const p = items.find(x => x.id === b.dataset.note);
    openModal(`<h2>个人备注</h2><textarea id="pn-note" style="min-height:110px">${esc(p.notes || "")}</textarea>
      <p><button class="primary" id="pn-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
    $("#pn-save").onclick = async () => {
      await api("/experience/" + p.id, { method: "PUT", body: { notes: $("#pn-note").value } });
      closeModal(); refresh();
    };
  });
  $$("button[data-del]").forEach(b => b.onclick = async () => {
    if (!confirm("删除该条?")) return;
    await api("/experience/" + b.dataset.del, { method: "DELETE" });
    refresh();
  });
  $("#exp-add").onclick = () => {
    openModal(`<h2>添加经验/方法</h2>
    <p class="muted">粘贴公开文章链接+你的摘要;或记录自己的方法。平台不抓取受限内容。</p>
    <div class="form-grid">
      <div class="full"><label>标题 *</label><input id="pe-title" style="width:100%"></div>
      <div><label>平台(抖音/小红书/知乎/B站/公众号…)</label><input id="pe-plat" style="width:100%"></div>
      <div><label>原文链接</label><input id="pe-url" placeholder="https://..." style="width:100%"></div>
      <div><label>作者(公开显示名)</label><input id="pe-author" style="width:100%"></div>
      <div><label>发布日期(可获得时)</label><input id="pe-date" placeholder="如 2026-03" style="width:100%"></div>
      <div class="full"><label>摘要(你的概括,不是复制全文)</label><textarea id="pe-sum"></textarea></div>
      <div class="full"><label>分类(逗号分隔)</label><input id="pe-cats" placeholder="如:数学,时间管理" style="width:100%"></div>
      <div class="full"><label>方法要点</label><input id="pe-methods" style="width:100%"></div>
      <div class="full"><label>适用阶段</label><input id="pe-stage" placeholder="基础/强化/冲刺/全程" style="width:100%"></div>
    </div>
    <p><button class="primary" id="pe-save">保存</button> <button onclick="closeModal()">取消</button></p>`);
    $("#pe-save").onclick = async () => {
      if (!$("#pe-title").value.trim()) return toast("标题必填");
      try {
        await api("/experience", { method: "POST", body: {
          title: $("#pe-title").value, platform: $("#pe-plat").value,
          url: $("#pe-url").value, author: $("#pe-author").value,
          published: $("#pe-date").value || null, summary: $("#pe-sum").value,
          categories: $("#pe-cats").value.split(",").map(s => s.trim()).filter(Boolean),
          methods: $("#pe-methods").value, stage: $("#pe-stage").value } });
        closeModal(); toast("已保存"); refresh();
      } catch (e) { toast(e.message); }
    };
  };
}

async function renderQuality(host) {
  const q = await api("/data-quality");
  const srcRow = (label, v) => `<div class="task"><span class="title">${label}</span><b>${v}</b></div>`;
  let html = `<div class="infobox">全部指标由真实数据计算;网页可打开不代表内容正确。生成于 ${esc(q.generated_at.replace("T", " "))}</div>
  <div class="row2">
    <div class="card"><h2>来源清单(${q.sources.total})</h2>
      ${srcRow("从未核验", q.sources.never_checked)}
      ${srcRow("超 30 天未核验", q.sources.stale)}
      ${srcRow("最近核验可访问", q.sources.accessible)}
      ${srcRow("无许可证(禁止导入内容)", q.sources.no_license)}
      <p class="muted" style="margin-bottom:0">最近成功核验:${esc(q.sources.last_success || "尚无")}</p></div>
    <div class="card"><h2>错题库(${q.mistakes.total})</h2>
      ${srcRow("缺正确解析", q.mistakes.missing_solution)}
      ${srcRow("缺错误原因", q.mistakes.missing_reason)}
      ${srcRow("AI 结果待确认", q.mistakes.needs_confirmation)}
      ${srcRow("疑似重复题面", q.mistakes.duplicates)}</div>
    <div class="card"><h2>知识点(${q.knowledge.total})</h2>
      ${srcRow("未开始", q.knowledge.not_started)}
      ${srcRow("缺出处(source)", q.knowledge.missing_source)}</div>
    <div class="card"><h2>最近活动</h2>
      ${srcRow("最近练习日期", esc(q.activity.last_record || "无"))}
      ${srcRow("最近反思日期", esc(q.activity.last_reflection || "无"))}
      ${srcRow("练习记录数", q.activity.records)}
      ${srcRow("反思记录数", q.activity.reflections)}</div>
  </div>
  <div class="hintbox" style="margin-bottom:0">${q.notes.map(esc).join("<br>")}</div>`;
  host.innerHTML = html;
  typeset(host);
}

async function renderSchools(host) {
  const items = await api("/universities?order=priority");
  const goals = await api("/goals");
  const starred = items.filter(u => u.priority > 0);
  let html = `<div class="infobox"><span class="sysdot on"></span>院校资料库:${items.length} 所候选 ·
    图片仅采用 <b>Wikimedia Commons 自由许可</b>资源并记录来源;招生人数/复试线必须绑定年份与来源,未核验一律标注「待核实」。</div>
  <div class="card" style="margin-bottom:16px"><h2>🏛️ 官方招生数据(按年份分档,S 级来源)</h2>
    <div class="toolbar" style="flex-wrap:wrap;gap:8px">
      <select id="adm-uni">${items.map(u => `<option value="${esc(u.id)}">${esc(u.name)}</option>`).join("")}</select>
      <select id="adm-year">${[2028, 2027, 2026].map(y => `<option value="${y}">${y} 年</option>`).join("")}</select>
      <button id="adm-load" class="btn">载入分档</button></div>
    <div id="adm-form" class="muted" style="padding:8px 0">选择院校与年份后载入。事实数字必须填来源;2028 档在官方发布前显示「官方未公开」。</div></div>
  ${goals.institution ? `<div class="target-hero" style="margin-bottom:16px">
    <div class="th-img">${uniImg(items.find(u => u.name === goals.institution), "fallback-svg")}</div>
    <div class="th-body"><h3 style="margin:0 0 4px">🎯 ${esc(goals.institution)}${goals.program ? " · " + esc(goals.program) : ""}</h3>
    <div class="muted">当前目标院校 · ${(goals.official_links || []).map(l => `<a href="${esc(l)}" target="_blank" rel="noopener">官方链接 ↗</a>`).join(" ")}</div>
    <div class="toolbar" style="margin:10px 0 0"><a class="btn" href="#growth/milestones">查看里程碑</a></div></div></div>` : ""}
  <div class="toolbar">
    <button class="primary" id="uni-add">+ 添加院校</button>
    <button id="uni-compare" ${starred.length >= 2 ? "" : "disabled"}>对比关注院校(${starred.length})</button>
    <span class="muted">点 ★ 设置关注度(1-3),当前目标院校在今日作战室展示</span></div>
  <div class="uni-grid stagger">`;
  if (!items.length) html += '<div class="card state"><div class="big">🏫</div><span>资料库为空</span></div>';
  for (const u of items) {
    const img = u.image || {};
    const isFallback = (img.license || "").includes("本系统生成");
    html += `<div class="uni-card" data-id="${esc(u.id)}">
      <div class="uni-cover">${uniImg(u, isFallback ? "fallback-svg" : "")}
        <span class="uni-badge">
          <button class="star-btn ${u.priority ? "on" : ""}" data-star="${esc(u.id)}" data-p="${u.priority}" title="关注度">${u.priority ? "★".repeat(u.priority) : "☆"}</button>
        </span>
        <span class="uni-city">${esc(u.city || "")}</span></div>
      <div class="uni-body">
        <h3>${esc(u.name)} <span class="muted" style="font-weight:400">${esc(u.short)}</span></h3>
        <div class="uni-meta">${esc(u.cs_school || "院系待补")}</div>
        <div class="uni-prog"><span style="width:${u.completeness}%"></span></div>
        <div class="uni-meta">资料完整度 <b>${u.completeness}%</b> · ${esc(u.data_status || "")}</div>
        <div class="uni-meta">${u.uses_408 === true ? '<span class="tag green">408</span>' : u.uses_408 === false ? '<span class="tag gray">非408</span>' : '<span class="tag amber">科目待核实</span>'}
          ${u.enrollment ? '<span class="tag">' + esc(u.enrollment) + ' 人(' + esc(u.enrollment_year || "?") + ')</span>' : ""}</div>
        <div class="img-note">图:${isFallback ? "本地生成占位(官方图核验中)" : esc(img.license || "")} ${img.source_page ? '· <a href="' + esc(img.source_page) + '" target="_blank" rel="noopener">来源</a>' : ""}</div>
        <div class="toolbar" style="margin:10px 0 0;gap:6px">
          <button data-edit="${esc(u.id)}">编辑资料</button>
          <button data-verify="${esc(u.id)}">标记已核验</button>
          ${u.official_site ? '<a class="btn" href="' + esc(u.official_site) + '" target="_blank" rel="noopener">官网 ↗</a>' : ""}
          <button class="again" data-del="${esc(u.id)}" style="margin-left:auto">删除</button></div>
      </div></div>`;
  }
  html += "</div><div id='uni-compare-box'></div>";
  host.innerHTML = html;
  typeset(host);

  $$("button[data-star]", host).forEach(b => b.onclick = async () => {
    const p = (+b.dataset.p + 1) % 4;
    await api("/universities/" + b.dataset.star, { method: "PUT", body: { priority: p } });
    renderSchools(host);
  });
  $$("button[data-edit]", host).forEach(b => b.onclick = () => uniForm(items.find(u => u.id === b.dataset.edit), host));
  $$("button[data-verify]", host).forEach(b => b.onclick = async () => {
    await api("/universities/" + b.dataset.verify + "/verify", { method: "POST", body: { result: "已人工核验" } });
    toast("已标记核验时间"); renderSchools(host);
  });
  $$("button[data-del]", host).forEach(b => b.onclick = async () => {
    if (!confirm("删除该院校及其资料?")) return;
    await api("/universities/" + b.dataset.del, { method: "DELETE" });
    renderSchools(host);
  });
  $("#uni-compare").onclick = () => {
    const rows = [["院校", "城市", "院系", "408", "招生人数", "复试线", "完整度", "核验"]];
    for (const u of starred) rows.push([
      u.name + " " + "★".repeat(u.priority), u.city || "—", u.cs_school || "—",
      u.uses_408 === true ? "是" : u.uses_408 === false ? "否" : "待核实",
      u.enrollment ? u.enrollment + "(" + (u.enrollment_year || "?") + ")" : "待核实",
      u.retest_line ? u.retest_line + "(" + (u.retest_line_year || "?") + ")" : "待核实",
      u.completeness + "%", (u.last_verified || "").slice(0, 10) || "未核验",
    ]);
    $("#uni-compare-box").innerHTML = '<div class="card" style="margin-top:16px"><h2>⚖️ 关注院校对比</h2>'
      + '<table class="data">' + rows.map((r, i) => "<tr>" + r.map(c =>
        (i === 0 ? "<th>" + esc(c) + "</th>" : "<td>" + esc(c) + "</td>")).join("") + "</tr>").join("") + "</table>"
      + '<p class="muted" style="margin:8px 0 0">「待核实」= 未核验官方数据,禁止当作事实依据。</p></div>';
  };
  $("#uni-add").onclick = () => {
    openModal(`<h2>添加院校</h2>
    <div class="form-grid">
      <div><label>校名</label><input id="nu-name" style="width:100%"></div>
      <div><label>城市</label><input id="nu-city" style="width:100%"></div>
      <div><label>官网</label><input id="nu-site" placeholder="https://..." style="width:100%"></div>
      <div><label>计算机学院名</label><input id="nu-cs" style="width:100%"></div>
    </div>
    <p><button class="primary" id="nu-save">保存(其余字段随后编辑)</button> <button onclick="closeModal()">取消</button></p>`);
    $("#nu-save").onclick = async () => {
      if (!$("#nu-name").value.trim()) return toast("校名必填");
      await api("/universities", { method: "POST", body: {
        name: $("#nu-name").value, city: $("#nu-city").value,
        official_site: $("#nu-site").value, cs_school: $("#nu-cs").value } });
      closeModal(); toast("已添加"); renderSchools(host);
    };
  };
  // ---- 官方招生分档录入(V2.0 模块一) ----
  const loadAdm = async () => {
    const uid = $("#adm-uni").value, year = $("#adm-year").value;
    const d = await api("/admission/records?uni_id=" + uid + "&year=" + year);
    const r = (d.items || [])[0];
    const u = items.find(x => x.id === uid);
    const f = $("#adm-form");
    if (!r) { f.innerHTML = '<span class="muted">无分档记录</span>'; return; }
    f.innerHTML = `<div class="form-grid" style="margin-top:6px">
      <div><label>专业名称(以当年目录为准)</label><input id="ad-mj" value="${esc(r.major_name || "")}" placeholder="官方未公开则留空"></div>
      <div><label>招生计划(人)</label><input id="ad-plan" type="number" value="${r.plan_total ?? ""}"></div>
      <div><label>推免人数(如有公开)</label><input id="ad-tm" type="number" value="${r.tuimian ?? ""}"></div>
      <div><label>统考招生(如有公开)</label><input id="ad-tk" type="number" value="${r.tongkao ?? ""}"></div>
      <div><label>是否 408</label><select id="ad-408"><option value="">官方未公开</option>
        <option value="true" ${r.uses_408 === true ? "selected" : ""}>是</option>
        <option value="false" ${r.uses_408 === false ? "selected" : ""}>否</option></select></div>
      <div><label>复试线(总分)</label><input id="ad-line" type="number" value="${r.retest_line ?? ""}"></div>
      <div style="grid-column:span 2"><label>复试科目</label><input id="ad-rsub" value="${esc(r.retest_subjects || "")}"></div>
      <div style="grid-column:span 2"><label>官方公告/目录链接</label><input id="ad-ann" value="${esc(r.announcement_url || u.official_site || "")}" placeholder="研招网或研究生院官网"></div>
      <div style="grid-column:span 2"><label>来源名称 *</label><input id="ad-srcn" value="${esc(r.source_name || "")}" placeholder="如:xx大学研究生院 2027 招生简章"></div>
      <div style="grid-column:span 2"><label>来源链接 *</label><input id="ad-srcu" value="${esc(r.source_url || "")}" placeholder="https://..."></div>
      <div style="grid-column:span 3"><label style="display:flex;gap:6px;align-items:center">
        <input type="checkbox" id="ad-verified"> 我已对照官方原文核验(标记为 S 级)</label></div></div>
    <div class="muted" style="font-size:12.5px;margin:6px 0">当前状态:${esc(r.data_status)} · 采集 ${esc((r.collected_at || "").slice(0, 10))} · 核验:${r.verified_at ? "已核验" : "未核验"} · ${r.year === 2028 ? "2028 官方尚未发布,历史数据不能冒充" : ""}</div>
    <button class="primary" id="ad-save">保存分档</button>`;
    $("#ad-save").onclick = async () => {
      const num = id => { const v = $("#" + id).value; return v === "" ? null : +v; };
      try {
        await api("/admission/records/" + r.id, { method: "PUT", body: JSON.stringify({
          major_name: $("#ad-mj").value, plan_total: num("ad-plan"),
          tuimian: num("ad-tm"), tongkao: num("ad-tk"),
          uses_408: $("#ad-408").value === "" ? null : $("#ad-408").value === "true",
          retest_line: num("ad-line"), retest_subjects: $("#ad-rsub").value,
          announcement_url: $("#ad-ann").value,
          source_name: $("#ad-srcn").value, source_url: $("#ad-srcu").value,
          mark_verified: $("#ad-verified").checked }) });
        toast("分档已保存(变更已留痕)"); loadAdm();
      } catch (e) { toast(e.message, "err"); }
    };
  };
  $("#adm-load").onclick = loadAdm;
}

function uniImg(u, extraCls) {
  const img = (u || {}).image || {};
  if (!img.file) return '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-3);font-size:28px">🏫</div>';
  return `<img src="${esc(img.file)}" alt="${esc(u.name)}" loading="lazy" class="${extraCls || ""}"
    onerror="this.style.display='none';this.parentNode.innerHTML='<div style=&quot;width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#8A93A0;font-size:28px&quot;>🏫</div>'">`;
}

function uniForm(u, host) {
  openModal(`<h2>编辑:${esc(u.name)}</h2>
    <p class="muted">招生数字必须同时填年份与来源;无法核实留空(显示「待核实」),禁止填估计值。</p>
    <div class="form-grid">
      <div><label>目标专业</label><input id="u-prog" value="${esc(u.program || "")}" style="width:100%"></div>
      <div><label>专业代码</label><input id="u-code" value="${esc(u.program_code || "")}" style="width:100%"></div>
      <div><label>学硕/专硕</label><select id="u-deg" style="width:100%">
        <option value="">(未定)</option>
        ${["学硕", "专硕"].map(d => `<option ${u.degree_type === d ? "selected" : ""}>${d}</option>`).join("")}</select></div>
      <div><label>初试科目(如 101,201,301,408)</label><input id="u-subj" value="${esc((u.exam_subjects || []).join(","))}" style="width:100%"></div>
      <div><label>是否 408</label><select id="u-408" style="width:100%">
        <option value="">待核实</option>
        <option value="true" ${u.uses_408 === true ? "selected" : ""}>是</option>
        <option value="false" ${u.uses_408 === false ? "selected" : ""}>否</option></select></div>
      <div><label>招生目录官方链接</label><input id="u-catalog" value="${esc(u.admission_catalog_url || "")}" placeholder="https://..." style="width:100%"></div>
      <div><label>复试办法链接</label><input id="u-retest" value="${esc(u.retest_rules_url || "")}" style="width:100%"></div>
      <div><label>历年录取信息链接</label><input id="u-history" value="${esc(u.history_admission_url || "")}" style="width:100%"></div>
      <div><label>招生人数(须同年份+来源)</label><input id="u-enr" type="number" value="${u.enrollment ?? ""}" style="width:100%"></div>
      <div><label>人数数据年份</label><input id="u-enry" placeholder="如 2025" value="${esc(u.enrollment_year || "")}" style="width:100%"></div>
      <div><label>复试线(须同年份+来源)</label><input id="u-line" value="${u.retest_line ?? ""}" style="width:100%"></div>
      <div><label>复试线年份</label><input id="u-liney" placeholder="如 2025" value="${esc(u.retest_line_year || "")}" style="width:100%"></div>
      <div><label>数据来源(招简/官网 URL 或名称)</label><input id="u-src" value="${esc(u.admission_source || "")}" style="width:100%"></div>
      <div><label>学费</label><input id="u-fee" value="${esc(u.tuition || "")}" style="width:100%"></div>
      <div><label>学制(年)</label><input id="u-dur" type="number" value="${u.duration_years ?? ""}" style="width:100%"></div>
      <div class="full"><label>院校介绍(依据官方)</label><textarea id="u-intro">${esc(u.intro || "")}</textarea></div>
      <div class="full"><label>备注/待核实项</label><textarea id="u-notes">${esc(u.notes || "")}</textarea></div>
    </div>
    <p><button class="primary" id="u-save">保存</button>
    <button id="u-goal">设为当前目标</button>
    <button onclick="closeModal()">取消</button></p>`);
  $("#u-save").onclick = async () => {
    const body = {
      program: $("#u-prog").value, program_code: $("#u-code").value,
      degree_type: $("#u-deg").value,
      exam_subjects: $("#u-subj").value.split(",").map(s => s.trim()).filter(Boolean),
      uses_408: $("#u-408").value === "" ? null : $("#u-408").value === "true",
      admission_catalog_url: $("#u-catalog").value, retest_rules_url: $("#u-retest").value,
      history_admission_url: $("#u-history").value,
      enrollment: $("#u-enr").value === "" ? null : +$("#u-enr").value,
      enrollment_year: $("#u-enry").value || null,
      retest_line: $("#u-line").value === "" ? null : $("#u-line").value,
      retest_line_year: $("#u-liney").value || null,
      admission_source: $("#u-src").value, tuition: $("#u-fee").value,
      duration_years: $("#u-dur").value === "" ? null : +$("#u-dur").value,
      intro: $("#u-intro").value, notes: $("#u-notes").value,
      data_status: "部分字段已填(" + new Date().toISOString().slice(0, 10) + ")",
    };
    try {
      await api("/universities/" + u.id, { method: "PUT", body });
      closeModal(); toast("已保存"); renderSchools(host);
    } catch (e) { toast(e.message); }
  };
  $("#u-goal").onclick = async () => {
    await api("/goals", { method: "PUT", body: {
      institution: u.name, program: u.program || "",
      official_links: [u.official_site, u.admission_catalog_url].filter(Boolean) } });
    toast("已设为当前目标(今日作战室将展示)"); closeModal();
  };
}

/* ================= 计划 ================= */
let planDate = todayStr();
ROUTES.plan = async () => {
  const [day, report, settings] = await Promise.all([
    api("/plan/day/" + planDate), api("/report/weekly/" + planDate), api("/settings"),
  ]);
  const d = new Date(planDate + "T00:00:00");
  let html = `<div class="page-head"><div>
    <div class="section-label">PLAN · ${planDate} 周${"日一二三四五六"[d.getDay()]}</div><h1>复习计划</h1></div>
    <div class="toolbar" style="margin:0">
      <button id="pl-prev">←</button><input type="date" id="pl-date" value="${planDate}"><button id="pl-next">→</button>
      <button class="primary" id="pl-gen">生成 / 刷新</button></div></div>
  <p class="section-desc">到期复习 → 薄弱专项 → 待验证 → 新知学习,装不下就少排。手动标记过的任务不会被覆盖。</p>
  <div class="card">${renderTaskList(day.tasks, true) || '<div class="state"><span>还没有任务,点击生成。</span></div>'}</div>`;
  html += `<div class="section-head"><div class="section-label">WEEKLY REPORT</div>
    <h2 class="section-title" style="font-size:22px">每周诊断(${esc(report.week_start)} ~ ${esc(report.week_end)})</h2></div>
  <div class="row2">
    <div class="card"><h2>① 本周学了什么 / ② 任务完成</h2>`;
  html += report.learned.length ? report.learned.map(l => `<div class="task"><span class="title">${esc(l.date)} ${esc(l.content)}</span></div>`).join("") : '<span class="muted">本周没有反思记录</span>';
  html += report.study_tasks.map(t => `<div class="task"><span class="tag gray">新知</span><span class="title">${esc(t.date)} ${esc(t.title)}</span></div>`).join("");
  html += `<p class="muted" style="margin:8px 0 0">任务:完成 ${report.tasks.done} · 跳过 ${report.tasks.skipped} · 未处理 ${report.tasks.pending}</p>
    <h2>⑨ 与上周对比</h2>
    <table class="data"><tr><th></th><th>做题量</th><th>正确率</th></tr>
    <tr><td>本周</td><td>${report.compare.this_week.total}</td><td>${report.compare.this_week.accuracy == null ? "—" : report.compare.this_week.accuracy + "%"}</td></tr>
    <tr><td>上周</td><td>${report.compare.last_week.total}</td><td>${report.compare.last_week.accuracy == null ? "—" : report.compare.last_week.accuracy + "%"}</td></tr></table></div>
    <div class="card"><h2>③④⑤ 练习与错误</h2><table class="data"><tr><th>科目</th><th>做题</th><th>正确率</th><th>用时</th></tr>`;
  const ps = report.per_subject;
  const keys = Object.keys(ps).length ? Object.keys(ps) : ["math", "cs408", "english"];
  for (const sub of keys) {
    const s = ps[sub] || {};
    html += `<tr><td><b>${SUBJECTS[sub] || sub}</b></td><td>${s.correct || 0}/${s.total || 0}</td>
      <td>${s.accuracy == null ? "—" : s.accuracy + "%"}</td><td>${s.minutes || 0} 分钟</td></tr>`;
  }
  html += `</table><p class="muted">错题复测 ${report.review.total} 次,又忘 ${report.review.again} 次</p>
    <h2>⑥ 优先薄弱点</h2>`;
  html += report.top_weak.length ? report.top_weak.map(w =>
    `<div class="wp-card"><b>${esc(w.name)}</b> <span class="tag ${WP_STATUS[w.status][1]}">${WP_STATUS[w.status][0]}</span>
     <div class="muted">${esc(w.judgment)}</div></div>`).join("")
    : '<span class="muted">暂无有数据支持的薄弱点</span>';
  html += `<h2>⑧ 证据不足的判断</h2>`;
  html += report.unverified_judgments.length
    ? report.unverified_judgments.map(w => `<div class="task"><span class="title">${esc(w.name)}</span><span class="tag amber">${WP_STATUS[w.status][0]}</span></div>`).join("")
    : '<span class="muted">无</span>';
  html += `</div></div>
  <div class="card"><h2>⑦ 下周建议</h2><ul style="margin:4px 0;padding-left:18px;font-size:13.5px">`
    + report.next_week_advice.map(a => "<li>" + esc(a) + "</li>").join("") + "</ul>";
  if (report.data_gaps.length) html += '<div class="hintbox" style="margin-bottom:0"><b>数据完整性提示:</b><br>' + report.data_gaps.map(g => "· " + esc(g)).join("<br>") + "</div>";
  html += "</div>";
  $("#view").innerHTML = html;
  typeset($("#view"));
  $("#pl-prev").onclick = () => { planDate = shiftDate(planDate, -1); ROUTES.plan(); };
  $("#pl-next").onclick = () => { planDate = shiftDate(planDate, 1); ROUTES.plan(); };
  $("#pl-date").onchange = e => { planDate = e.target.value; ROUTES.plan(); };
  $("#pl-gen").onclick = async () => {
    await api("/plan/generate", { method: "POST", body: { date: planDate } });
    toast("已生成"); ROUTES.plan();
  };
  bindTaskButtons(ROUTES.plan);
};

/* ================= 学习画像(独立页,从作战室/成长页跳转) ================= */
ROUTES.profile = async () => {
  const [prof, persona, mock] = await Promise.all([
    api("/profile"), api("/persona"), api("/mock-scores")]);
  let html = `<div class="page-head"><div>
    <div class="section-label">PROFILE · 个人画像与备考档案</div><h1>个人画像</h1></div>
    <span class="muted">学习结论全部附带证据;预测类内容与事实数据分开呈现</span></div>`;
  /* --- 考研档案(persona,可编辑) --- */
  html += `<div class="card"><h2>🎓 考研档案(决策模型输入,全部可改)</h2>
    <div class="row2" style="grid-template-columns:repeat(3,1fr)">
      <div><label>考研年份</label><input id="pf-year" type="number" min="2026" max="2030" value="${persona.exam_year || 2028}"></div>
      <div><label>本科院校</label><input id="pf-school" value="${esc(persona.bachelor_school || "")}"></div>
      <div><label>本科专业</label><input id="pf-major" value="${esc(persona.bachelor_major || "")}"></div>
      <div><label>方案</label><input id="pf-plan" value="${esc(persona.plan || "11408")}"></div>
      <div><label>英语</label><input id="pf-eng" value="${esc(persona.english || "英语一")}"></div>
      <div><label>目标地区(可空)</label><input id="pf-region" value="${esc(persona.target_region || "")}"></div>
    </div>
    <div style="margin-top:8px"><label>专业方向(逗号分隔)</label>
      <input id="pf-dirs" value="${esc((persona.directions || []).join(","))}"></div>
    <div class="toolbar" style="margin-top:10px"><button class="primary" id="pf-save">保存档案</button>
      <span class="muted">模型以当年官方招生目录为准;此处仅是决策输入</span></div></div>`;
  /* --- 月度模拟成绩(真实成绩录入) --- */
  const rows = mock.items || [];
  html += `<div class="card"><h2>📊 月度模拟成绩(决策模型只用真实成绩)</h2>
    <div class="toolbar" style="flex-wrap:wrap;gap:8px">
      <select id="ms-sub">${["math", "cs408", "english", "politics"].map(s => `<option value="${s}">${SUBJECTS[s]}</option>`).join("")}</select>
      <input id="ms-month" placeholder="2026-10" style="width:100px">
      <input id="ms-score" type="number" placeholder="分数" style="width:90px">
      <input id="ms-paper" placeholder="试卷名(选填)" style="width:160px">
      <button class="primary" id="ms-add">录入</button></div>
    ${rows.length ? `<table style="width:100%;font-size:13.5px"><tr>
        <th>月份</th><th>科目</th><th>成绩/满分</th><th>试卷</th><th></th></tr>
      ${rows.map(r => `<tr><td>${esc(r.month)}</td><td>${SUBJECTS[r.subject] || r.subject}</td>
        <td><b>${r.score}</b>/${r.full_mark}</td><td class="muted">${esc(r.paper || "")}</td>
        <td><button data-del="${r.id}" class="btn" style="padding:2px 8px">删</button></td></tr>`).join("")}
      </table>` : '<div class="muted" style="padding:10px 0">还没有模拟成绩。择校概率模型需要 ≥2 科的月度真实模拟成绩,系统不会用主观评价代替。</div>'}</div>`;
  html += `<div class="infobox">成绩趋势与录取概率见 <a href="#decision">智能择校 →</a></div>`;
  if (prof.stage) html += `<div class="infobox">当前阶段:<b>${esc(prof.stage)}</b>${prof.days_left != null ? " · 距考试 " + prof.days_left + " 天" : ""}</div>`;
  html += '<div class="row3">';
  for (const [sub, s] of Object.entries(prof.subjects)) {
    html += `<div class="card"><h2>${SUBJECTS[sub]}</h2>
      <div class="stat-num" style="font-size:26px">${s.progress_pct}%</div><div class="stat-label">${s.knowledge_total} 个知识点已启动</div>
      <div class="status-bar">${STATUS_ORDER.map(st => {
        const v = s.status_dist[st] || 0;
        return v ? `<span style="width:${s.knowledge_total ? v / s.knowledge_total * 100 : 0}%;background:${STATUS_COLOR[st]}"></span>` : "";
      }).join("")}</div>
      <div class="status-legend">${STATUS_ORDER.map(st => {
        const v = s.status_dist[st] || 0;
        return v ? `<span><i style="background:${STATUS_COLOR[st]}"></i>${STATUS_TXT[st]} ${v}</span>` : "";
      }).join("")}</div>
      <p class="muted" style="margin-bottom:0">做题 ${s.attempted} · 正确率 ${s.accuracy == null ? "—" : s.accuracy + "%"} · 错题 ${s.mistakes}</p></div>`;
  }
  html += "</div><div class='section-head'><div class='section-label'>WEAK POINTS</div><h2 class='section-title' style='font-size:22px'>薄弱点追踪</h2></div>";
  const wps = prof.weak_points || [];
  html += wps.length ? wps.map(w => {
    const st = WP_STATUS[w.status] || WP_STATUS.unverified;
    return `<div class="wp-card"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
      <b>${esc(w.name)}</b>
      <span><span class="tag ${SUBJECT_TAG[w.subject]}">${SUBJECTS[w.subject]}</span>
      <span class="tag ${st[1]}">${st[0]}</span>
      ${w.trend ? '<span class="tag gray">' + esc(w.trend) + "</span>" : ""}</span></div>
      <div style="font-size:13.5px;margin:4px 0">${esc(w.judgment)}</div>
      <div class="conf-track"><div class="conf-fill" style="width:${Math.round(w.confidence * 100)}%;background:${w.status === "confirmed" ? "var(--green)" : "var(--amber)"}"></div></div>
      <span class="muted">置信度 ${Math.round(w.confidence * 100)}%${w.retest.attempts ? " · 复测 " + w.retest.correct + "/" + w.retest.attempts : " · 尚无复测"}</span>
      ${w.evidence.slice(0, 3).map(e => '<div class="ev">' + esc(e.text) + "</div>").join("")}
      ${w.recommended_action ? '<div class="act">→ ' + esc(w.recommended_action) + "</div>" : ""}</div>`;
  }).join("") : '<div class="card state"><div class="big">🔍</div><b>暂无薄弱点判断</b><span>录入错题并完成复测后,这里会出现带证据的分析。</span></div>';
  html += `<div class="row2" style="margin-top:20px">
    <div class="card"><h2>高频错误模式(近 14 天)</h2>`;
  html += (prof.error_patterns || []).length
    ? prof.error_patterns.slice(0, 6).map(p => `<div class="task"><span class="title">${esc(p.reason)}</span><span class="tag amber">×${p.count}</span></div>`).join("")
    : '<span class="muted">暂无</span>';
  html += `</div><div class="card"><h2>近 14 天练习</h2>${trendChart(prof.trend_14d || [])}</div></div>`;
  if ((prof.data_gaps || []).length)
    html += '<div class="hintbox"><b>数据缺口(补上这些,画像会更准):</b><br>' + prof.data_gaps.map(g => "· " + esc(g)).join("<br>") + "</div>";
  $("#view").innerHTML = html;
  typeset($("#view"));
  // 档案与模拟成绩交互
  $("#pf-save").onclick = async () => {
    try {
      await api("/persona", { method: "PUT", body: JSON.stringify({
        exam_year: +$("#pf-year").value,
        bachelor_school: $("#pf-school").value, bachelor_major: $("#pf-major").value,
        plan: $("#pf-plan").value, english: $("#pf-eng").value,
        target_region: $("#pf-region").value,
        directions: $("#pf-dirs").value.split(",").map(s => s.trim()).filter(Boolean) }) });
      toast("档案已保存"); ROUTES.profile();
    } catch (e) { toast(e.message, "err"); }
  };
  $("#ms-add").onclick = async () => {
    try {
      await api("/mock-scores", { method: "POST", body: JSON.stringify({
        subject: $("#ms-sub").value, month: $("#ms-month").value.trim(),
        score: $("#ms-score").value, paper: $("#ms-paper").value }) });
      toast("已录入"); ROUTES.profile();
    } catch (e) { toast(e.message, "err"); }
  };
  $$("button[data-del]").forEach(b => b.onclick = async () => {
    try { await api("/mock-scores/" + b.dataset.del, { method: "DELETE" }); ROUTES.profile(); }
    catch (e) { toast(e.message, "err"); }
  });
};

function weekTrend(trend) {
  const days = trend.slice(-7);
  const max = Math.max(...days.map(t => t.total), 1);
  return `<svg width="100%" height="86" viewBox="0 0 320 86" preserveAspectRatio="none" role="img">
    ${days.map((t, i) => {
      const h = Math.round(t.total / max * 52);
      return `<rect x="${i * 44 + 8}" y="${60 - h}" width="28" height="${Math.max(h, 2)}" rx="4" fill="var(--navy-500)" opacity="${t.total ? 0.9 : 0.25}"><title>${t.date}:${t.total} 题</title></rect>
      <text x="${i * 44 + 22}" y="76" text-anchor="middle" font-size="9" fill="var(--text-3)">${t.date.slice(5)}</text>`;
    }).join("")}</svg>`;
}

function trendChart(trend) {
  if (!trend.length) return '<div class="muted">暂无记录</div>';
  const max = Math.max(...trend.map(t => t.total), 1);
  const W = 620, H = 148, bw = W / trend.length;
  let bars = "", labels = "";
  trend.forEach((t, i) => {
    const h = Math.round(t.total / max * 100);
    bars += `<rect class="bar" x="${i * bw + 5}" y="${110 - h}" width="${bw - 10}" height="${h}" rx="4"><title>${t.date}:${t.total} 题${t.accuracy != null ? ",正确率 " + t.accuracy + "%" : ""}</title></rect>`;
    if (i % 2 === 0) labels += `<text x="${i * bw + bw / 2}" y="128" text-anchor="middle">${t.date.slice(5)}</text>`;
  });
  return `<svg class="bar-chart" width="${W}" height="${H}" role="img">${bars}${labels}</svg>`;
}

/* ================= 智能择校(V2.0) ================= */
const TIER_TAG = { 冲刺: "red", 目标: "amber", 稳妥: "green", 保底: "gray" };
let decisionOpen = null;

ROUTES.decision = async () => {
  const [rec, persona] = await Promise.all([api("/decision/recommend"), api("/persona")]);
  let html = `<div class="page-head"><div>
    <div class="section-label">DECISION · 智能择校</div><h1>智能择校与录取评估</h1></div></div>
  <div class="infobox">${esc(rec.note)}。目标年份 <b>${persona.exam_year || 2028}</b>;
    概率模型只用官方历年数据与你的真实模拟成绩,数据不足时明确显示"预测不可靠"。</div>
  <div class="toolbar" style="margin:12px 0"><a class="btn" href="#profile">填写档案 / 录入模拟成绩 →</a>
    <a class="btn" href="#intel/schools">维护官方招生数据 →</a></div>
  <div id="dec-list">${rec.items.map((e, i) => {
    const m = e.match || {};
    return `<div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
        <b>${esc(e.name)}</b>
        <span>${e.tier ? `<span class="tag ${TIER_TAG[e.tier] || "gray"}">${e.tier}</span>` : '<span class="tag gray">未分层</span>'}
        <span class="score-pill" title="${esc((m.items || []).map(x => x.item + ":" + (x.points ?? "—")).join("; "))}">${m.score ?? "—"}<small>/100 匹配度</small></span></span></div>
      <div class="muted" style="font-size:12.5px;margin:4px 0">${esc(e.region || "")} · ${e.uses_408 === true ? "考408" : e.uses_408 === false ? "不考408" : "初试科目未公开"}
        ${Object.keys(e.line_years || {}).length ? " · 复试线 " + Object.entries(e.line_years).map(([y, v]) => y + ":" + v).join(" / ") : " · 官方复试线未采集"}</div>
      <div class="muted" style="font-size:12.5px">${esc(e.tier_note)}</div>
      <div class="hot-actions" style="margin-top:8px">
        <button data-p="${e.uni_id}" class="btn">📈 录取概率评估</button>
        <button data-m="${i}" class="btn">匹配度明细</button></div>
      <div id="pd-${e.uni_id}"></div>
      <div id="md-${i}" class="muted" style="font-size:12.5px;margin-top:6px;display:none">
        ${(m.items || []).map(x => `· ${esc(x.item)}:${x.points == null ? "无法评分" : x.points + " 分"} —— ${esc(x.why)}`).join("<br>")}</div>
    </div>`;
  }).join("")}</div>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  $$("button[data-m]").forEach(b => b.onclick = () => {
    const el = $("#md-" + b.dataset.m);
    el.style.display = el.style.display === "none" ? "block" : "none";
  });
  $$("button[data-p]").forEach(b => b.onclick = async () => {
    const box = $("#pd-" + b.dataset.p);
    if (decisionOpen === b.dataset.p) { box.innerHTML = ""; decisionOpen = null; return; }
    decisionOpen = b.dataset.p;
    box.innerHTML = '<span class="muted">模型计算中…</span>';
    const d = await api("/decision/probability/" + b.dataset.p);
    if (!d.ok) { box.innerHTML = `<div class="muted">${esc(d.error || "计算失败")}</div>`; return; }
    if (!d.reliable) {
      box.innerHTML = `<div class="infobox" style="border-left:3px solid var(--amber)">
        <b>预测不可靠</b> —— 系统不会编造概率。原因:<br>
        ${d.reasons.map(r => "· " + esc(r)).join("<br>")}
        <br><span class="muted">已覆盖数据:${(d.data_coverage.line_years || []).join("年,") || "无"}${d.data_coverage.mock_subjects ? " · 模拟科目 " + d.data_coverage.mock_subjects + " 科" : ""}</span></div>`;
      return;
    }
    box.innerHTML = `<div class="infobox" style="border-left:3px solid var(--gold)">
      <div style="display:flex;gap:18px;flex-wrap:wrap;font-size:15px">
        <span>进入复试 <b>${Math.round(d.p_pass_line * 100)}%</b></span>
        <span>复试通过(假设) <b>${Math.round(d.p_final_given_pass * 100)}%</b></span>
        <span>最终录取 <b class="h1-accent">${Math.round(d.p_final * 100)}%</b></span>
        <span>置信度 <b>${esc(d.confidence)}</b></span></div>
      <div style="margin-top:6px">成绩估计 ${d.score_estimate.total}±${d.score_estimate.sigma}
        (基于 ${d.score_estimate.based_on_subjects} 科真实模拟) · ${esc(d.targets.suggest)}</div>
      <div style="margin-top:6px">三情景录取概率:${Object.entries(d.scenario_probability).map(([k, v]) => k + " " + Math.round(v * 100) + "%").join(" · ")}</div>
      <details style="margin-top:6px"><summary class="muted" style="cursor:pointer">模型假设与数据覆盖</summary>
        <div class="muted" style="font-size:12.5px;margin-top:4px">
          数据覆盖:复试线年份 ${(d.data_coverage.line_years || []).join("、")};模拟成绩 ${d.data_coverage.mock_count} 条<br>
          ${d.assumptions.map(a => "· " + esc(a)).join("<br>")}
          <br>${esc(d.note)}</div></details></div>`;
  });
};

/* ================= 个人中心 ================= */
ROUTES.account = async () => {
  const [acc, settings, lan] = await Promise.all([
    api("/account"), api("/settings"), api("/lan"),
  ]);
  const ai = settings.ai || {};
  const aiStatus = await api("/ai/status");
  let html = `<div class="page-head"><div>
    <div class="section-label">PERSONAL</div><h1>个人中心</h1></div>
    <button id="logout-btn">退出登录</button></div>
  <div class="row2">
    <div class="card"><h2>👤 账号</h2>
      <p style="margin:0 0 4px"><b>${esc(acc.display_name)}</b> <span class="muted">(@${esc(acc.username)} · 建于 ${esc((acc.created || "").slice(0, 10))})</span></p>
      <label>显示名</label><input id="acc-name" value="${esc(acc.display_name)}" style="width:100%">
      <label>激励风格</label><select id="acc-style" style="width:100%">
        ${[["rational", "理性教练 —— 用证据和数字说话"], ["gentle", "温和陪伴 —— 累了就休息,马拉松心态"], ["sprint", "高强度冲刺 —— 提醒你保持节奏"]]
          .map(([v, n]) => `<option value="${v}" ${acc.motivation_style === v ? "selected" : ""}>${n}</option>`).join("")}</select>
      <label>每日训练题量(共 <span id="dq-total"></span> 题/天)</label>
      <div class="toolbar" style="gap:6px">${["math", "cs408", "english", "politics"].map(sub =>
        `<label style="margin:0">${SUBJECTS[sub]}<input type="number" min="0" max="50" data-quota="${sub}"
          value="${((settings.daily_train || {}).quotas || {})[sub] ?? 5}" style="width:56px"></label>`).join("")}
        <button id="dq-save">保存题量</button></div>
      <label>各科当前水平(自评,供教练参考)</label>
      <div class="toolbar" style="gap:6px">${["math", "cs408", "english", "politics"].map(sub =>
        `<label style="margin:0">${SUBJECTS[sub]}<select data-level="${sub}">
        ${["未开始", "基础薄弱", "中等", "熟练"].map((l, i) =>
          `<option value="${i}" ${((settings.subjects[sub] || {}).level || 0) === i ? "selected" : ""}>${l}</option>`).join("")}
        </select></label>`).join("")}</div>
      <label>修改密码</label>
      <div class="toolbar"><input id="pw-old" type="password" placeholder="原密码" style="flex:1;min-width:120px">
      <input id="pw-new" type="password" placeholder="新密码(≥8位)" style="flex:1;min-width:120px">
      <button id="pw-save">修改</button></div>
      <div class="toolbar" style="margin-top:10px"><button class="primary" id="acc-save">保存偏好</button></div>
      <h2>🔐 审计日志(最近)</h2>
      <div id="audit-list" class="muted">加载中…</div></div>
    <div><div class="card"><h2>🎯 考试信息(确认后再填)</h2>
      <div class="form-grid">
        <div><label>考试年份</label><input id="e-year" value="${esc(settings.exam_year || "")}" style="width:100%"></div>
        <div><label>考试日期</label><input id="e-date" type="date" value="${esc(settings.exam_date || "")}" style="width:100%"></div>
        <div><label>目标院校</label><input id="e-school" value="${esc(settings.target_school || "")}" style="width:100%"></div>
        <div><label>数学类型</label><select id="e-math" style="width:100%">
          <option value="">(未定)</option><option value="数一" ${settings.math_type === "数一" ? "selected" : ""}>数一</option>
          <option value="数二" ${settings.math_type === "数二" ? "selected" : ""}>数二</option></select></div>
      </div>
      <p><button class="primary" id="e-save">保存</button></p>
      <p class="muted" style="margin-bottom:0">也可在「情报站 → 梦校」中维护候选院校并设为当前目标。</p></div>
    <div class="card"><h2>🤖 AI 模型(本地 Ollama 默认)</h2>
      <div class="toolbar"><span class="tag ${aiStatus.service_ok ? "green" : "red"}">${aiStatus.service_ok ? "Ollama 运行中" : "Ollama 未运行"}</span>
      ${aiStatus.available ? '<span class="tag green">已就绪 · ' + esc(aiStatus.model) + "</span>" : '<span class="tag amber">未选择模型</span>'}</div>
      <div class="form-grid">
        <div><label>主模型</label><select id="ai-model" style="width:100%"></select></div>
        <div><label>视觉模型</label><select id="ai-vmodel" style="width:100%"></select></div>
      </div>
      <div class="toolbar" style="margin-top:8px"><button id="ai-save" class="primary">保存 AI 配置</button>
      <button id="ai-test">测试连接</button><span id="ai-test-result" class="muted"></span></div>
      <p class="muted" style="margin-bottom:0">云端 API 可选:如需切换,手动编辑 data/settings.json 中 ai.mode="cloud"。</p></div>
    <div class="card"><h2>📵 局域网访问</h2>
      <div id="lan-info" class="muted">读取中…</div>
      <div class="toolbar" style="margin-top:8px"><input id="ac-code" type="password" placeholder="新访问密码(可选)" style="flex:1;min-width:120px">
      <button id="ac-save">设密码</button><button id="ac-clear">清除</button></div>
      <p class="muted" style="margin-bottom:0">手机访问:${lan.lan_url ? "<a href='" + esc(lan.lan_url) + "'><b>" + esc(lan.lan_url) + "</b></a>" : "(未检测到)"}</p></div>
    <div class="card"><h2>🗄 数据与隐私</h2>
      <div class="toolbar"><button id="bk-now">立即备份</button>
      <button data-exp="all">导出全量 zip</button>
      <button data-exp="mistakes">导出错题 MD</button>
      <button data-exp="records">导出练习 CSV</button></div>
      <p class="muted">数据在 data/(含图片),backups/ 自动备份;导出在 exports/。</p>
      <button id="data-del" class="again">删除全部学习数据</button>
      <span class="muted">(保留账号;需二次确认)</span></div></div></div>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  // AI 模型下拉
  const mSel = $("#ai-model"), vSel = $("#ai-vmodel");
  const models = aiStatus.models || [];
  if (models.length) {
    mSel.innerHTML = '<option value="">(不使用)</option>' + models.map(m =>
      `<option value="${esc(m.name)}" ${aiStatus.model === m.name ? "selected" : ""}>${esc(m.name)}${m.vision ? " [视觉]" : ""}</option>`).join("");
    const vs = models.filter(m => m.vision);
    vSel.innerHTML = '<option value="">(不使用)</option>' + (vs.length ? vs : models).map(m =>
      `<option value="${esc(m.name)}" ${aiStatus.vision_model === m.name ? "selected" : ""}>${esc(m.name)}</option>`).join("");
  } else { mSel.innerHTML = "<option>(无本地模型)</option>"; vSel.innerHTML = "<option>(无)</option>"; }
  $("#ai-save").onclick = async () => {
    await api("/settings", { method: "PUT", body: { ai: {
      mode: "local", model: $("#ai-model").value, vision_model: $("#ai-vmodel").value } } });
    toast("已保存"); ROUTES.account();
  };
  $("#ai-test").onclick = async () => {
    $("#ai-test-result").textContent = "测试中…";
    try {
      const r = await api("/settings/ai/test", { method: "POST" });
      $("#ai-test-result").innerHTML = r.ok
        ? '<span style="color:var(--green)">✓ ' + esc(r.sample || "OK") + "</span>"
        : '<span style="color:var(--red)">✗ ' + esc(r.error) + "</span>";
    } catch (e) { $("#ai-test-result").textContent = "✗ " + e.message; }
  };
  // 审计
  api("/account/audit").then(events => {
    $("#audit-list").innerHTML = events.length
      ? events.slice(0, 10).map(e => `<div class="task"><span class="title">${esc(e.time)} · ${esc(e.event)}</span></div>`).join("")
      : "暂无记录";
  });
  const dqTotal = () => { $("#dq-total").textContent =
    $$("input[data-quota]").reduce((a, i) => a + (+i.value || 0), 0); };
  $$("input[data-quota]").forEach(i => i.oninput = dqTotal); dqTotal();
  $("#dq-save").onclick = async () => {
    const quotas = {};
    $$("input[data-quota]").forEach(i => quotas[i.dataset.quota] = +i.value || 0);
    try {
      await api("/train/settings", { method: "PUT", body: { quotas } });
      toast("每日训练题量已保存(明天生效,或点「换一批」立即重抽)");
    } catch (e) { toast(e.message); }
  };
  $("#acc-save").onclick = async () => {
    await api("/account", { method: "PUT", body: {
      display_name: $("#acc-name").value, motivation_style: $("#acc-style").value } });
    const subjects = {};
    $$("select[data-level]").forEach(sel => {
      const sub = sel.dataset.level;
      subjects[sub] = { ...(settings.subjects[sub] || {}),
        level: +sel.value };
    });
    await api("/settings", { method: "PUT", body: { subjects: {
      ...settings.subjects, ...subjects } } });
    toast("已保存(含各科水平)");
  };
  $("#pw-save").onclick = async () => {
    try {
      await api("/account/password", { method: "POST", body: {
        old_password: $("#pw-old").value, new_password: $("#pw-new").value } });
      toast("密码已修改,请重新登录");
      location.hash = "#login"; navigate();
    } catch (e) { toast(e.message); }
  };
  $("#logout-btn").onclick = async () => {
    await api("/logout", { method: "POST" });
    location.hash = "#login"; navigate();
  };
  $("#e-save").onclick = async () => {
    await api("/settings", { method: "PUT", body: {
      exam_year: $("#e-year").value || null, exam_date: $("#e-date").value || null,
      target_school: $("#e-school").value || null, math_type: $("#e-math").value || null } });
    toast("已保存");
  };
  api("/lan").then(l => {
    $("#lan-info").innerHTML = l.lan_url
      ? `手机访问:<a href="${esc(l.lan_url)}"><b>${esc(l.lan_url)}</b></a> · ${l.protected ? "已设密码" : "未设密码"}`
      : "未检测到局域网地址";
  });
  $("#ac-save").onclick = async () => {
    const v = $("#ac-code").value.trim();
    if (!v) return toast("输入新密码");
    await api("/settings", { method: "PUT", body: { access_code: v } });
    toast("访问密码已设置"); ROUTES.account();
  };
  $("#ac-clear").onclick = async () => {
    await api("/settings", { method: "PUT", body: { access_code: "" } });
    toast("已清除"); ROUTES.account();
  };
  $("#bk-now").onclick = async () => { const r = await api("/backup", { method: "POST" }); toast("已备份:" + r.path); };
  $$("button[data-exp]").forEach(b => b.onclick = async () => {
    const r = await api("/export/" + b.dataset.exp);
    toast("已导出:" + r.file);
  });
  $("#data-del").onclick = async () => {
    if (!confirm("将删除全部错题/记录/反思/对话/计划(保留账号),不可恢复。确定?")) return;
    const second = prompt("此操作不可逆。输入 DELETE 确认:");
    if (second !== "DELETE") return toast("已取消");
    await api("/account/delete-data", { method: "POST", body: { confirm: "DELETE" } });
    toast("学习数据已清空"); ROUTES.account();
  };
};

/* ================= 启动 ================= */
window.addEventListener("load", () => {
  try {
    if ("serviceWorker" in navigator &&
        (location.protocol === "https:" ||
         ["localhost", "127.0.0.1"].includes(location.hostname))) {
      navigator.serviceWorker.register("/static/sw.js").catch(() => {});
    }
  } catch (e) { /* 忽略 */ }
  window.addEventListener("offline", () => $("#offline-banner").classList.add("show"));
  window.addEventListener("online", () => $("#offline-banner").classList.remove("show"));
  applyThemeToggle();
  const start = () => { if (!navigate._bound) { navigate._bound = 1; navigate(); } };
  if (window.renderMathInElement) start();
  else setTimeout(start, 300);
});

// MARKER-test-12345