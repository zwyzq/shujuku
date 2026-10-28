# AI 使用日志（阶段一 + 阶段二）

使用工具：Grok Bot / Cursor 助手（对话式编程）

| 日期 | 环节 | 提示词摘要 | AI 产出 | 我如何核验/修改 |
|------|------|------------|---------|-----------------|
| 2026-10-22 | Schema | 按问卷星类需求设计 MongoDB 集合，并考虑阶段二题库扩展 | 提出 users/surveys/questions/responses 四集合；questions 独立于 surveys | 确认采用；拒绝把题目嵌进 survey 文档，方便阶段二复用 |
| 2026-10-22 | 技术选型 | 后端用什么合适 | 建议 Flask + pymongo | 采用；连本地 mongod，库名沿用实验 `ecnu10245501461` |
| 2026-10-22 | 骨架 | 搭 Flask 项目并连库、建索引 | 生成 app 包、health/auth 路由、requirements | 实测 `/api/health`；修正 template_folder 指向项目根目录 |
| 2026-10-22 | 问卷 API | 实现 CRUD、发布、公开链接 | surveys 路由、public_token、publish/close | 空问卷禁止发布；删除时级联删题目与答卷 |
| 2026-10-22 | 题目/跳转/校验 | 多题型 + jump_rules + validation 存库不写死 | questions 路由；fill 校验与可达题计算 | 补充多选 min/max_select、数字 integer；跳转支持数字比较 |
| 2026-10-22 | 填写与统计 | 提交答卷与按题统计 | fill POST、stats 分布/抽样/均值 | 冒烟脚本覆盖跳转结束路径 |
| 2026-10-22 | 前端 | 简单网页走通主流程 | login/列表/编辑/填写/统计五页 | 填写改为逐题跳转；编辑页可配匿名、截止、跳转规则 |
| 2026-10-22 | 需求对照 | 对照《大作业一第一阶段》查漏 | 补 allow_anonymous、deadline、登录填写门禁、/survey/ 别名 | 用未登录访问与过期截止分别测 401/403 |
| 2026-10-22 | 测试文档 | 整理测试用例与报告结构 | test_cases.md、本日志、完成报告 | 人工走查 + `tests/smoke_test.py` |

| 2026-10-28 | 阶段二需求映射 | 对照八条用户反馈设计 item/version 与冻结策略 | 提出 question_items + question_versions；问卷题快照 + frozen | 采纳；拒绝问卷题只存可变引用 |
| 2026-10-28 | 题库后端 | 实现列表/创建/版本/分享/from-bank/跨卷统计 | 生成 app/routes/bank.py 与索引扩展 | 本地手工测分享可见性与冻结拦截 |
| 2026-10-28 | 题库前端 | 题库页、详情页、编辑页选用 | templates/bank.html、bank_item.html；survey_edit 下拉 | 点通主路径；确认旧卷题干不随新版本变 |
| 2026-10-28 | 阶段二报告 | 写变更完成报告并导出 PDF | phase2_report.md、README 更新、本日志追加 | 对照变更说明逐条核对后定稿 |
