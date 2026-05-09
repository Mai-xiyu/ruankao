# 后端说明

FastAPI 后端提供多科目软考题库 API、用户认证、访客 session、导入、清理、统计和 DeepSeek 辅助接口。

## 初始化

```bash
pip install -r requirements.txt
copy .env.example .env
python scripts/init_database.py
python scripts/migrate_schema.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`init_database.py` 会创建数据库和业务账号、创建缺失表、执行幂等迁移、写入预置标签并导入样例数据。真实密码和 API Key 只写入本地 `.env`。

## 主要 API

- `GET /api/subjects?level=中级`
- `GET /api/subjects/grouped`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/guest-session`
- `GET /api/questions?level=中级&subject_id=1&quality_status=ok&has_answer=true`
- `GET /api/practice/random?subject_id=1`
- `POST /api/admin/cleanup/preview`
- `POST /api/admin/cleanup/apply`
- `GET /api/admin/import-batches`

写入类题库接口（导入、清理、创建/更新/删除题目、考试、科目、标签）需要已登录的 `admin` 角色；普通用户和访客只能刷题、收藏、记录错题。

## try-learning

```bash
python scripts/crawl_try_learning.py --all-subjects --confirm-public-source
python scripts/import_try_learning.py --candidate-no 1234 --all-subjects --confirm-public-source
python scripts/capture_try_learning_browser.py --candidate-no 1234 --subject-code wlgcs --promote --confirm-public-source --headless
python scripts/run_try_learning_pipeline.py --candidate-no 1234 --all-subjects --confirm-public-source
```

公开 JSON 没有答案时，脚本会保存标准化草稿和质量报告，但默认不入库。
浏览器捕获依赖 Playwright，首次使用前执行：

```bash
python -m playwright install chromium
```

如需用 DeepSeek / 可选 SearXNG 给草稿推断答案：

```bash
python scripts/enrich_try_learning_answers.py --only wlgcs --limit 20 --use-search --confirm-ai-answers
```

AI 答案不会标记为人工校对；默认 `quality_status=ai_answered`，需要抽查后再改为 `ok`。

## 质量规则

以下题会被清理接口标记为低质量候选：

- 无答案
- 单选题缺少有效选项
- 题干过短
- 题干依赖图、表、拓扑、日志、波形但缺少图片
- `quality_status` 不是 `ok`
- 未校对 AI 草稿
