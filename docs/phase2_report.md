# 基于 MongoDB 的问卷系统 · 阶段二变更完成报告

> **GitHub 仓库链接：** [https://github.com/zwyzq/shujuku](https://github.com/zwyzq/shujuku)

- 学号：10245501461  
- 姓名：钟尉  
- 课程：MongoDB 相关课程大作业一 · 第二阶段（需求变更）  
- 日期：2026-10-28  
- 代码目录：`~/Desktop/mongodb-survey`  
- 技术栈：Python / Flask / pymongo / MongoDB 6 / 简单 HTML+JS 前端  
- 说明：本阶段在**阶段一系统之上扩展**，不推倒重做；演示题目仅为功能验收用的占位内容，不要求题目文案具有业务含义。

---

## 1. 阶段目标（相对阶段一）

阶段一已实现：账号、问卷 CRUD、多题型、跳转与校验、公开填写、单卷统计。  
阶段二根据「上线后用户反馈」做题库化改造，核心诉求是：

1. 题目可保存、复用、分享；  
2. 修改题库**不得破坏**已发布问卷的历史题面与数据对齐；  
3. 题目有版本历史，多版本可并存；  
4. 能查看某题被哪些问卷引用，以及该题在**跨问卷**维度上的统计。

界面仍保持简单可用；考察重点仍是 **MongoDB 文档模型与一致性取舍**。

---

## 2. 八项变更需求对照表

| # | 用户反馈要点 | 实现方式 | 入口 / API |
|---|--------------|----------|------------|
| 1 | 保存常用题，新建问卷直接选用 | `question_items` + `question_versions`；编辑页「从题库选用」把某版本**快照**写入本卷 `questions` | 页面 `/bank`；`POST /api/bank/items`；`POST /api/surveys/<id>/questions/from-bank` |
| 2 | 题目分享给他人使用 | 题库条目 `shared_with`（按用户名添加）与 `is_public_share`；列表按所有者 / 被分享 / 公开可见过滤 | 题详情页分享区；`POST /api/bank/items/<id>/share` |
| 3 | 改题不影响已做好的问卷 | 问卷内保存题干/选项等**副本**；发布时 `frozen=true`；已发布/冻结题禁止就地 PATCH | `surveys.publish` 批量冻结；`questions` 更新拦截 |
| 4 | 记录修改历史、知道从哪一版改来 | 每次「新建版本」插入新文档，带 `version`、`parent_version_id` | `POST /api/bank/items/<id>/versions`；详情页版本列表 |
| 5 | 同一题多版本同时存在 | 旧版本文档保留；不同问卷可引用不同 `bank_version_id` | 选用时指定 `version_id`；item 上 `head_version_id` 仅表示最新 |
| 6 | 查看某题被哪些问卷使用 | 按 `bank_item_id` 反查 `questions`，附问卷标题与所用版本 | `GET /api/bank/items/<id>` 返回 `used_by` |
| 7 | 建立题库并管理 | 独立题库页：列表、新建、详情、版本、分享 | `/bank`、`/bank/<item_id>` |
| 8 | 单题跨问卷统计 | 聚合所有引用该 `bank_item_id` 的答卷答案，输出分布 / 数值汇总 / 文本抽样 | `GET /api/bank/items/<id>/stats` |

以上 8 点均在本地演示路径中走通（登录 → 题库建题 → 分享/新建版本 → 问卷选用 → 发布 → 再改题库 → 旧卷题面不变 → 查看引用与跨卷统计）。

---

## 3. MongoDB Schema 变更与理由

### 3.1 保留阶段一集合

继续使用：`users`、`surveys`、`questions`、`responses`。旧接口与阶段一填写/统计逻辑不变。

### 3.2 新增集合

**`question_items`（逻辑题目 / 题库条目）**

- 表示「一道可复用的题」这一实体，不绑死某个问卷。  
- 字段要点：`owner_id`、`title_hint`、`shared_with`、`is_public_share`、`head_version_id`。

**`question_versions`（题目版本）**

- 不可变内容快照链：`item_id`、`version`、`parent_version_id`、`type` / `title` / `options` / `validation` 等。  
- 修改题库 = **追加新版本**，而不是覆盖旧文档。

详细字段见 `docs/schema_phase2.md`。

### 3.3 `questions` 增量字段

| 字段 | 含义 |
|------|------|
| `bank_item_id` | 溯源到题库逻辑题（可空，兼容阶段一手写题） |
| `bank_version_id` | 溯源到具体版本 |
| `frozen` | 发布后为 true，禁止就地改题干 |

问卷题文档仍保存当时的 `title`、`options`、`validation` 等，形成**问卷侧快照**：题库再怎么升版本，已写入本卷的字段不会自动跟着变。

### 3.4 为何这样适合 MongoDB

1. **版本是文档**：一版一行，天然适合追加式历史，不必做复杂的历史表 JOIN。  
2. **多态题型**继续落在版本文档与问卷快照上，形状随题型变化。  
3. **引用查询简单**：`questions.find({ bank_item_id })` 即可回答「谁在用这道题」。  
4. **跨卷统计**：先找引用该 item 的 `question_id` 集合，再扫 `responses.answers`，文档模型下异构 `value` 仍可统一处理。

阶段一只把题目做成独立集合，正是为了本阶段不必从「嵌在 survey 数组里」整体推翻。

---

## 4. 冻结 / 快照设计

```
题库 item ──head──► version vN
                      │
        from-bank 拷贝快照
                      ▼
问卷 questions 文档（title/options/... + bank_* + frozen?）
                      │
              发布时 frozen=true
                      │
         禁止 PATCH 就地改题干
```

要点：

1. **选用即拷贝**：`from-bank` 把版本内容写入本卷 `questions`，并记录 `bank_item_id` / `bank_version_id`。  
2. **发布即冻结**：`publish` 时对该卷所有题 `frozen=true`。  
3. **改题走新版本**：题库侧 `POST .../versions`；若要把新表述用到新问卷，再选用新版本；旧卷保持旧快照。  
4. **答卷仍按问卷内 `question_id` 存储**：统计与跳转逻辑与阶段一一致；跨卷统计额外按 `bank_item_id` 聚合。

这样同时满足「复用」与「去年问卷不能因为今年改题而变」。

---

## 5. 版本关系（版本图）

创建条目时生成 `v1`（`parent_version_id = null`）。  
每次「新建版本」：

- `version = max(version)+1`  
- `parent_version_id = 指定父版本或当前 head`  
- 更新 item 的 `head_version_id` 与 `title_hint`

示意：

```
v1 ──► v2 ──► v3   （head 指向 v3）
 ▲       ▲
 │       └── 问卷 B 可引用 v2
 └── 问卷 A 可引用 v1（快照已冻结）
```

详情页列出全部版本及父子关系，便于回溯「现在这题是从哪一版改来的」。  
（本实现以「新建版本」为主路径；选用旧版本加入新卷即可达到「恢复/沿用旧表述」的效果。）

---

## 6. 页面与 API 摘要

### 6.1 页面

| 路径 | 说明 |
|------|------|
| `/bank` | 题库列表、新建常用题 |
| `/bank/<item_id>` | 版本历史、分享、被引用问卷、跨卷统计 |
| `/surveys/<id>`（编辑页） | 「从题库选用」下拉 + 加入本卷（阶段一能力保留） |

### 6.2 阶段二 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/bank/items` | 我的 / 被分享 / 公开题库列表 |
| POST | `/api/bank/items` | 创建题库题（同时生成 v1） |
| GET | `/api/bank/items/<id>` | 详情、版本列表、`used_by` 引用 |
| POST | `/api/bank/items/<id>/versions` | 基于父版本新建版本 |
| POST | `/api/bank/items/<id>/share` | 按用户名分享或切换公开分享 |
| POST | `/api/surveys/<id>/questions/from-bank` | 从指定版本拷贝进问卷 |
| GET | `/api/bank/items/<id>/stats` | 跨问卷答题分布 / 数值 / 抽样 |

阶段一原有 `/api/auth`、`/api/surveys`、`/api/questions`、`/api/fill` 等保持可用。

---

## 7. 测试与验收说明

未编造量化指标。本阶段以**手工主路径验收**为主（与阶段一冒烟脚本互补）：

1. 注册/登录后进入题库，新建题目并保存。  
2. 在题详情中分享给另一用户或开启公开分享；对方题库列表可见。  
3. 「新建版本」修改题干后，版本列表出现 v2，且带父版本信息。  
4. 在未发布问卷中「从题库选用」加入题目并发布。  
5. 再次在题库新建版本后，**已发布问卷编辑页中题干仍为旧快照**；对冻结题就地修改被拒绝。  
6. 题详情「被哪些问卷使用」列出引用；跨卷统计页能汇总多卷答案（有答卷时）。

自动化：阶段一 `python tests/smoke_test.py` 仍可用于主问卷链路；题库接口可在服务启动后按上表用浏览器或 HTTP 客户端复核。

演示题目文案可为占位内容（如随意中文题干），不影响对模型与行为的评判。

---

## 8. AI 使用说明（阶段二）

详细流水见 `docs/ai_usage_log.md`（已追加阶段二行）。

### 8.1 AI 帮了什么

- 按八条用户反馈映射到集合拆分（item / version）与冻结策略。  
- 实现 `bank` 路由、题库页面、编辑页「从题库选用」、跨卷统计聚合。  
- 整理本变更报告结构，并与阶段一报告体例对齐。

### 8.2 我如何核验 / 调整

- 坚持「拷贝快照 + frozen」，拒绝「问卷题直接引用可变题库文档」以免改库牵动旧卷。  
- 发布时批量冻结；PATCH 拦截给出明确错误，引导走新版本。  
- 本地启动 mongod / Flask，按第 7 节路径手工点通后再写本报告。

### 8.3 自己把握的设计点

- item 与 version 两集合分离，head 指针表示最新但不删除旧版。  
- `used_by` 与跨卷 stats 都基于 `bank_item_id`，与答卷 `question_id` 解耦清晰。  
- 阶段一手写题无 bank 字段仍可正常使用，兼容旧数据。

---

## 9. 遇到的问题与解决

| 问题 | 解决 |
|------|------|
| 若问卷题只存 version 引用、不存副本，改库会牵动旧卷 | 选用时拷贝 title/options 等到 `questions`，version id 仅溯源 |
| 已发布卷仍允许改题会破坏统计语义 | `frozen` + 发布时批量设置；更新接口拒绝就地修改 |
| 分享后对方看不到 | 列表查询 `$or`：所有者 / `shared_with` / `is_public_share` |
| Mac 上 Flask/Mongo 端口占用 | 先检查 27017/5001 是否已有进程，避免重复启动 |

---

## 10. 运行说明（验收用）

```bash
# 若 mongod 未在跑（端口 27017）
~/Software/MongoDB/mongodb-macos-aarch64-6.0.1/bin/mongod \
  --dbpath ~/Software_Data/MongoDB/data/testdb \
  --port 27017 --fork \
  --logpath ~/Software_Data/MongoDB/log/mongod.log

cd ~/Desktop/mongodb-survey
python run.py
```

浏览器：http://127.0.0.1:5001/login  

演示建议：登录 → **题库**建题 → 详情页分享 / 新建版本 → 新建问卷 → **从题库选用** → 发布 → 再改题库版本 → 确认旧卷不变 → 查看引用与跨卷统计。

---

## 11. 阶段二交付清单

| 提交项 | 位置 |
|--------|------|
| 扩展后的后端与前端 | 项目根目录（含 `app/routes/bank.py`、`templates/bank*.html`） |
| Schema（阶段一 + 二） | `docs/schema.md`、`docs/schema_phase2.md` |
| 变更需求原文 | `docs/phase2_change_requests.docx` |
| 配置与运行说明 | `README.md` |
| AI 使用日志 | `docs/ai_usage_log.md` |
| 本变更完成报告 | `docs/phase2_report.md`；PDF：`2026_ECNU_PJ1_2_钟尉.pdf` |
| 代码仓库 | https://github.com/zwyzq/shujuku |

---

（报告正文完）
