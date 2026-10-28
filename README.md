# 基于 MongoDB 的问卷系统（阶段一 + 阶段二）

华东师范大学 · 2026 大作业一  
学号：10245501461 · 姓名：钟尉  

仓库：[https://github.com/zwyzq/shujuku](https://github.com/zwyzq/shujuku)

简化版在线问卷（问卷星 / Google Forms 风格）：注册登录、创建问卷、题型与跳转/校验、公开填写、结果统计；**阶段二**增加题库、题目分享、版本历史、发布冻结快照、引用查询与跨问卷统计。  
技术栈：**Python + Flask + pymongo + MongoDB**，前端为简单 HTML/JS。

## 快速运行

```bash
# 1. 依赖
pip install -r requirements.txt

# 2. 配置（复制后按需修改）
cp .env.example .env

# 3. 启动本地 MongoDB（示例路径按本机安装调整）
# mongod --dbpath <你的数据目录> --port 27017 --fork --logpath <日志路径>

# 4. 启动服务
python run.py
```

浏览器打开：http://127.0.0.1:5001/login  

健康检查：http://127.0.0.1:5001/api/health  

题库入口（阶段二）：http://127.0.0.1:5001/bank  

## 功能概览

### 阶段一

- 用户注册 / 登录（Session）
- 问卷 CRUD、发布 / 关闭、公开链接（`/fill/<token>`、`/survey/<token>`）
- 题型：单选、多选、文本/数字填空等；校验规则与跳转规则存 MongoDB
- 填写：支持匿名开关、截止时间；逐题跳转
- 统计：选项分布、文本抽样、数字均值
- 测试：`python tests/smoke_test.py`（需服务已启动）

### 阶段二（题库扩展）

- 题库保存常用题，问卷编辑页「从题库选用」
- 题目分享给指定用户或公开分享
- 版本历史（`question_versions`）与多版本并存；`head_version_id` 指向最新
- 已发布问卷题目冻结；题库修改生成新版本，**不改动旧卷快照**
- 查看某题被哪些问卷引用；单题跨问卷统计

## 目录结构

```
app/           # Flask 后端（含 routes/bank.py）
templates/     # 页面（含 bank.html、bank_item.html）
static/        # 样式与前端脚本
tests/         # 冒烟测试
docs/          # Schema、测试用例、AI 日志、阶段一/二报告
run.py
requirements.txt
.env.example
```

## 文档

| 文件 | 说明 |
|------|------|
| `docs/schema.md` | 阶段一 MongoDB 集合设计 |
| `docs/schema_phase2.md` | 阶段二题库 / 版本扩展 |
| `docs/phase2_change_requests.docx` | 阶段二用户反馈变更说明 |
| `docs/test_cases.md` | 测试用例 |
| `docs/ai_usage_log.md` | AI 使用日志 |
| `docs/phase1_report.md` | 阶段一完成报告 |
| `docs/phase2_report.md` | 阶段二变更完成报告 |

## API 摘要

- 阶段一：`/api/auth`、`/api/surveys`、`/api/questions`、`/api/fill/<token>`  
- 阶段二：`/api/bank/items`、`.../versions`、`.../share`、`.../stats`，以及 `POST /api/surveys/<id>/questions/from-bank`
