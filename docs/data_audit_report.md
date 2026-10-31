# 数据真实性与数据架构审查报告(data_audit_report)

> 审查日期:2026-10-31 · 代码基线 `2ce03db` · 方法:逐集合扫描代码播种点 + `data/*.json` 全量实况核对 + 写路径校验审计
> 约束遵守:本阶段未新增页面/视觉效果;未生成任何新的事实性数据;所有结论可复现。

## 一、数据五分类总表(逐集合定级)

图例:**官方真实**=可溯源到官方来源;**用户真实**=用户本人操作产生;**公开经验**=公开社区内容(带链接);**AI 生成分析**=AI 产出且已标注;**演示/模拟**=示例或硬编码兜底。

| 集合(data/*.json) | 实况 | 定级 | 诚实度评估 |
|---|---|---|---|
| `records`/`train`/`train_state` | 1 条做题记录 + 每日训练状态,均来自真实操作 | **用户真实** | ✓ 干净;学习任务完成自动落的 study_task 记录 total=0,不虚构对错 |
| `mistakes`(3 条) | 2 条 seed=True(示例错题,带"示例可删"约定),1 条用户真实 | **演示 2 + 用户真实 1** | ✓ seed 字段区分;⚠️ 前端列表未按 seed 显著标注"示例"(低风险,记录待办) |
| `vocab`(1 条) | 1 条示例词条,source 自述"示例…可删除" | **演示** | ✓ 已自标 |
| `knowledge`(5 条)+ `catalog` | 知识点骨架与章节结构;catalog.source="章节结构依据公开考试大纲整理;具体范围以当年官方大纲为准(待核验)",knowledge 项带 source/status | **官方真实(待核验)** | ✓ 有来源声明与"待核验"标注,无编造细节 |
| `universities`(10 所) | 名称/城市/官网/院系为公开常识手工录入;**enrollment/retest_line 全部为 None**,admission_source 空,last_verified None;图片来自 Wikimedia Commons 自由许可(CREDITS.md 留档) | **官方真实(待核验)+ 公开经验(图)** | ✓ 招生事实字段全空不冒充;UI 显示"待核实";⚠️ 基础字段(如 cs_school 名称)属公开常识但未逐条附来源链接 → v7 补 source_url 字段(默认空=未核验) |
| `questions`(508) | 461 AI 生成练习题(强制标注)、46 平台自录原创、1 真题(待核验);content-hash 去重 | **AI 生成分析 461 + 平台原创 46 + 官方真实 1(待核验)** | ✓ 三类强制分标,真题未核验不得冒充 |
| `motivations`(10) | 4 条公版古籍(战国策/荀子/孟子,license=公版古籍)、4 条平台原创(作者=大雪深埋)、2 条网络流传(author="佚名(网络流传)"、license="来源待核验") | **公版真实 4 + 平台原创 4 + 来源待核验 2** | ✓ 三种来源已如实分标;server.py 内 QUOTES 硬编码兜底池亦标"系统内置/网络流传佚名"(V3.1 已降级为兜底) |
| `experience_posts`(4) | 全部 author="大雪深埋"、无 source_url——平台原创方法论文章,非真实博主内容 | **AI/平台生成分析** | ⚠️ 数据侧无来源字段标注"原创性",靠作者名暗示;v7 补 source_type="platform_original" |
| `radar`(82) | 研招网官方(带官方日期)、GitHub API(真实元数据)、DDG 公开搜索(仅摘要标"日期未核验")、AI/营销类已分类;评分依据保留 | **官方真实 + 公开经验 + AI 生成分析**,营销类单独 G 类 | ✓ 全平台最完整的来源字段(via_query/published_at/verified_at/verify_status/dedup_hash) |
| `institutions`(0) | 空;校验:年份 2020-2040/科目代码 101/201/301/408/URL 格式 | — | ✓ 入口校验在 |
| `goals`/`plan`/`reflections`/`coach` | 用户真实操作数据 | **用户真实** | ✓ |
| `sources`(12) | 研招网/教育考试院/各校研究生院官网 URL 清单 | **官方真实**(网址公开可验证) | ✓ |
| 代码内硬编码:QUOTES 兜底池、默认配额(math/cs408/english/politics 各 5)、`stage_of` 月份阶段划分 | 均为**逻辑默认值**而非事实数据 | **演示/默认** | ✓ 均有标注或为配置默认 |

**结论:未发现"事实数据伪装真实"的情况。** 所有 AI 生成内容已标注;所有无法核验的招生事实字段为空而非编造;示例数据均带 seed 标记或自述"可删除"。

## 二、四大输出(按用户要求)

### 1. 当前有哪些数据是模拟/演示数据

- `mistakes` 中 2 条 seed=True 示例错题(含"等价无穷小误用"等),`vocab` 中 1 条示例词条——**均带标记,建议用户熟悉后手动删除**(删除入口已存在,不做自动清理以免误删真实数据);
- server.py 内置 QUOTES 兜底语录池(仅当用户语录库为空时兜底,已标"系统内置");
- **没有**任何模拟的分数线、招生人数、报录比、录取结果——这些字段全部为 None/空。

### 2. 哪些接口没有真实数据来源(含校验缺口)

- **实锤缺口 F-A**:`PUT /api/universities/<uid>` 填 **retest_line(复试线)只强制年份,不强制来源**——违反"分数线须可追溯"红线(招生人数已有强制)。→ 本轮已修(见 §四)。
- `POST /api/institutions` 的 `requirements/key_dates` 自由文本无来源要求(风险低:属用户自记备考信息,非对外展示的事实数据;记录不修)。
- 语录兜底池/默认配额:接口层已标注来源或"默认",不构成缺口。
- 知识点 content_md 部分为骨架描述,来源挂在 catalog 级"待核验"声明,逐条 source 字段已有,深度内容按需补。

### 3. 哪些页面需要重构(仅数据呈现维度,本轮不动 UI)

- **梦校详情页**:enrollment/retest_line 已显示"待核实" ✓;但未显示"数据来源链接"(admission_source 仅存文本,无 source_url 字段)→ v7 字段落位后,展示时附链接即顺带解决;
- **错题列表**:seed=True 示例错题与真实错题同列表展示,建议后续加"示例"角标(低风险待办);
- **经验与方法页**:4 篇平台原创文章建议加"平台原创"角标,与公开经验帖区分(v7 字段落位后同理);
- 其余页面(首页雷达/训练/画像)数据呈现已带来源与时间,无需重构。

### 4. 建议的数据同步架构

分层原则:**事实层(官方)→ 经验层(公开/AI,永远标注)→ 用户层(本地自持)**,三层不混存:

```
[事实层 facts]      研招网/高校官网/GitHub API —— 唯一允许写入"分数线/招生人数/大纲"的层,
                    必须带 source_url + published_at,无来源则字段保持空
[经验层 signals]    DDG/站点索引/用户提交链接 —— 只存链接+摘要+核验状态,永不升级为事实
[用户层 records]    本地操作数据 —— 只属于用户,永不参与来源追溯体系
同步机制:radar.refresh(已有,幂等+去重+过期标记)周期拉取经验层;
         事实层不自动抓取招生数字(反爬/准确性风险),采用"用户录入+强制来源+人工核验(verify 端点已有)"
         —— 这是当前架构有意为之的诚实设计,不建议改为自动抓取
```

## 三、统一来源字段标准(任务 3)

标准块(7 字段,所有承载事实/外部内容的集合逐步对齐;已有同义字段的集合做**映射而非重复**):

| 标准字段 | universities | questions | motivations | experience_posts | radar | knowledge |
|---|---|---|---|---|---|---|
| source_name | admission_source(已有) | source_name(新增) | author(已有) | author(已有) | platform(已有) | source(已有) |
| source_url | **新增**(默认空=未核验) | source_url(新增,真题待核验) | source_url(新增,空) | source_url(已有) | url(已有) | — |
| source_type | official/未核验 | 枚举已有(真题/AI 生成/自录) | 公版/平台原创/待核验 | **platform_original(新增)** | ctype+verify_status(已有) | official_pending |
| published_at | admission_published(已有) | **新增**(真题年份) | — | created(已有) | published_at(已有) | — |
| updated_at | **新增** | **新增** | **新增** | **新增** | fetched_at(已有) | updated(已有) |
| verified_at | last_verified(已有) | **新增**(null=未核验) | — | — | verified_at(已有) | — |
| confidence | — (以 data_status 表达) | — (枚举即置信) | — | — | score(已有) | — |

实现:v6→v7 迁移为上表"新增"字段补位(**一律默认空/未核验,不填任何编造值**),源代码同义字段保持兼容。

## 四、本轮实际修改(审查后执行,非 UI)

1. **F-A**:`universities_update` 补齐复试线来源强制(填 retest_line 必须同时有 admission_source),与招生人数对齐;测试覆盖;
2. **迁移 v6→v7**:按 §三 标准为 universities/questions/motivations/experience_posts 补 source_url/source_type/published_at/updated_at/verified_at(全部默认空或既有真实值,零编造);schema_version 6→7;
3. 测试:迁移幂等性 + 字段落位 + F-A 校验(新增/扩展测试用例)。

## 五、优先数据源清单(任务 5,写入标准)

院校与招生事实仅接受以下来源(录入时 source_url 校验域名归属):
1. 中国研究生招生信息网(yz.chsi.com.cn)——研招网;
2. 高校研究生院官网(如 yz.tsinghua.edu.cn);
3. 高校学院官网;
4. 当年官方招生简章/专业目录原文(上述域名的直接页面)。
低于以上层级的来源(自媒体、聚合站)录入时降低置信并在 UI 标"来源待核验"。
