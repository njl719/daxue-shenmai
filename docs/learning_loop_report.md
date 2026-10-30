# 第四阶段报告:核心学习流程与 AI 能力完善(learning_loop_report)

> 执行日期:2026-10-30 · 依据:前三阶段报告 + 代码实测。原则:只完善已有功能、不虚构数据、AI 输出必经校验、无新增模块。

## 0. 学习闭环逐环节审计结论

闭环:学习计划 → 实际执行记录 → 错题录入 → 错因与知识点管理 → 复习任务 → 再次测试 → 学习结果记录 → 薄弱点分析 → 后续计划调整。

| 环节 | 现状(实测) | 本轮动作 |
|---|---|---|
| 学习计划 | `planner.generate_day_plan` 已按考试日期(exam_phase)、每日可用时长(daily_minutes)、各科配额、到期错题优先、薄弱知识点(weak_ids)排任务;科目启停可配置,无写死默认 | 无缺陷,不动 |
| **实际执行记录** | **断链(实锤)**:任务标记 done 仅改状态,不产生学习记录——周报/画像的"学习投入"与任务完成率互不相通 | **L1 已修** |
| 错题录入 | 拍照上传(白名单校验)→ AI 识别(置信度、needs_confirmation 强制开启)→ 人工校对后结构化保存;原文图片与 ai_recognition 字段并存 | **L2 修复后全覆盖 11408** |
| 错因/知识点管理 | 错因枚举 10 类(ERROR_REASONS)、知识点多标签;**检索缺错因/知识点过滤** | **L3 已补** |
| 复习任务/再次测试 | SRS(grades again/hard/good/easy,ease∈[1.3,2.8])驱动到期复测;计划引擎把到期错题排为最优先任务 | 无缺陷,不动 |
| 学习结果记录 | 练习/训练提交均落 records(client_id 幂等) | 无缺陷,不动 |
| 薄弱点分析 | compute_weak_points 综合 错题+练习+反思 三类证据,带证据链与 confirmed/suspected/unverified/conflict 状态,不凭空贴标签 | 无缺陷,不动 |
| 计划调整 | 顺延/重排/次日移动;薄弱点驱动任务生成 | 无缺陷,不动 |

## 1. 本轮修复(根因/修复/验证)

### L1 任务完成与学习记录打通(app/server.py `plan_task`)

- **根因**:闭环第一环断裂——完成任务只改 `status`,学习投入从未进入 records;周报的"做题/时长"与"任务完成率"因此永远对不上。
- **修复**:action=done 时自动落一条 `session_type="study_task"` 的学习记录,`client_id="task-<id>"` 幂等(reset/skip 后再 done 不重复);`duration_min` 用真实上报的 actual_minutes(未报则用预估);任务回填 `record_id` 可追溯。
- **不虚构原则**:total/correct 恒为 0——"完成学习任务"不冒充"做题对错",不污染正确率统计;科目非法的任务不落记录。
- **测试**:`test_task_done_creates_linked_record` / `test_task_done_idempotent_after_reset`(done→reset→done、done→skip→done 均单条)/ `test_task_done_links_duration`。

### L2 政治(11408 之一)在 AI 链路中缺失(app/ai.py)

- **根因(三处)**:① `RECOGNIZE_PROMPT` 科目枚举只有 math|cs408|english;② `_SUBJECT_NORMALIZE` 无政治(马原/毛中特/史纲/思修/时政);③ `recognize_mistake` 返回的 subject **原样透传**——模型返回"政治/数学"等中文时,保存接口会 400。qtype 枚举也缺政治的"选择/分析"。默认框架 11408 含政治,拍政治错题整条链路不可用。
- **修复**:提示词补 politics 与 选择/分析;归一化表补 7 个政治别名;`_KNOWN_TOPIC_KW` 补政治关键词(反思提取的科目推断同步受益);识别结果 subject **强制归一化**——可归一则转枚举,不可归一置空(不猜),再由用户在校对时选择。
- **测试**:中文科目"政治"→politics(含 mock _post_chat 全链路)/ 不可识别科目置空 / 反思提取含 politics / 提示词内容断言。

### L3 错题检索补错因与知识点过滤(app/server.py `list_mistakes`)

- **根因**:检查单第 4 项"检索"——原过滤器只有科目/题型/文本/到期,无法按错因(如"计算失误")或知识点标签检索错题,错因管理与复习针对性不足。
- **修复**:新增 `error_reason`、`knowledge_id` 两个查询参数,语义为精确匹配。
- **测试**:`test_mistake_filters_error_reason_and_knowledge`(含空结果)。

## 2. 明确核查过、不修改的项(避免无证据重构)

- **AI 画像真实性**(检查单 5):compute_profile/compute_weak_points 只读 records/mistakes/reflections 真实数据;L1 落库的 study_task 记录 total=0,不参与正确率,不等于掌握度。
- **AI 结论可追溯/不覆盖原始数据**(检查单 7):AI 识别结果存 `ai_recognition` 独立字段且 `needs_confirmation=True` 强制开启,原始图片永久保留;教练工具提案走 PROPOSE 确认制;用户校对后保存的才是权威数据。已有机制健全。
- **模型失败处理**(检查单 8):`_post_chat` 空回复重试+json_mode 降级重试;识别/反思/教练在 AI 不可用时返回明确错误与"手动填写"引导(`_empty_recognition`),不伪造;雷达 AI 失败保留规则版。已有机制健全,本轮 L2 的归一化属于"返回格式错误"处理的补强。

## 3. 测试结果(原始记录)

- 新增 `tests/test_learning_loop.py` 8 项:定向运行 **8 passed**。
- 全量回归:见下。

```
161 passed in 1056.26s (0:17:36)
```
(153 → 161 为新增 test_learning_loop.py 8 项;0 失败,无回归。)

## 4. 提交清单

- `app/server.py`:L1(任务→记录)、L3(检索过滤)
- `app/ai.py`:L2(politics 枚举/归一化/关键词、识别结果强制归一化)
- `tests/test_learning_loop.py`(新增 8 项)、`docs/learning_loop_report.md`(本文件)、`docs/implementation_plan.md`(状态)

## 5. 遗留与说明

- 政治错题的拍照识别质量依赖本地 qwen2.5vl 对中文印刷/手写的实际表现,建议用户实测一批后反馈;识别失败路径已有(手动填写),不会阻塞。
- 邀请码注册(A/B/C)仍待用户决策,与本阶段无关。
