# 阶段一测试用例

环境：本地 mongod `localhost:27017`，库 `ecnu10245501461`，服务 `http://127.0.0.1:5001`

自动化：`python tests/smoke_test.py`（服务需已启动）

## TC01 注册登录
- 步骤：打开 `/login` → 注册新用户 → 自动进入列表
- 输入：用户名、密码（≥6 位）
- 期望：`POST /api/auth/register` 201；`GET /api/auth/me` 返回该用户

## TC02 创建问卷
- 步骤：点「新建问卷」
- 输入：标题
- 期望：列表出现草稿；`status=draft`

## TC03 添加题目
- 步骤：编辑页添加单选 / 多选 / 数字填空
- 输入：选项、必填、多选 min/max、数字 min/max/整数
- 期望：题目出现在列表；`GET /api/surveys/<id>` 含 validation

## TC04 发布与链接
- 步骤：至少 1 题后点「发布」
- 期望：`status=published`；生成 `/fill/<token>` 与 `/survey/<token>`

## TC05 跳转逻辑
- 步骤：第 1 题单选，规则 `no -> end`；填写选 no
- 期望：不再出现后续题；提交成功且答卷不含被跳过题

## TC06 校验
- 步骤：必答题不选直接提交；多选超过 max_select；数字超出范围
- 期望：前端提示或 `400 validation failed`

## TC07 提交问卷
- 步骤：按跳转路径答完点提交
- 期望：`201`；`responses` 集合新增文档

## TC08 统计
- 步骤：打开「统计」
- 期望：答卷数正确；单选有分布；填空有 samples；数字有 avg

## TC09 匿名与登录填写
- 关闭「允许匿名」并保存 → 未登录打开填写链接
- 期望：提示需登录并跳转 `/login`
- 打开匿名后无需登录可填

## TC10 截止时间
- 设置过去的截止时间并发布
- 期望：`GET /api/fill/<token>` 返回 `survey expired`
