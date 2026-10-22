# 阶段二 Schema 扩展（在阶段一基础上，不推倒重做）

## 设计原则
- 保留阶段一 `users/surveys/questions/responses` 与全部旧接口。
- 新增题库相关集合；问卷中的 `questions` 可引用某一**题目版本**。
- **已发布问卷中的题目快照不随题库修改而变**：问卷题文档保存当时的 title/options/validation 副本；`bank_version_id` 仅作溯源。
- 修改题库题 → 生成新版本，旧版本仍可被旧问卷引用。

## 新增集合

### question_items（逻辑题目 / 题库条目）
```js
{
  _id: ObjectId,
  owner_id: ObjectId,
  title_hint: String,          // 便于列表展示，通常=最新版题干
  shared_with: [ObjectId],     // 被分享到的用户
  is_public_share: Boolean,    // 可选：是否对所有登录用户可见（默认 false）
  head_version_id: ObjectId,   // 当前最新版本
  created_at, updated_at
}
```

### question_versions（题目版本）
```js
{
  _id: ObjectId,
  item_id: ObjectId,           // -> question_items
  version: Number,             // 1,2,3...
  parent_version_id: ObjectId | null,
  type, title, required, options, validation, jump_rules_template,
  created_at,
  created_by: ObjectId
}
```

## 阶段一 questions 集合增量字段（可选）
```js
{
  // ...原有字段保持...
  bank_item_id: ObjectId | null,
  bank_version_id: ObjectId | null,
  frozen: Boolean   // 问卷已发布后为 true，禁止就地改题干（应走新版本）
}
```

## 跨问卷统计
对某一 `bank_item_id`（或指定 version）：
找到所有 `questions` 引用这些版本 → 聚合对应 `responses.answers`。
