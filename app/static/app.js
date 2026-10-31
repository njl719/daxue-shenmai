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
}
window.addEventListener("hashchange", navigate);

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
  const [persona, plan, brief] = await Promise.all([
    api("/persona"), api("/plan/day/" + todayStr()), api("/radar/home")]);
  const daysLeft = persona.exam_phase_days;
  const doneToday = (plan.tasks || []).filter(t => t.status === "done").length;
  const pct = plan.tasks.length ? Math.round(100 * doneToday / plan.tasks.length) : 0;
  let html = `<section class="hero">
    <div class="hero-badge"><span class="dot"></span>${persona.exam_year || 2028} 考研 · 11408 方案
      ${daysLeft != null ? " · 距考约 <b>" + daysLeft + "</b> 天" : ""}</div>
    <h1>${pct >= 80 ? "今天的状态很好,继续保持" : "先把今日计划推进完"}</h1>
    <p class="hero-desc">计划完成率 <b>${pct}%</b>(${doneToday}/${plan.tasks.length})
      ${brief && brief.found ? " · 最新动态:<a href='#intel/hot'>" + esc(brief.found.title.slice(0, 24)) + "…</a>" : ""}</p>
    <div class="hero-actions">
      <a class="hero-cta" href="#decision">🎯 智能择校</a>
      <a class="hero-ghost" href="#exp">📰 经验贴</a>
      <a class="hero-ghost" href="#plan">今日计划</a>
      <a class="hero-ghost" href="#intel/schools">院校库</a>
    </div></section>
  <div class="stats-band stagger">
    <div class="stat-cell"><div class="stat-num">${pct}<span style="font-size:14px">%</span></div>
      <div class="stat-label">今日计划完成率</div></div>
    <div class="stat-cell"><div class="stat-num">${daysLeft != null ? daysLeft : "—"}</div>
      <div class="stat-label">距考天数(${persona.exam_year || 2028})</div></div>

    <div class="stat-cell"><div class="stat-num">${persona.directions ? persona.directions.length : 0}</div>
      <div class="stat-label">目标方向</div></div>
    <div class="stat-cell"><div class="stat-num">${(brief.top || {}).items ? brief.top.items.length : 0}</div>
      <div class="stat-label">近期情报条数</div></div></div>
  <section class="radar-zone" id="home-radar"><div class="section-label">RADAR · 今日考研雷达</div>
    <div class="muted" style="margin:8px 0 14px">重要提醒与近期动态,全部来自公开检索与官方公告;<a href="#intel/hot">进入考研热点 →</a></div>
    <div class="radar-grid" id="radar-cards"><div class="muted">雷达加载中…</div></div></section>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  renderHomeRadar();
};

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
let growthTab = "timeline";
ROUTES.growth = async (sub) => {
  if (sub) growthTab = sub;
  const names = { timeline: "时间线与热力图", milestones: "里程碑" };
  let html = `<div class="page-head"><div>
    <div class="section-label">GROWTH</div><h1>成长记录</h1></div></div>
  <div class="tabs">${Object.entries(names).map(([k, n]) =>
    `<button data-t="${k}" ${growthTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="growth-body"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  $$(".tabs button").forEach(b => b.onclick = () => { growthTab = b.dataset.t; ROUTES.growth(growthTab); });
  const body = $("#growth-body");
  if (growthTab === "motivation") { location.hash = "#exp"; return; }
  if (growthTab === "timeline") await renderTimeline(body);
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
let intelTab = "hot";
ROUTES.intel = async (sub) => {
  if (sub) intelTab = sub;
  const names = { hot: "考研热点", sources: "来源与数据源", schools: "院校库", quality: "数据质量" };
  let html = `<div class="page-head"><div>
    <div class="section-label">INTELLIGENCE</div><h1>考研情报站</h1></div></div>
  <div class="tabs">${Object.entries(names).map(([k, n]) =>
    `<button data-t="${k}" ${intelTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="intel-body"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  $$(".tabs button").forEach(b => b.onclick = () => { intelTab = b.dataset.t; ROUTES.intel(intelTab); });
  const body = $("#intel-body");
  if (intelTab === "sources") await renderSources(body);
  else if (intelTab === "quality") await renderQuality(body);
  else if (intelTab === "hot") await renderHot(body);
  else await renderSchools(body);
};

/* ================= 经验贴(V2.0 核心模块) ================= */
const EXP_TABS = [
  ["all", "全部"], ["985", "985上岸"], ["211", "211上岸"], ["regular", "普通本科逆袭"],
  ["cs", "计算机考研"], ["plan11408", "11408备考"], ["math1", "数学一"], ["e408", "408"],
  ["english1", "英语一"], ["choose", "择校与专业"], ["retest", "复试与调剂"],
  ["fail", "失败复盘避坑"], ["habit", "长期备考自律"],
];
function expMatch(item, tab) {
  const t = (item.title || "") + " " + (item.summary || "");
  if (tab === "all") return true;
  if (tab === "985") return /985|清华|北大|复旦|上海交通|浙江大学|南京大学|中科大|哈工大|华中科技/.test(t);
  if (tab === "211") return /211|北邮|西电|华东理工|南京理工|华中师范|苏州大学/.test(t);
  if (tab === "regular") return /普通本科|双非|二本|三本|逆袭/.test(t);
  if (tab === "cs") return /计算机|408|cs|编程|软件工程/.test(t) || item.subject === "cs408";
  if (tab === "plan11408") return /11408|数学一.{0,6}英语一|数一.{0,6}408/.test(t);
  if (tab === "math1") return /数学一|数一|高数|考研数学/.test(t) || item.subject === "math";
  if (tab === "e408") return item.subject === "cs408" || /408/.test(t);
  if (tab === "english1") return /英语一|阅读|作文模板|长难句/.test(t) || item.subject === "english";
  if (tab === "choose") return item.category === "choose" || /择校|选学校|报录比/.test(t);
  if (tab === "retest") return /复试|调剂|面试/.test(t);
  if (tab === "fail") return item.category === "fail" || /失败|没考上|落榜|后悔|避坑/.test(t);
  if (tab === "habit") return /自律|长期|坚持|习惯|作息/.test(t);
  return true;
}
let expTab = "all", expBucket = "30", expQ = "";

ROUTES.exp = async () => {
  let html = `<div class="page-head"><div>
    <div class="section-label">EXPERIENCE · 经验贴</div><h1>经验贴</h1></div></div>
  <div class="infobox">全部条目来自公开检索的真实帖子(带原文链接与可信度标记);
    AI/规则拆解仅基于摘要,不编造作者与结果。抖音/小红书无合规公开接口,走搜索引擎站点索引,来源不可用时如实显示。</div>
  <div class="toolbar" style="flex-wrap:wrap;gap:8px">
    <input id="exp-q" placeholder="搜索标题/摘要" value="${esc(expQ)}" style="flex:1;min-width:180px">
    <select id="exp-bucket">${[["7", "最近 7 天"], ["30", "最近 30 天"], ["90", "最近 90 天"], ["annual", "一年内"], ["all", "全部时间"]].map(([v, n]) =>
      `<option value="${v}" ${expBucket === v ? "selected" : ""}>${n}</option>`).join("")}</select>
    <button class="primary" id="exp-refresh">⟳ 更新</button>
    <span class="muted" id="exp-status"></span></div>
  <div class="tabs" id="exp-tabs">${EXP_TABS.map(([k, n]) =>
    `<button data-t="${k}" ${expTab === k ? 'class="on"' : ""}>${n}</button>`).join("")}</div>
  <div id="exp-quote"></div>
  <div id="exp-list"><div class="muted">加载中…</div></div>`;
  $("#view").innerHTML = html;
  typeset($("#view"));
  api("/motivation/daily").then(d => {
    const el = $("#exp-quote");
    if (el && d.quote) el.innerHTML = `<div class="card" style="border-left:3px solid var(--gold);margin-bottom:12px">
      <b>今日一句</b> <span class="tag gray">${esc(d.quote.author || "")}</span>
      <span class="tag ${/待核验/.test(d.quote.license || d.quote.source || "") ? "amber" : "green"}">${esc(d.quote.license || d.quote.source || "")}</span>
      <div style="margin-top:6px;font-size:15px">${esc(d.quote.text)}</div></div>`;
  }).catch(() => {});
  const load = async () => {
    const p = new URLSearchParams();
    if (expBucket !== "all") p.set("bucket", expBucket);
    if (expQ) p.set("q", expQ);
    const d = await api("/radar?" + p.toString());
    radarCats = d.categories || {}; radarLevs = d.levels || {};
    $("#exp-status").textContent = d.status.last_success
      ? "上次更新 " + d.status.last_success.replace("T", " ").slice(0, 16)
      : "尚未检索过";
    const items = d.items.filter(i => !i.ctype || !["expired"].includes(i.ctype)).filter(i => expMatch(i, expTab));
    $("#exp-list").innerHTML = items.length ? items.map(i => {
      const lv = radarLevs[i.source_level] || "来源未定";
      return `<div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;gap:10px">
        <b><a href="${esc(i.url)}" target="_blank" rel="noopener" style="color:var(--text);text-decoration:none">${esc(i.title)}</a></b>
        <span class="score-pill" title="可信度等级">${esc(radarLevs[i.source_level] || "来源未定")}</span></div>
      <div class="muted" style="font-size:13px;margin:6px 0">${esc(i.summary || "(无摘要)")}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <span class="tag gray">${esc(i.platform)}</span>
        ${i.author ? `<span class="tag gray">${esc(i.author)}</span>` : ""}
        <span class="tag ${i.published_at ? "gray" : "amber"}">${i.published_at ? "发布 " + esc(i.published_at) : "日期未核验"}</span>
        <span class="tag gray">抓取 ${esc((i.fetched_at || "").slice(0, 10))}</span>
        ${i.category && radarCats[i.category] ? `<span class="tag blue">${esc(radarCats[i.category])}</span>` : ""}</div>
      <div class="hot-actions">
        <button data-a="open" data-u="${esc(i.url)}" class="btn">原文 ↗</button>
        <button data-a="ai" data-id="${i.id}" class="btn">🧠 拆解</button>
        <button data-a="favorite" data-id="${i.id}" class="btn">${i.favorite ? "★ 已藏" : "☆ 收藏"}</button>
        <button data-a="hide" data-id="${i.id}" class="btn">🚫 不感兴趣</button></div>
      <div class="exp-detail" id="ed-${i.id}"></div></div>`;
    }).join("") : `<div class="card"><div class="muted" style="padding:18px;text-align:center">该筛选下暂无内容 —— 点「⟳ 更新」检索,或换个分类。来源不可用时系统如实显示,不用虚构内容填充。</div></div>`;
    $$("#exp-list button[data-a]").forEach(b => b.onclick = async () => {
      const a = b.dataset.a, id = b.dataset.id;
      if (a === "open") return window.open(b.dataset.u, "_blank");
      if (a === "ai") {
        b.disabled = true; b.textContent = "拆解中…";
        try {
          const d = await api("/radar/analyze/" + id);
          const gen = d.generator === "ai" ? `<span class="tag blue">AI 拆解(${esc(d.model)})</span>` : '<span class="tag gray">规则提炼(AI 未配置)</span>';
          $("#ed-" + id).innerHTML = `<div class="infobox" style="margin-top:8px">
            <div><b>方法:</b>${esc(d.method)}</div>
            <div><b>背景:</b>${esc(d.background)}</div>
            <div><b>适用:</b>${esc(d.audience)}</div>
            <div><b>局限:</b>${esc(d.limits)}</div>
            <div style="margin-top:4px">${gen} <a href="${esc(d.url)}" target="_blank" rel="noopener">查看原文 →</a></div></div>`;
          b.textContent = "拆解"; b.disabled = false;
        } catch (e) { toast(e.message, "err"); b.disabled = false; b.textContent = "拆解"; }
        return;
      }
      try {
        await api("/radar/feedback", { method: "POST", body: JSON.stringify({ id, action: a }) });
        toast(a === "favorite" ? "已收藏" : "已记录"); load();
      } catch (e) { toast(e.message, "err"); }
    });
  };
  $("#exp-refresh").onclick = async () => {
    const b = $("#exp-refresh");
    b.disabled = true; b.textContent = "检索中…";
    try { const r = await api("/radar/refresh", { method: "POST" });
      toast(r.ok ? `新增 ${r.stats.added} 条` : "检索失败:" + (r.failure_reason || "网络不可用"), r.ok ? "ok" : "err");
    } catch (e) { toast(e.message, "err"); }
    b.disabled = false; b.textContent = "⟳ 更新";
    load();
  };
  $("#exp-bucket").onchange = e => { expBucket = e.target.value; load(); };
  $("#exp-q").onchange = e => { expQ = e.target.value.trim(); load(); };
  $$("#exp-tabs button").forEach(b => b.onclick = () => {
    expTab = b.dataset.t;
    $$("#exp-tabs button").forEach(x => x.classList.toggle("on", x === b));
    load();
  });
  await load();
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
  const aiStatus = { base_url: (ai.base_url || ""), model: (ai.model || ""),
    has_key: !!ai.api_key,
    available: !!(ai.api_key && ai.base_url && ai.model) };
  let html = `<div class="page-head"><div>
    <div class="section-label">PERSONAL</div><h1>个人中心</h1></div>
    <button id="logout-btn">退出登录</button></div>
  <div class="row2">
    <div class="card"><h2>👤 账号</h2>
      <p style="margin:0 0 4px"><b>${esc(acc.display_name)}</b> <span class="muted">(@${esc(acc.username)} · 建于 ${esc((acc.created || "").slice(0, 10))})</span></p>
      <label>显示名</label><input id="acc-name" value="${esc(acc.display_name)}" style="width:100%">
      <label>修改密码</label>
      <div class="toolbar"><input id="pw-old" type="password" placeholder="原密码" style="flex:1;min-width:120px">
      <input id="pw-new" type="password" placeholder="新密码(≥8位)" style="flex:1;min-width:120px">
      <button id="pw-save">修改</button></div>
      <div class="toolbar" style="margin-top:10px"><button class="primary" id="acc-save">保存显示名</button></div>
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
    <div class="card"><h2>🤖 AI(云端接口,可选)</h2>
      <div class="toolbar">${aiStatus.available ? '<span class="tag green">已配置 · ' + esc(aiStatus.model) + "</span>" : '<span class="tag amber">未配置 —— 全部功能走规则解析,基础能力不受影响</span>'}</div>
      <div class="form-grid">
        <div><label>Base URL(OpenAI 兼容)</label><input id="ai-base" value="${esc(aiStatus.base_url || "")}" placeholder="https://api.openai.com/v1" style="width:100%"></div>
        <div><label>模型名</label><input id="ai-model" value="${esc(aiStatus.model || "")}" placeholder="gpt-4o-mini / glm-4-flash / deepseek-chat" style="width:100%"></div>
        <div style="grid-column:span 2"><label>API Key(留空不修改已存 Key)</label><input id="ai-key" type="password" placeholder="${aiStatus.has_key ? "已保存,留空保持不变" : "sk-..."}" style="width:100%"></div>
      </div>
      <div class="toolbar" style="margin-top:8px"><button id="ai-save" class="primary">保存 AI 配置</button>
      <button id="ai-test">测试连接</button><span id="ai-test-result" class="muted"></span></div>
      <p class="muted" style="margin-bottom:0">不配置也完全可用;经验贴拆解等 AI 能力会显示"规则提炼"。本平台不再使用本地 Ollama。</p></div>
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
  // 云端 AI 配置
  $("#ai-save").onclick = async () => {
    const body = { ai: {
      base_url: $("#ai-base").value.trim(), model: $("#ai-model").value.trim() } };
    if ($("#ai-key").value.trim()) body.ai.api_key = $("#ai-key").value.trim();
    await api("/settings", { method: "PUT", body });
    toast("已保存"); ROUTES.account();
  };
  $("#ai-test").onclick = async () => {
    $("#ai-test-result").textContent = "测试中…";
    try {
      const r = await api("/settings/ai/test", { method: "POST" });
      $("#ai-test-result").innerHTML = r.ok
        ? '<span style="color:var(--green)">✓ ' + esc(r.reply || "OK") + "</span>"
        : '<span style="color:var(--red)">✗ ' + esc(r.error) + "</span>";
    } catch (e) { $("#ai-test-result").textContent = "✗ " + e.message; }
  };
  // 审计
  api("/account/audit").then(events => {
    $("#audit-list").innerHTML = events.length
      ? events.slice(0, 10).map(e => `<div class="task"><span class="title">${esc(e.time)} · ${esc(e.event)}</span></div>`).join("")
      : "暂无记录";
  });
  $("#acc-save").onclick = async () => {
    try {
      await api("/account", { method: "PUT", body: {
        display_name: $("#acc-name").value } });
      toast("已保存"); ROUTES.account();
    } catch (e) { toast(e.message, "err"); }
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