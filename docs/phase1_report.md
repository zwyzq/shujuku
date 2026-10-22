# 基于 MongoDB 的问卷系统 · 阶段一项目完成报告

> **GitHub 仓库链接：** [https://github.com/zwyzq/shujuku](https://github.com/zwyzq/shujuku)

- 学号：10245501461  
- 姓名：钟尉  
- 课程：MongoDB 相关课程大作业一 · 第一阶段  
- 日期：2026-10-22  
- 代码目录：`~/Desktop/mongodb-survey`  
- 技术栈：Python / Flask / pymongo / MongoDB 6 / 简单 HTML+JS 前端  

---

## 1. 项目目标

实现一个简化版在线问卷系统（类似问卷星 / Google Forms）：注册用户可创建与管理问卷，通过 URL 分发；填写者按规则答题并提交；创建者可查看统计。

本阶段重点考察 MongoDB 设计、后端业务逻辑（尤其是跳转与校验）、文档与 AI 使用规范。界面仅需简单可用。

## 2. 系统设计概述

### 2.1 总体结构

```
浏览器（简单网页）
    ↓ HTTP / Session Cookie
Flask 后端（REST API + 页面路由）
    ↓ pymongo
MongoDB（库 ecnu10245501461）
```

- **页面**：`/` 我的问卷、`/login` 登录注册、`/surveys/<id>` 编辑、`/surveys/<id>/stats` 统计、`/fill/<token>` 与 `/survey/<token>` 填写。  
- **API**：`/api/auth/*`、`/api/surveys/*`、`/api/questions/*`、`/api/fill/<token>`、`/api/health`。  
- **会话**：Flask session 保存 `user_id`；密码使用 werkzeug 哈希，不明文存储。

### 2.2 功能模块

| 模块 | 能力 |
|------|------|
| 账号 | 注册、登录、登出、查看当前用户；用户只能看到自己的问卷 |
| 问卷 | 创建/编辑标题说明、匿名开关、截止时间、发布/关闭/重开、删除 |
| 题目 | 单选、多选、文本填空、数字填空（及扩展：评分、日期）；必填；选项；校验规则；跳转规则 |
| 填写 | 公开链接；匿名或需登录；逐题跳转；校验失败提示；保存答卷 |
| 统计 | 答卷总数；单选/多选/评分分布；文本抽样；数字均值/最值 |

## 3. MongoDB 设计

### 3.1 集合划分

采用 **四个集合**，而不是把所有内容塞进一个文档：

1. `users` — 账号  
2. `surveys` — 问卷元数据与发布状态  
3. `questions` — 题目（按 `survey_id` 归属，**独立集合**）  
4. `responses` — 答卷  

详细字段见 `docs/schema.md`。

### 3.2 为什么适合 MongoDB（而非强行用关系表结构）

1. **题目多态**：单选/多选/填空等字段形状不同（options、validation 各异），用文档比多表 JOIN 更自然。  
2. **跳转与校验是数据**：`jump_rules`、`validation` 存在题目文档中，问卷配置变化不必改代码分支写死。  
3. **答卷异构**：`answers[].value` 可为字符串、数字或数组，文档模型表达成本低。  
4. **为阶段二预留**：题目独立集合，后续题库复用、版本、共享时可扩展，而不必从「嵌在 survey 里的数组」整体推翻。

### 3.3 关键索引

- `users.username` 唯一  
- `surveys.public_token` 唯一（sparse）  
- `surveys.owner_id`  
- `questions (survey_id, order)`  
- `responses.survey_id`  

启动时在 `app/db.py` 中自动确保。

### 3.4 冗余与一致性取舍

- 答卷中保存 `question_id` + `value`，不冗余拷贝整道题干，避免题目修改后统计对不齐题意时难以追踪；统计时再关联 `questions`。  
- 发布后生成 `public_token`，关闭问卷不删除 token，便于「重新开放」仍用原链接。

## 4. 跳转设计

### 4.1 存储

每道题可有 `jump_rules` 数组：

```js
{ when_value: <匹配值或数字条件>, goto_question_id: ObjectId | "end" }
```

- 单选/多选：`when_value` 为选项 `value`（多选支持「包含」匹配）。  
- 数字填空：支持 `{ op: ">=", value: 18 }` 等形式。  
- 无匹配规则时，默认进入顺序下一题；无下一题则结束。

跳转规则由用户在编辑页配置（如 `no -> end`），**不写死在业务代码**。

### 4.2 运行时

1. **填写页（前端）**：按当前答案解析下一题 id，逐题展示，选「结束」则显示提交。  
2. **提交（后端）**：用同一套可达性算法计算本应回答的题目集合，只校验可达题；跳过题不要求作答。  

这样前后端规则一致，避免「页面跳过了但服务端仍报必填」。

## 5. 校验设计

校验规则存放在 `questions.validation`，提交时按题型解释：

| 题型 | 规则示例 |
|------|----------|
| 单选/评分 | 值必须在 options 中；必填 |
| 多选 | 子集合法；`min_select` / `max_select` / `exact_select` |
| 文本 | `min_length` / `max_length` / `pattern` |
| 数字 | `min` / `max` / `integer` |
| 日期 | `YYYY-MM-DD` |

问卷级：`status` 须为 published；未过 `deadline`；若 `allow_anonymous=false` 则填写须登录。

## 6. API 说明（摘要）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录 |
| POST | /api/auth/logout | 登出 |
| GET | /api/auth/me | 当前用户 |
| GET/POST | /api/surveys/ | 列表 / 创建 |
| GET/PATCH/DELETE | /api/surveys/\<id\> | 详情（含题）/ 更新 / 删除 |
| POST | /api/surveys/\<id\>/publish\|close\|reopen | 发布 / 关闭 / 重开 |
| POST | /api/surveys/\<id\>/questions | 加题 |
| PATCH/DELETE | /api/questions/\<id\> | 改题 / 删题 |
| GET | /api/surveys/\<id\>/stats | 统计 |
| GET/POST | /api/fill/\<token\> | 拉取填写数据 / 提交 |
| GET | /api/health | 连库健康检查 |

完整启动方式见根目录 `README.md`。

## 7. 测试结果

测试用例清单见 `docs/test_cases.md`。

自动化冒烟：`python tests/smoke_test.py`  
覆盖：注册 → 建卷 → 加题（含跳转 end）→ 发布 → 两次提交（含跳过）→ 统计。

手工/脚本补充：

- 关闭匿名后未登录访问填写 API → `401 login required to fill`  
- 截止时间已过 → `403 survey expired`  
- 浏览器主路径：登录、新建、加题、发布、另开窗口填写、查看统计 — 已通过  

结论：阶段一需求中的账号、问卷管理、三类核心题型、跳转、校验、填写、统计均已实现并可演示。

## 8. AI 使用过程说明

详细流水见 `docs/ai_usage_log.md`。

### 8.1 AI 帮了什么

- 快速搭好 Flask 目录与 Mongo 连接、索引。  
- 根据需求草拟 schema 与 REST 接口骨架。  
- 生成简单前端页面，缩短「能点着演示」的时间。  
- 协助对照需求文档查漏（匿名、截止、登录门禁等）。

### 8.2 AI 不足之处 / 我改了什么

- 最初 `Flask(__name__)` 默认找 `app/templates`，页面 500；改为显式 `template_folder`/`static_folder`。  
- 题目若嵌在 survey 内不利于阶段二；坚持 **questions 独立集合**。  
- 填写页初版整页列出所有题，后改为 **逐题 + 跳转**，与后端可达性一致。  
- 补充多选数量限制、整数数字题、匿名/截止等需求明文要求的字段。

### 8.3 自己设计的部分

- 四集合划分与索引策略。  
- 「跳转与校验数据化」原则及前后端同一套匹配语义。  
- 发布 token 保留以便 reopen；删除问卷级联清理。  
- 库名与本地 mongod 沿用课程实验环境，降低提交与验收成本。

## 9. 遇到的问题与解决

| 问题 | 解决 |
|------|------|
| Mac 重启后 mongod 未自启 | 使用 `--fork` 手动启动；README 写明命令 |
| 模板找不到 | 指定项目根下 templates/static |
| 发布与填写 API 路径和页面抢路由 | 页面 `/fill/<token>`，API 改为 `/api/fill/<token>`，并增加 `/survey/<token>` 别名 |
| 跳过题仍被当成必填 | 提交前计算 reachable 集合，只校验可达题 |

## 10. 运行说明（验收用）

```bash
# 启动 MongoDB（若未在跑）
~/Software/MongoDB/mongodb-macos-aarch64-6.0.1/bin/mongod \
  --dbpath ~/Software_Data/MongoDB/data/testdb \
  --port 27017 --fork \
  --logpath ~/Software_Data/MongoDB/log/mongod.log

cd ~/Desktop/mongodb-survey
python run.py
```

浏览器打开：http://127.0.0.1:5001/login  

演示建议路径：注册/登录 → 新建问卷 → 添加单选（配置跳转）与填空 → 发布 → 复制填写链接 → 提交 → 统计页查看。

## 11. 阶段一交付清单

| 提交项 | 位置 |
|--------|------|
| 后端与前端代码 | 项目根目录 |
| MongoDB schema | `docs/schema.md` |
| 配置说明 | `README.md`、`.env` |
| API/系统说明 | 本报告第 2、6 节；`README.md` |
| 测试用例 | `docs/test_cases.md`、`tests/smoke_test.py` |
| AI 使用日志 | `docs/ai_usage_log.md` |
| 项目完成报告 | 本文件 `docs/phase1_report.md` |

## 12. 阶段二展望（未实现，仅说明设计预留）

需求变更将引入题库、共享、题目版本与跨问卷统计。当前将 `questions` 独立存放，并在答卷中引用 `question_id`，是为了在 **不推倒重做** 的前提下扩展：后续可增加 `question_bank` / `question_versions` 等集合，问卷改为引用某一版本 id，旧问卷快照不受新版本影响。

---

（报告正文完）