# 第四轮报告:功能精简、Ollama 移除与经验贴重构(v4_report)

> 2026-10-31 · 按指定七步执行 · 备份:`backups/pre-v4-20261031-141538/`(data+app 代码,4MB)
> 测试:全量 **154 passed in 2 分 16 秒**(179 − 32 项已删功能用例 + 7 项新增/改写),CI 见推送。

## 1. 删除了哪些功能(前端+后端+路由层完整移除)

**本地 Ollama(彻底)**:`get_ai_config` 的 local 模式、`local_service_ok`、`list_local_models`、`LOCAL_BASE_URL`、`/api/ai/status`、`/api/ai/models`、`/api/ai/recognize`(错题OCR)、设置页模型下拉/Ollama 状态卡、所有"请安装/启动 Ollama"提示;`ai.py` 现为云端 OpenAI 兼容 only(settings 优先 → 6 个环境变量兜底),并有 `test_no_local_ollama_artifacts` 红线测试(11434/list_local_models/ollama serve 等字样不得回潮)。启动横幅与页脚已改。

**AI 顾问**:`#coach` 页、`/api/coach/chat`、`/api/coach/chat/stream`、`/api/coach/history`、`/api/tools/execute`(提案白名单)、`coach_reply/coach_stream` 函数。

**刷题系统**:`#study` 全部页签(训练/练习/错题/生词/题库/知识库管理)、`/api/mistakes*`(5)、`/api/vocab*`(4)、`/api/practice/session`、`/api/questions*`(5)、`/api/train/*`(4)、`/api/upload`+`/api/images/*`(错题图)、`/api/reflections` 保留但 `/api/reflections/extract` 转为云端/规则;导航"练习工具"入口与"待刷"徽章移除。

**数据零删除**:mistakes/train/questions/vocab 等历史 json 原样保留(画像/周报仍可读);records/plan/reflections/成长统计全部保留。

## 2. 修改的文件

`app/ai.py`(重写,131 行)、`app/server.py`(-294 行端点 + 新增 analyze)、`app/static/app.js`(2729→1409 行)、`app/static/index.html`(导航/页脚/浅色默认)、`app/static/sw.js`(v5)、`app/questionbank.py`(来源字段)、`app/radar.py`(模板去错题化)、`tests/` 11 个文件修剪改写、`docs/v4_checklist.md`。

## 3. 新增接口

`GET /api/radar/analyze/<id>`(经验贴拆解:AI 可用→按摘要提炼并标 AI 级;未配置→规则提炼如实标注"规则提炼(AI 未配置)";禁止编造分数/录取/身份)、`/api/radar?q=`(搜索);`/api/settings/ai/test` 保留用于云端连通性测试。

## 4. 经验贴模块(重构完成)

- 新路由 `#exp`:顶部搜索 + 12 个横向分类标签(985/211/普通本科逆袭/计算机/11408/数一/英语一/408/择校/复试调剂/失败避坑/长期自律,规则映射可解释)+ 7/30/90/一年/全部时间筛选;
- 卡片展示:标题/平台/作者(公开时)/发布时间/原文链接/抓取时间/摘要/分类/可信度等级(S·官方原始/A·可信公开/B·来源待核验/AI·模型原创/来源未定);原文跳转、收藏、不感兴趣;
- **拆解**:每条可请求 AI 拆解(方法/背景/适用人群/局限),未配置 AI 时规则提炼并明确标注——已实测显示"规则提炼(AI 未配置)";
- **今日一句**:来自语录库(公版古籍/平台原创带出处,来源待核验条目显著标注);
- 数据源:复用雷达四通道(研招网官方/GitHub API/DDG/小红书抖音站点索引);**去重**(content-hash)、**失效标记**(reverify)、**最后更新时间**显示均为既有能力;代理缺失时站点通道如实显示失败,不用虚构内容填充;
- 定时更新:`auto_refresh` 设置(每 6 小时线程)可用,默认关闭需在设置开启。

## 5. 平台精简后形态

导航:首页 / 院校库 / 院校预测 / 经验贴 / 成长记录 / 设置(桌面+移动);首页 = 考研进度(计划完成率/距考天数)+ 重要提醒(五段式行动建议)+ 近期动态(雷达);默认主题改为浅色(深色可切),SW 缓存升 v5;启动横幅改为"2028 AI 考研决策与情报中心"。

## 6. 测试与验收

- 全量 154 passed(含 Ollama 移除红线、经验贴分析诚实标注、来源强制回归);
- 浏览器活体验收:新首页(2028/距考/计划完成率/重启恢复建议——正确识别 7 天未学习)、经验贴页(今日一句/分类/27 张卡/拆解规则版)、设置页(云端 AI 卡、无 Ollama 卡、无训练题量卡)、已删端点 404/401、无来源保存被拒(上轮)、`coach/history` 401(认证门仍生效);
- 修复过程中经浏览器真实加载发现并修复 3 处 JS 结构错误(悬空 else/重复 `}`)——只靠括号配平检查不够,已用真实 script 加载验证。

## 7. 未完成/说明

- 云端 AI 未配置时拆解为规则提炼(如实标注);配置 Key 后自动升级为 AI 拆解;
- 反思页签已并入成长记录;说题功能属 coach 体系,随其移除;
- 独立刷题软件成绩导入 mock_scores 需其数据格式(待用户提供)。
