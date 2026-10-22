# AI 使用日志（阶段一）

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
