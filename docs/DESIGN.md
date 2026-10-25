# 个人考研复习平台 · 系统设计

> 版本:v0.1 MVP(2026-10-24)
> 目标:本地运行、数据自持、可长期记录学习效果并辅助复习的个人系统。

## 1. 设计原则

1. **本地优先**:所有数据以 JSON/Markdown 文件存放在 `data/` 目录,不依赖任何在线服务,不上传任何学习数据。
2. **数据可迁移**:所有核心数据可一键导出为 Markdown / CSV / zip 包,离开本系统仍可读。
3. **记录优于生成**:系统不凭空生成题目和"权威答案"。练习任务来自你自己录入的错题与标注薄弱的知识点;答案与解析必须来自你提供的教材/真题来源,并要求填写 `source`(依据)字段。AI 生成的任何内容默认标记,可核验、可删除。
4. **计划服务于人**:计划引擎只在你给定的每日时间内排任务,不无限加量;所有任务可手动跳过、顺延、标记完成。
5. **未确认不锁定**:目标院校、考试科目(数一/数二)、考试年份未确认前,系统只提供骨架与占位配置,不生成"锁定版"计划。

## 2. 技术架构

```
┌─────────────────────────────────────────────┐
│  浏览器 (单页应用, 纯 HTML/JS/CSS)             │
│  - KaTeX 本地化渲染 LaTeX                     │
│  - 自带轻量 Markdown 渲染器                    │
│  - hash 路由: 仪表盘/知识库/错题/练习/统计/计划  │
└──────────────────┬──────────────────────────┘
                   │ HTTP 127.0.0.1:8321 (仅本机)
┌──────────────────▼──────────────────────────┐
│  Flask 后端 (app/server.py)                   │
│  ├─ storage.py   JSON 文件存储(原子写+备份)    │
│  ├─ srs.py       间隔复习引擎 (SM-2 变体)      │
│  ├─ planner.py   复习计划引擎                  │
│  └─ exporter.py  导出 Markdown/CSV/zip        │
└──────────────────┬──────────────────────────┘
                   │
           data/ 目录(纯文件, git 友好)
```

- 运行依赖:Python 3.10+、Flask(已安装)。测试:pytest + requests(已安装)。
- 无数据库、无构建步骤、无付费服务。

## 3. 目录结构

```
个人平台/
├── run.py                # 入口: python run.py → 自动开浏览器
├── app/
│   ├── server.py         # Flask 应用与全部 API 路由
│   ├── storage.py        # 存储层:加载/原子保存/自动备份/轮转
│   ├── srs.py            # 间隔复习算法(独立纯函数,可单测)
│   ├── planner.py        # 计划生成(独立纯函数,可单测)
│   ├── exporter.py       # 导出
│   ├── seed.py           # 首次初始化:目录骨架+少量示例(标记 seed)
│   └── static/           # 前端(index.html/app.js/style.css/vendor/katex)
├── data/                 # ★ 你的全部学习数据
│   ├── settings.json     # 考试信息(占位待确认)、每日时间、科目优先级
│   ├── catalog.json      # 科目→模块→章节 大纲骨架(用于进度统计)
│   ├── knowledge.json    # 知识点(数学/408/英语共用一套结构)
│   ├── mistakes.json     # 错题库(SRS 驱动复习)
│   ├── records.json      # 练习/答题记录
│   ├── vocab.json        # 英语生词与长难句
│   └── plan.json         # 已生成的每日计划与任务状态
├── backups/              # 自动备份(启动时+每日首次保存,保留最近 N 份)
├── tests/                # 单元测试 + API 集成测试
└── docs/DESIGN.md        # 本文档
```

## 4. 数据结构

### 4.1 settings.json —— 配置(含待确认占位)

```json
{
  "exam_year": null,          // 待确认:考试年份
  "exam_date": null,          // 待确认:如 "2027-12-25",确认后计划引擎启用倒计时
  "target_school": null,      // 待确认:目标院校
  "math_type": null,          // 待确认: "数一" | "数二"(影响大纲范围)
  "daily_minutes": 240,
  "subjects": {
    "math":   {"enabled": true, "priority": 1, "minutes": 90},
    "cs408":  {"enabled": true, "priority": 2, "minutes": 90},
    "english":{"enabled": true, "priority": 3, "minutes": 45}
  },
  "weekly_review_weekday": 6,  // 0=周一…6=周日,当天追加周复盘任务
  "backup_on_start": true,
  "max_backups": 14
}
```

### 4.2 catalog.json —— 大纲骨架(只描述结构,不含笔记内容)

`subject → track(模块) → chapter(章节)`,每章有稳定 `id`。知识点通过 `chapter_id` 挂接。
进度统计 = 已有知识点(状态≠not_started)的章节数 / 总章节数。

### 4.3 knowledge.json —— 知识点(三科目统一结构)

```json
{
  "id": "kp-math-0001",
  "subject": "math",                 // math | cs408 | english
  "chapter_id": "math-gaoshu-ch1",
  "name": "洛必达法则",
  "prerequisites": ["kp-math-0002"],  // 前置知识点 id,用于绘制依赖关系
  "tags": ["计算", "易错"],
  "content_md": "正文,支持 $LaTeX$ 与 Markdown",
  "formulas": [                       // 公式+适用条件+常见误用(数学重点)
    {"latex": "\\lim f/g = \\lim f'/g'",
     "condition": "0/0 或 ∞/∞ 型,且导数比的极限存在或为∞",
     "misuse": "不验证型就直接用;数列极限不能直接用"}
  ],
  "comparisons": [                    // 易混概念对比(408 重点)
    {"with": "对比对象", "table": {"维度": ["A 的特点", "B 的特点"]}}
  ],
  "source": "同济《高等数学》第七版 §3.2",   // 依据:教材/标准出处,必填建议
  "status": "not_started|learning|reviewing|mastered",
  "seed": false,                      // true = 系统自带示例,可删
  "created": "...", "updated": "..."
}
```

**约定差异处理**:凡涉及标准/教材有分歧的内容(如 OSI 模型层数表述、补码移码定义细节),必须在 `content_md` 或 `source` 中写明本条采用的定义及其出处。

### 4.4 mistakes.json —— 错题(SRS 核心表)

```json
{
  "id": "mk-0001",
  "subject": "math",
  "knowledge_ids": ["kp-math-0001"],   // 归因到知识点
  "qtype": "计算",                      // 数学:概念|计算|证明|综合应用
                                       // 408: 概念|计算|综合
                                       // 英语:定位错误|逻辑理解|词义误判|选项辨析
  "question_md": "题面…",
  "my_answer_md": "我当时的做法",
  "correct_answer_md": "正确答案(来自教材/真题解析)",
  "error_reason": "条件未验证",          // 错误原因(自分类)
  "solution_md": "正确推导过程(可核验,逐步)",   // 必填建议,不接受只有答案
  "source": "《660题》P12 题15",
  "difficulty": 3,                      // 1-5
  "reviews": [
    {"date": "2026-10-24", "result": "again", "interval": 1}
  ],
  "interval_days": 1, "ease": 2.3, "lapses": 2,
  "next_review": "2026-10-25",
  "archived": false,
  "seed": false, "created": "..."
}
```

### 4.5 records.json —— 练习记录

```json
{
  "id": "rc-0001", "date": "2026-10-24",
  "subject": "math", "session_type": "mistake_review|practice|mock",
  "knowledge_ids": [...],
  "total": 10, "correct": 7, "duration_min": 25,
  "detail": [{"ref": "mk-0001", "correct": false, "seconds": 180}]
}
```

正确率、用时、反复出错(lapses)统计全部由此表 + mistakes 派生,不冗余存储。

### 4.6 vocab.json —— 英语生词/长难句

```json
{"id": "vb-0001", "kind": "word|sentence",
 "text": "approximate", "context_md": "原文片段…", "meaning_md": "释义/句子分析",
 "source": "2011 Text 2",
 "reviews": [...], "interval_days": 1, "ease": 2.5,
 "next_review": "...", "lapses": 0, "seed": false}
```

### 4.7 plan.json —— 计划

```json
{"generated_at": "...",
 "days": {"2026-10-25": {"tasks": [
   {"id": "tk-...", "subject": "math", "kind": "review|practice|study|weekly_review",
    "title": "复习到期错题 6 题", "payload": {"mistake_ids": [...]},
    "est_minutes": 15, "status": "pending|done|skipped",
    "actual_minutes": null, "note": ""}
 ]}}}
```

重新生成某日计划时,只替换 `pending` 任务,保留 done/skipped(不破坏手动记录)。

## 5. 间隔复习算法(srs.py,SM-2 变体)

四级评分:`again`(忘了)/ `hard`(勉强)/ `good`(会)/ `easy`(轻松)。

| 评分 | 间隔 | 难度系数 ease |
|------|------|---------------|
| again | 重置为 1 天,lapses+1 | −0.20 |
| hard  | max(1, round(旧间隔×1.2)) | −0.15 |
| good  | 新题→1 天;否则 round(旧间隔×ease) | 不变 |
| easy  | 新题→3 天;否则 round(旧间隔×ease×1.3) | +0.15 |

- ease 限制在 [1.3, 2.8];间隔上限 60 天(考研周期内保证循环)。
- 纯函数 `schedule(item, result, today) → 新字段`,独立单测覆盖边界。

## 6. 计划引擎(planner.py)

输入:settings(每日总分钟、科目优先级与配额)、到期错题、薄弱知识点(正确率<60% 且练习≥3 次,或 lapses≥2)、未学知识点、当天是否复盘日。
输出:当日任务列表。规则:

1. 先排**到期复习**(欠账优先,est = 2.5 分钟/题),再排**薄弱知识点练习**(从错题库取该知识点未到期错题重组),再排**新知学习**(30 分钟/块)。
2. 各科目用时长不超过 `subjects[x].minutes`,总时长不超过 `daily_minutes`;装不下就少排,不挤占休息。
3. `exam_date` 已设置时:仪表盘显示倒计时,并按剩余时间占比提示阶段(基础/强化/冲刺);未设置时只按常规循环,不生成冲刺计划。
4. 每个任务可 `done / skip / move`(顺延到明天),可改 est_minutes —— 手动优先于算法。

## 7. API 一览(全部 127.0.0.1)

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/PUT | /api/settings | 配置读写 |
| GET | /api/catalog | 大纲骨架+进度 |
| GET/POST/PUT/DELETE | /api/knowledge[/<id>] | 知识点 CRUD(支持 ?subject=&q=) |
| GET/POST/PUT/DELETE | /api/mistakes[/<id>] | 错题 CRUD(支持 ?due=&subject=) |
| POST | /api/mistakes/<id>/review | SRS 评分 {result} |
| GET/POST | /api/records | 练习记录 |
| GET/POST | /api/vocab[/<id>/review] | 生词/长难句 + SRS |
| GET | /api/stats/summary | 各科正确率/用时/薄弱点/到期数 |
| GET | /api/plan/day/<date> | 查看某日计划 |
| POST | /api/plan/generate | {date} 生成(保留手动记录) |
| POST | /api/plan/task/<id> | {action: done/skip/move, actual_minutes} |
| GET | /api/plan/weekly/<date> | 周复盘数据 |
| GET | /api/practice/session | 今日应复习的错题+生词 |
| GET | /api/export/<what> | mistakes/knowledge/records → md/csv; all → zip |

## 8. 备份与数据安全

- 启动时自动备份 `data/ → backups/backup-YYYYMMDD-HHMMSS/`,每次保存节流为每日最多一份。
- 手动备份:`POST /api/backup` 或界面按钮。
- 轮转保留 `max_backups`(默认 14)份,超出删最旧。
- 写入采用"临时文件 + os.replace"原子操作,防止写一半损坏。

## 9. 明确不做的事

- 不内置 AI 生成题库(防错误答案、防无价值刷题);练习来自你的真实错题重组。
- 不做在线同步/云服务。
- 未确认考试信息前不生成日期锁定的全程计划。
