# 软考中级网络工程师题库后端

## 项目介绍

这是一个用于本地/内网部署的软考中级“网络工程师”题库管理后端，支持考试年份管理、题目管理、JSON 导入、刷题、错题本、收藏、统计、Swagger API，以及 DeepSeek v4 辅助导入。

## 技术栈

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PyMySQL
- Pydantic v2
- python-dotenv
- Uvicorn
- DeepSeek OpenAI-compatible Chat Completions API

## 环境准备

创建虚拟环境：

```bash
python -m venv .venv
```

激活虚拟环境：

Windows:

```bat
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 数据库配置

复制配置：

```bash
cp .env.example .env
```

编辑配置：

```bash
nano .env
```

`.env` 中需要填写 MySQL 管理员密码、业务用户密码。管理员连接只用于初始化数据库、创建业务用户和授权；后端运行时只使用业务用户 `rk_bank` 连接 `rk_network_engineer`。

DeepSeek v4 是可选能力。未配置 `DEEPSEEK_API_KEY` 时，普通题库 API 不受影响，AI 辅助接口会返回明确配置提示。

## 一键初始化数据库

```bash
python scripts/init_database.py
```

初始化脚本会完成：

- 创建数据库 `rk_network_engineer`
- 创建业务用户 `rk_bank`
- 授权业务库权限
- 创建业务表
- 写入预置标签
- 导入样例数据

脚本可重复执行，不会重复插入相同题目。

## 启动后端

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 导入 JSON 样例

```bash
python scripts/import_json.py data/samples/2024_spring_morning_sample.json
```

更新重复题的答案、解析、标签和难度：

```bash
python scripts/import_json.py data/samples/2024_spring_morning_sample.json --update-existing
```

## API 文档入口

```text
http://127.0.0.1:8000/docs
```

## curl 示例

查询题目：

```bash
curl "http://127.0.0.1:8000/api/questions?year=2024&tag=TCP%2FIP"
```

只看有答案的可练习题：

```bash
curl "http://127.0.0.1:8000/api/questions?has_answer=true"
```

随机刷题：

```bash
curl "http://127.0.0.1:8000/api/practice/random?limit=5"
```

提交答案：

```bash
curl -X POST "http://127.0.0.1:8000/api/practice/submit" \
  -H "Content-Type: application/json" \
  -d "{\"question_id\":1,\"user_answer\":\"B\",\"duration_seconds\":30}"
```

AI 提取题目草稿：

```bash
curl -X POST "http://127.0.0.1:8000/api/ai/extract-questions" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"题干和选项文本\",\"exam\":{\"exam_name\":\"网络工程师\",\"level\":\"中级\",\"year\":2024,\"season\":\"上半年\",\"paper_type\":\"上午综合知识\"}}"
```

AI 生成模拟题草稿：

```bash
curl -X POST "http://127.0.0.1:8000/api/ai/generate-questions" \
  -H "Content-Type: application/json" \
  -d "{\"exam\":{\"exam_name\":\"网络工程师\",\"level\":\"中级\",\"year\":2026,\"season\":\"上半年\",\"paper_type\":\"上午综合知识\",\"source_name\":\"DeepSeek AI 生成\"},\"question_count\":5,\"question_types\":[\"single_choice\"],\"difficulty\":3,\"knowledge_areas\":[\"TCP/IP\",\"路由协议\"],\"tags\":[\"网络基础\"]}"
```

导入 AI 生成题：

```bash
curl -X POST "http://127.0.0.1:8000/api/import/ai-generated" \
  -H "Content-Type: application/json" \
  -d @ai_generated_draft.json
```

## DeepSeek v4 辅助导入

AI 功能只处理用户提供、公开授权或合法取得的文本、URL 或 JSON 草稿。系统不会绕过登录、付费墙、验证码或反爬限制，也不会自动批量复制未知版权题库。

DeepSeek 默认配置：

- `DEEPSEEK_MODEL=deepseek-v4-flash`
- `DEEPSEEK_REASONING_MODEL=deepseek-v4-pro`

AI 输出会经过 Pydantic schema 校验，导入时默认标记为 `is_verified=false`，建议人工校对后再标记为已验证。

AI 生成题会使用 `source_type=ai-generated` 记录导入批次，题目默认未校对，不能当作历年真题标注。

## 合规来源采集脚本

采集脚本只处理你明确提供的 URL 或 URL 列表，默认尊重 `robots.txt`，不绕过登录、付费墙、验证码或反爬限制，不会自动入库。原始采集内容写入 `data/sources/`，该目录已加入 `.gitignore`。

单个 URL：

```bash
python scripts/crawl_sources.py --url "https://example.com/page.html" --confirm-legal
```

URL 列表：

```bash
python scripts/crawl_sources.py --url-file data/source_urls.txt --max-pages 20 --confirm-legal
```

跟随同域名链接：

```bash
python scripts/crawl_sources.py --url "https://example.com/index.html" --follow-links --max-pages 30 --delay 2 --confirm-legal
```

把采集结果交给 DeepSeek v4 生成未校对 JSON 草稿：

```bash
python scripts/ai_extract_sources.py data/sources/crawl_YYYYMMDD_HHMMSS.jsonl --year 2024 --season 上半年 --paper-type 上午综合知识 --confirm-legal
```

生成草稿后直接入库：

```bash
python scripts/ai_extract_sources.py data/sources/crawl_YYYYMMDD_HHMMSS.jsonl --year 2024 --confirm-legal --import-to-db
```

建议先检查 AI 生成的草稿 JSON，再通过 API 或 `scripts/import_json.py` 入库。

## 全网候选一条龙

全网候选脚本通过搜索 API 发现候选 URL，然后按“搜索候选 -> robots 合规抓取 -> DeepSeek 来源审核 -> DeepSeek 结构化 -> 可选入库”执行。DeepSeek 不能替代版权判断，所以未知来源默认只生成草稿；只有满足以下任一条件才会自动入库：

- 来源域名通过 `--allow-domain` 明确加入允许列表。
- 页面正文有明确开放授权信号，且 DeepSeek 审核为低风险可结构化。
- 你显式传入 `--auto-approve`，表示你确认这些候选来源可以自动入库。

推荐使用自建 SearXNG：

```env
SEARCH_PROVIDER=searxng
SEARXNG_BASE_URL=http://127.0.0.1:8080
```

也可以使用 Bing Search API：

```env
SEARCH_PROVIDER=bing
BING_SEARCH_API_KEY=请在本地 .env 中填写
BING_SEARCH_ENDPOINT=https://api.bing.microsoft.com/v7.0/search
```

只审核不结构化入库：

```bash
python scripts/web_search_pipeline.py --year 2024 --season 上半年 --paper-type 上午综合知识 --dry-run --confirm-legal
```

生成草稿，等待人工确认：

```bash
python scripts/web_search_pipeline.py --year 2024 --season 上半年 --paper-type 上午综合知识 --confirm-legal
```

允许指定域名自动入库：

```bash
python scripts/web_search_pipeline.py --year 2024 --season 上半年 --paper-type 上午综合知识 --allow-domain example.com --confirm-legal
```

确认候选来源可自动入库：

```bash
python scripts/web_search_pipeline.py --year 2024 --season 上半年 --paper-type 上午综合知识 --auto-approve --confirm-legal
```

脚本日志和草稿默认写入 `data/web_pipeline/`，该目录不会提交。

## Gitee 授权资料导入

如果你确认 `https://gitee.com/zaonai/network_engineer` 仓库及其中资料的授权允许本地学习整理，可先把仓库克隆到 `data/sources/gitee_zaonai_network_engineer/`，再用脚本从历年真题 PDF 抽取文本、调用 DeepSeek 结构化，并按年份、上/下半年、上午/下午卷别入库。

```bash
git clone https://gitee.com/zaonai/network_engineer data/sources/gitee_zaonai_network_engineer
python scripts/import_gitee_network_engineer.py --years 2009-2024 --confirm-license --update-existing --skip-existing-exams --max-chars 20000
```

导入日志和 AI 草稿默认写入 `data/gitee_imports/`，该目录不会提交。AI 结构化结果仍会标记为未人工校对，建议验收时抽查题干、答案和解析。

脚本默认要求自动入库草稿的答案覆盖率不低于 60%，否则只保存草稿并跳过入库，避免无答案 PDF 抽取结果污染题库。可用 `python scripts/audit_question_quality.py --json` 查看当前题库质量统计。

## Docker Compose

本项目不创建 MySQL 容器，只启动后端服务，并通过 `.env` 连接远程 MySQL。

```bash
docker compose up --build
```

## 合规声明

本项目仅用于个人学习、资料整理和题库管理。
真题内容、解析、PDF、扫描件等资料的版权归原权利方所有。
请仅导入自己整理、公开授权或合法取得的数据。

## 常见问题

### 初始化提示 DB_PASSWORD 无效

请在 `.env` 中填写长度至少 12 位的业务用户密码。密码不能包含单引号、反斜杠或换行。

### AI 接口提示未配置

请在 `.env` 中填写 `DEEPSEEK_API_KEY`。不使用 AI 功能时可以忽略。

### 中文乱码

请确认 JSON 文件使用 UTF-8 编码，MySQL 数据库使用 `utf8mb4` 字符集。
