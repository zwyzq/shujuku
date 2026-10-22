# 基于 MongoDB 的问卷系统（阶段一）

华东师范大学 · 2026 大作业一 · 第一阶段  
学号：10245501461 · 姓名：钟尉

简化版在线问卷（问卷星 / Google Forms 风格）：注册登录、创建问卷、题型与跳转/校验、公开填写、结果统计。  
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

## 功能概览

- 用户注册 / 登录（Session）
- 问卷 CRUD、发布 / 关闭、公开链接（`/fill/<token>`、`/survey/<token>`）
- 题型：单选、多选、文本/数字填空等；校验规则与跳转规则存 MongoDB
- 填写：支持匿名开关、截止时间；逐题跳转
- 统计：选项分布、文本抽样、数字均值
- 测试：`python tests/smoke_test.py`（需服务已启动）

> 仓库中另含阶段二题库扩展（`/bank`），不影响阶段一验收。

## 目录结构

```
app/           # Flask 后端
templates/     # 页面
static/        # 样式与前端脚本
tests/         # 冒烟测试
docs/          # Schema、测试用例、AI 日志、报告
run.py
requirements.txt
.env.example
```

## 文档

| 文件 | 说明 |
|------|------|
| `docs/schema.md` | MongoDB 集合设计 |
| `docs/test_cases.md` | 测试用例 |
| `docs/ai_usage_log.md` | AI 使用日志 |
| `docs/phase1_report.md` / `.docx` | 阶段一完成报告 |

## API 摘要

见报告或启动后的页面操作；核心前缀：`/api/auth`、`/api/surveys`、`/api/fill/<token>`。
