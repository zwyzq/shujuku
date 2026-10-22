# 阶段一 MongoDB Schema（问卷系统）

数据库：`ecnu10245501461`（本地 mongod，与水杉实验一致）

## users
```js
{
  _id: ObjectId,
  username: String,          // unique
  password_hash: String,     // werkzeug
  email: String,
  created_at: ISODate
}
```

## surveys
```js
{
  _id: ObjectId,
  owner_id: ObjectId,        // -> users
  title: String,
  description: String,
  status: "draft" | "published" | "closed",
  public_token: String,      // 填写链接用，unique
  allow_anonymous: Boolean,  // false 则填写须登录
  deadline: ISODate | null,
  created_at: ISODate,
  updated_at: ISODate,
  published_at: ISODate | null
}
```

## questions
```js
{
  _id: ObjectId,
  survey_id: ObjectId,       // 独立集合，便于阶段二题库迁移
  order: Number,
  type: "single" | "multiple" | "text" | "number" | "rating" | "date",
  title: String,
  required: Boolean,
  options: [                 // single/multiple/rating
    { value: String, label: String }
  ],
  validation: {              // 存数据，不写死在代码
    min_length: Number,
    max_length: Number,
    min: Number,
    max: Number,
    integer: Boolean,
    min_select: Number,
    max_select: Number,
    exact_select: Number,
    pattern: String
  },
  jump_rules: [              // 条件跳转
    { when_value: String|Number|Array, goto_question_id: ObjectId | "end" }
  ],
  created_at: ISODate
}
```

## responses
```js
{
  _id: ObjectId,
  survey_id: ObjectId,
  answers: [
    { question_id: ObjectId, value: Mixed }
  ],
  submitted_at: ISODate,
  meta: { ip: String, user_agent: String }  // 可选
}
```

索引建议：
- users.username unique
- surveys.public_token unique
- surveys.owner_id
- questions.survey_id + order
- responses.survey_id
