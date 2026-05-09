# 软考多科目题库系统

本项目已经从“网络工程师单科题库”改为“高级 / 中级 / 初级多科目题库系统”。后端使用 FastAPI + SQLAlchemy + MySQL，前端使用 Vue 3 + Element Plus。系统支持科目分栏、题库查询、刷题、错题、收藏、基础用户系统、访客 session、DeepSeek 辅助导入和数据清理。

## 快速启动

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
python scripts/init_database.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd frontend
npm install
npm run dev
```

入口：

- 后端 Swagger: `http://127.0.0.1:8000/docs`
- 前端: `http://127.0.0.1:5173`

## 当前能力

- 科目：`GET /api/subjects`、`GET /api/subjects/grouped`
- 认证：注册、登录、退出、访客 session
- 题库：按级别、科目、年份、标签、质量状态、答案状态过滤
- 练习：随机刷题、按标签刷题、错题练习
- 复盘：错题记录和收藏按登录用户或访客 session 隔离
- 清理：`POST /api/admin/cleanup/preview`、`POST /api/admin/cleanup/apply`
- 导入：JSON、AI JSON、AI 生成题、try-learning 草稿质量门槛

写入类题库接口需要 `admin` 角色登录；普通用户和访客只保留刷题、收藏、错题记录等个人数据能力。

## try-learning 数据源

try-learning 是 SPA 页面，公开 HTML 只提供 JS 外壳。项目提供两类脚本：

```bash
cd backend
python scripts/crawl_try_learning.py --all-subjects --confirm-public-source
python scripts/import_try_learning.py --candidate-no 1234 --all-subjects --confirm-public-source
python scripts/capture_try_learning_browser.py --candidate-no 1234 --subject-code wlgcs --promote --confirm-public-source --headless
python scripts/run_try_learning_pipeline.py --candidate-no 1234 --all-subjects --confirm-public-source
```

浏览器脚本按这个公开流程执行：`#/LoginView` 输入准考证号 `1234`，进入 `#/SelectSubject` 选择科目，再到 `#/MockPrinciple` 点击阅读同意，最后在 `#/UserInfo` 确认进入考试并捕获 XHR/JSON。

导入脚本会先做质量门槛：答案覆盖率、选项完整率、图片完整率、重复率。当前公开 JSON 没有答案字段，因此默认只保存草稿和质量报告到 `backend/data/try_learning/drafts/`，不会污染正式题库。只有明确传入 `--allow-unanswered` 才会允许无答案题以非 `ok` 状态入库。题干和选项图片会记录到 `question_images`，下载后的图片通过 `/static/data/...` 访问。

浏览器捕获需要 Playwright 浏览器内核：

```bash
cd backend
python -m playwright install chromium
```

AI 推断答案是独立步骤，结果默认标记 `quality_status=ai_answered` 且 `is_verified=false`：

```bash
python scripts/enrich_try_learning_answers.py --only wlgcs --limit 20 --use-search --confirm-ai-answers
```

## 数据清理

清理会先备份当前题库到：

```text
backend/data/exports/cleanup_backup_*.json
```

默认建议先隔离为 `quality_status=low_quality`，前端题库和刷题默认只显示 `quality_status=ok` 且有答案的题。

## 合规边界

只处理自整理、公开授权或合法取得的数据。不绕过登录、付费墙、验证码或反爬限制；不自动批量复制未知版权题库。DeepSeek 结果默认 `is_verified=false`，需要人工确认后再作为可用题维护。
