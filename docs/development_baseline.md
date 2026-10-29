# 第二阶段开发基线(development_baseline)

> 生成时间:2026-10-27 · 基线提交:`b4a607a`(标签 `baseline-v3.1`)· 分支 `main`
> 本文档是迭代开发的安全基线快照。所有结论均来自对当前工作区的实测,无推测成分。
> **2026-10-30 第二轮核对**见文末 §8;`docs/audit_report.md` 已回填创建(第一阶段补做)。

## 0. 审计前置说明

- **`docs/audit_report.md` 不存在**。docs/ 目录现有:AI_SETUP / BENCHMARK / DEPLOY / DESIGN / RESOURCES / TESTING / TODO 共 7 份文档。第一阶段未产出该审计报告,本文件第 1-5 节即补做的审计,结论已按实测填写。
- **`docs/implementation_plan.md` 不存在**,本次按"更新"意图**新建**,内容见该文件。
- 历史背景:第一阶段的实际成果以 Git 历史为准(V3.1 热点雷达 `d3f8962`、V3 题库与每日训练 `91951b8`、公网隧道脚本 `dee92ac`),平台功能与测试状态见第 3、4 节。

## 1. Git 工作区状态(任务 1)

| 项 | 状态 |
|---|---|
| 当前分支 | `main`(唯一开发分支,跟踪 `origin/main`) |
| 基线提交 | `b4a607a` "保全:补入 3 所院校的自动生成 fallback 校徽" |
| 工作区 | **干净**(status 无任何未提交/未跟踪文件) |
| 未提交修改 | 无。审计时发现的 3 个未跟踪 SVG(`scut/whu/zju-fallback.svg`)为院校图片管线的自动生成资产,与已入库的 `sjtu/xidian-fallback.svg` 同族,已验证内容合法后**提交保全**(非丢弃) |
| 额外 worktree | `C:/Users/南金林/WorkBuddy/Worktrees/个人平台/main-7723cfe2`,分支 `workbuddy/main-7723cfe2`,与 main 同指 `ddc6d6f`。**外部工具(WorkBuddy)所有,本轮不触碰、不合并、不删除** |
| 回滚锚点 | 标签 `baseline-v3.1` 已打在基线提交并推送 origin。任何后续改动出问题,以该标签为"已知良好状态" |

**结论:无覆盖风险。** 所有第一阶段的修改均已提交并推送;本阶段从干净工作区开始。

## 2. 启动 / 构建 / 测试 / 数据存储(任务 2)

| 类别 | 命令 / 位置 | 说明 |
|---|---|---|
| 启动 | `python run.py` | 默认 127.0.0.1:8321;`DX_PORT`/`PORT` 环境变量可覆盖;Windows 桌面环境自动开浏览器 |
| 构建命令 | **无构建步骤**(纯 Python + 原生 JS,无打包) | render.yaml 的 buildCommand 仅 `pip install flask` |
| 测试命令 | `python -m pytest tests/ -q` | 13 个测试文件;详见第 4 节 |
| 数据库类型 | **无 SQL 数据库**。JSON 文件存储(`app/storage.py`,原子写 `os.replace` + 线程锁) | `render.yaml` 未配置任何 Postgres/Redis |
| 数据位置 | `data/*.json`(25 个集合文件)+ `data/images/`(错题照片、校徽) | 迁移版本标记 `data/schema_version.json`,当前 **v6** |
| 备份 | `backups/`(启动时自动备份,现有 18 份) | 由 `Store._maybe_daily_backup` 驱动 |
| 部署 | `render.yaml`(daxue-shenmai,free plan,健康检查 `/api/health`);实际公网暴露经 cloudflared 隧道(`tools/publish.py`),**默认未部署到任何生产环境** | |

## 3. 基线测试结果(任务 3,原始记录)

- 全量套件:`python -m pytest tests/ -q` 于本机(Windows / Python 3.10.11 / flask 3.1.3 / pytest 9.1.1)执行,2026-10-27 深夜启动、跨零点完成,耗时 53 分 07 秒。
- **原始结果:`1 failed, 141 passed`**(原始输出逐字记录):
  ```
  FAILED tests/test_api_v2.py::test_weekly_report_endpoint - assert 0 == 6
  1 failed, 141 passed in 3186.79s (0:53:06)
  ```
- **失败根因(已定位,本轮不修)**:`test_weekly_report_endpoint` 向"今天"写入做题记录,却查询**硬编码的周起始日 `2026-10-24`**。该周写于 10 月中旬,随真实日期推进(现为 10-28),新写入的记录落在该周窗外,断言 `this_week.total == 6` 得 0。此测试将永久失败,与 Midnight/竞态无关;单独重跑复现同一失败。
- 影响:仅测试自身日期硬编码,**不是产品代码缺陷**;`/api/report/weekly` 端点功能正常(其余 report 相关断言均过)。修复方式:测试内按 `datetime.date.today()` 动态计算所在周起始日(已在 implementation_plan.md 列为 T0,下一阶段第一批执行)。
- 历史参照:V3.1 合入时(2026-10-27 日内)同一套件 142 passed 全绿——即基线在"测试写入日"是绿的,日期硬编码使其随后转红,进一步证实根因。
- CI(GitHub Actions,ubuntu + Python 3.11):push 到 main 触发,历史提交全绿;CI 与本地均不依赖本机 Ollama(cloud/local 模式显式隔离)。
- 注意:本地套件全跑 26~53 分钟(含真实文件 IO 集成测试,受机器负载波动),属预期,非卡死;单文件可用 `pytest tests/<file>.py -q` 快速定位。

## 4. 隔离分支 / 工作区(任务 4)

- **现状**:已有外部 worktree(WorkBuddy),不征用。
- **本阶段的隔离策略**(已执行,均不影响现有工作):
  1. 回滚锚点:标签 `baseline-v3.1`(只读指针,零风险);
  2. 每个任务独立小提交,推送前本地全量测试必须通过;
  3. 数据目录 `data/`、`backups/` 永不入库,任何改动都不可能波及用户数据;
  4. 未创建新开发分支——理由:单人单人库、CI 直接守护 main、历史一贯工作流即"小步提交 main"。若后续任务需要大改(如登录体系扩展),再按需开 `feature/*` 分支,届时不会影响现有工作。

## 5. 资源保护措施盘点(任务 5)

| 资源 | 保护措施 | 实测确认 |
|---|---|---|
| 数据库迁移 | `app/migrate.py` 顺序迁移(`@migration(n)` 链,v1→v6),`schema_version.json` 记录当前版本;迁移幂等(重跑不重复播种);**测试与生产共用同一迁移代码路径** | v6,含热点雷达数据层 |
| 启动备份 | `create_app` 后 `store.backup("startup")`(可在 settings 关闭),`backups/` 现有 18 份 | 已确认 |
| 上传文件 | 仅允许图片扩展名(`ALLOWED_IMAGE_EXT`,白名单校验);落盘到 `data/images/`(gitignore 内);文件名服务端生成 | 已确认 |
| 环境变量 | 使用中:`DX_PORT`/`PORT`(端口)、`DX_DATA_DIR`(数据目录重定向,测试隔离用)、`OLLAMA_MODELS`(本机);云端 AI Key 走 `OPENAI_API_KEY` 等 6 个环境变量,**仅运行时读取,不落盘** | 已确认 |
| 密钥扫描 | `git grep` 长密钥模式扫描:未发现硬编码密钥/密码/令牌;无 `.env` 文件;用户密码为 PBKDF2-HMAC-SHA256(600k 轮)哈希存储,库存的是哈希非明文 | 已确认 |
| 敏感路径 gitignore | `data/`、`backups/`、`exports/`、`*.log`、`tools/cloudflared.exe`(53MB 二进制)、`tools/public_url.txt`(本机公网地址)、`tools/tmp/` | `git check-ignore` 逐一确认命中 |
| 会话 | 服务端随机 token(32B),HttpOnly + SameSite=Lax cookie,7 天滑动过期 | 已确认 |

## 6. 本轮开发边界与选定任务(任务 6)

**边界(本轮不做):**
- 不重置 Git、不 force push、不清理任何"未知"文件;
- 不删除/重建 `data/`(用户真实学习数据 + 70 条雷达库);
- 不把任何真实凭据写入仓库或文档;
- 不部署 Render / 不购买域名 / 不产生任何费用;
- 不动 WorkBuddy worktree;
- 不做大规模重构:现有 142 项测试(141 绿 + 1 项日期硬编码待修)锁定的行为是本轮的安全网;T0 修复前,全量回归以"仅 T0 一项已知失败"为通过标准,不得引入新失败。

**已随基线完成的零风险动作:**
1. 提交保全 3 个未跟踪 SVG(`b4a607a`);
2. 创建并推送回滚标签 `baseline-v3.1`。

**选定任务(证据充分 · 优先级高 · 风险低 · 可验证,执行细则见 implementation_plan.md):**

| # | 任务 | 证据 | 验证方式 |
|---|---|---|---|
| T1 | 新增 `requirements.txt` 并固定 flask 版本;render.yaml 与 CI 改为引用它 | 审计发现仓库**无依赖清单**,CI/Render 各自 ad-hoc `pip install`,版本漂移无锁定(实测 flask 3.1.3 / pytest 9.1.1) | 全新 venv 按 requirements 安装 → 142 测试全过 → CI 绿 |
| T2 | 密码强度基线校验:注册/改密时强制最小长度 | **证据更正(2026-10-28)**:复核发现 auth 层**已有 6 位下限**(create_user/change_password 各一处),基线初稿"无最小长度校验"系误记——当时只检索了 server.py 端点层。任务据实缩小为:下限 6→8 位 + 边界测试 | 单测:7 位 400、8 位通过(两入口);存量账号登录不受影响;全量回归 |
| T3 | 会话清扫:登录时清理过期会话已存在,补充"启动时"一次性清扫 | `auth.create_session` 已过滤过期项(实测确认),但历史过期 token 仍留在 `sessions.json` 中,公网暴露面下值得收敛 | 单测:插入过期会话 → 触发清扫 → 文件中不存在 |

**明确排除的高价值但超出本轮风险边界的项**(记录到 implementation_plan.md 待后续阶段决策):邀请码注册体系(公网多人使用,涉及账号体系扩展)、Render 正式部署、AI 云端 Key 集成。

## 7. 环境适配性结论

当前环境**适合安全修改**:工作区干净、全部历史已推送、测试基线全绿、用户数据不入库且有 18 份备份、无硬编码密钥。无需"保留现场"特殊处理。

## 8. 第二轮核对(2026-10-30)

**任务 1 — Git 状态**:工作区干净(status 无任何条目),HEAD `2d41eb6`(T4),全部已推送;标签 `baseline-v3.1` 在;WorkBuddy worktree 仍在原 commit,未触碰。上一轮 T0-T4 六个提交即 `584e1d8..2d41eb6`,CI 全绿。**无覆盖风险。**

**任务 2 — 命令与存储**(与 §2 一致,复核无变化):启动 `python run.py`;无构建;测试 `python -m pytest tests/ -q`;JSON 存储 `data/`(schema v6);备份轮转**确认存在**(`Store._rotate`,默认 `max_backups=14`)——上轮"18 份备份"为轮转前的历史堆积,机制本身健全。

**任务 3 — 当日基线测试**:全量 `pytest tests/ -q` 于 2026-10-30 重新执行,原始输出逐字:
```
146 passed in 2300.13s (0:38:20)
```

**任务 4 — 隔离**:沿用上轮策略(标签锚点+小步提交+数据不入库);未新建分支——本轮任务均为文档/CI 改动,风险更低。WorkBuddy worktree 不征用。

**任务 5 — 资源保护**(增量发现):
- `deploy/requirements.txt`(`flask>=3.0`,未固定版本)为**孤儿文件**——docker-compose 构建上下文是仓库根,Dockerfile 实际复制根 `requirements.txt`(已固定 3.1.3);全仓 grep 确认无任何引用。已列 N2 清理,消除"第三份依赖清单"漂移源。
- README.md 数据陈旧:测试徽章写 117 项(实际 146),功能表缺每日训练/热点雷达/公网隧道;`deploy/` 与 Docker 说法经核实**属实**。

**任务 6 — 本轮边界与选定任务**:边界同 §6(不重置/不删库/不部署/不动 worktree/不做大重构);**邀请码注册仍挂起**——上轮已呈报方案 A(共享数据)/B(完全隔离)/C(不做),用户尚未选择,继续等待。本轮选定(均文档/CI 级,风险极低):

| # | 任务 | 证据 | 验证方式 |
|---|---|---|---|
| N1 | 创建 `docs/audit_report.md`(第一阶段回填) | 模板要求阅读该文件但其不存在(上轮已如实记录) | 文件落库;内容与 Git 历史/测试记录逐项可对 |
| N2 | README 事实刷新 + 删除孤儿 `deploy/requirements.txt` | 徽章 117→146;功能表缺 V3/V3.1;孤儿清单全仓无引用 | README 数字/功能与实测一致;docker 构建(IFF 用户需要时)不受影响;全量回归 |
| N3 | CI 增加 Python 3.10 job(矩阵) | T1 记录的 CI 3.11 vs 本地 3.10 版本差,闭环 | 两个 job 均绿的 CI 运行 |

**结论:环境适合安全修改,无需保留现场。**
