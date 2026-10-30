# 第三阶段报告:后端、数据库与数据可靠性修复(backend_fix_report)

> 执行日期:2026-10-30 · 基于第二阶段基线(`docs/development_baseline.md` §8)与第一阶段审计回填(`docs/audit_report.md`)
> 原则执行情况:全部修复均有实测证据与前置复现;每次只改一个逻辑单元并跑定向测试;接口与数据格式保持兼容;未删除任何真实数据;未访问生产环境(本机即全部环境)。

## 0. 逐项核查结论(七项检查单)

| # | 检查项 | 结论 |
|---|---|---|
| 1 | 数据关联 | **发现 F2**:知识点删除无级联,`mistakes[].knowledge_ids`/`records[].knowledge_ids` 会留下孤立引用(当前真实数据恰好无孤儿,属潜在缺陷);画像端已用 `kp.get()` 容错不会崩,但关联静默丢失。→ 已修 |
| 2 | 持久化 | 后端 JSON 原子写即持久;前端仅 `localStorage` 存主题色(`dx-theme`),学习数据全部走 API——刷新/重登录均从服务端读,无缺陷 |
| 3 | 前端统计真实性 | 首页/训练/画像统计均来自真实接口(records/train/mistakes/growth);硬编码仅存于语录兜底池(已标注来源)与默认配额 fallback(标注"默认"),无演示数据混入 |
| 4 | 参数校验/异常处理 | **发现 F1、F3**:`/api/records` 的 total/correct 无负数与 correct≤total 校验、`int("abc")` 直接 500、date 未验格式;`/api/mistakes` 的 difficulty 同类。→ 已修 |
| 5 | 重复提交/状态一致/并发 | records(train)均带 `client_id` 幂等;train finish 幂等;radar 提交有去重哈希;Store 全程 RLock+原子写。真实数据实测:0 重复 client_id、0 孤儿引用。无缺陷 |
| 6 | 鉴权/隔离/敏感信息 | 全部业务端点在 `before_request` 认证门内(历史实测 401);审计日志仅记用户名与事件,无密码/令牌;`/api/lan` 公开但仅返回局域网 URL(手机配对设计使然,信息量低,记录在案)。单账号架构下的"用户隔离"不适用(邀请码方案 A/B/C 仍待用户决策) |
| 7 | 初始化/迁移/备份恢复 | 迁移 v1→v6 幂等有版本标记;备份有启动/每日双触发+14 份轮转;**发现 F4:恢复流程完全缺失**(有备份无恢复路径,回滚能力形同虚设)。→ 已补工具与测试 |

## 1. 实际修改与根因/修复/验证

### F1 `/api/records` 参数校验(app/server.py)

- **根因**:`total = int(body.get("total") or 0)` 三重缺陷——垃圾字符串抛 ValueError 变 500;负数放行;`correct > total` 放行(会污染正确率统计);`date` 不验格式。
- **修复**:统一 `_int_or_none`(缺省→默认,非法字符串→400);负数、correct>total、非法 date(非 ISO 格式)一律 400 带中文原因。兼容性:合法整数/数字字符串仍接受(测试覆盖 `"8"`→8);现有前端传值全部合法。
- **测试**:`test_records_reject_negative_and_overflow` / `test_records_reject_non_int_and_bad_date` / `test_records_accepts_valid_and_casts`(7/7 过)。

### F2 知识点删除级联清理(app/server.py `delete_knowledge`)

- **根因**:删除只动 `knowledge` 集合,引用残留;后续画像聚合按 `kp.get(kid)` 跳过,薄弱点证据静默缺失。
- **修复**:删除后同请求内清理 `mistakes`/`records` 两处引用,响应体返回 `{deleted, mistakes, records}` 计数(新增字段,向后兼容)。
- **测试**:`test_knowledge_delete_cleans_references`(建引用→删→断言清理计数+画像 200+重复删 404)。

### F3 `/api/mistakes` difficulty 校验(app/server.py)

- **根因**:`int(body.get("difficulty") or 3)`——`"abc"` 500;`0 or 3` 把合法越界值吞成默认 3(测试时抓到的真 bug)。
- **修复**:显式区分"未填→默认 3"与"填了但非法→400(1-5)"。
- **测试**:`test_mistake_difficulty_validation`(`abc`/0/9 均 400,`"4"`→4)。

### F4 备份恢复工具(tools/restore_backup.py,新增;tests/test_backend_fix.py)

- **根因**:只有备份没有恢复,回滚能力缺失。
- **修复**:三重安全设计——默认只读列出;`--apply` 需交互键入 `RESTORE`;执行前自动做一次 `pre-restore` 安全备份。恢复为镜像式(多余文件删除),核心逻辑 `restore()`/`mirror_copy()` 可单测。
- **测试**:`test_restore_dry_run_and_mirror`(dry-run 不动文件;apply 后内容还原、多余文件删除、安全备份存在)/ `test_restore_rejects_bad_name`;另在真实 `backups/` 上做了**只读**列出演练(7 份备份均正确识别)。

## 2. 测试结果(原始记录)

- 新增 `tests/test_backend_fix.py` 7 项:定向运行 **7 passed**(经历一次自我修正:`or` 默认值吞掉合法 0、垃圾串静默归零——修复语义后全过)。
- 全量回归:见下(运行完成后回填)。
- 兼容性检查:grep 确认无任何既有测试/调用方依赖被收紧的边界值。

全量回归原始输出:
```
153 passed in 1085.91s (0:18:05)
```
(146 → 153 为新增 test_backend_fix.py 7 项;0 失败,无回归。)

## 3. 提交清单

- `server.py`:F1/F2/F3(一处文件三个独立逻辑块,每块定向测试先行验证后合并提交)
- `tools/restore_backup.py`(新增)、`tests/test_backend_fix.py`(新增 7 项)
- `docs/backend_fix_report.md`(本文件)、`docs/implementation_plan.md`(状态更新)

## 4. 跳过事项(按阶段原则)

- **单账号→多用户隔离**:属架构级改造,方案 A/B/C 待用户决策(上轮已呈报),本轮不动。
- **登录限速**:单实例+8 位密码下风险可接受,且公网经 Cloudflare 中转;记录在案,不做。
- **正常工作模块**(records 幂等、train 状态机、radar 去重):有测试锁定、无缺陷证据,不重构。
