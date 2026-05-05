# 软考中级网络工程师题库管理系统

本项目是一个本地/内网可用的软考中级“网络工程师”真题题库管理系统。第一阶段重点交付后端 MVP：题库管理、JSON 导入、刷题、错题本、收藏、统计、Swagger API，以及 DeepSeek v4 辅助结构化导入能力。

## 项目结构

```text
rk-network-engineer-bank/
├─ backend/
│  ├─ app/                 # FastAPI 应用
│  ├─ alembic/             # 数据库迁移
│  ├─ scripts/             # 提取、导入、审查脚本
│  ├─ data/
│  │  ├─ full_export.json  # 全量题目数据（2500+题）
│  │  ├─ pdf_extracted/    # PDF 提取的 JSON
│  │  └─ sources/          # 原始 PDF（需自行 clone，不上传）
│  ├─ requirements.txt
│  ├─ .env.example
│  └─ README.md
├─ frontend/
│  └─ README.md
└─ README.md
```

## 快速开始

进入后端目录：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，填写 MySQL 管理员密码、业务用户密码和可选的 DeepSeek API Key。

```bash
python scripts/init_database.py          # 初始化数据库
python scripts/import_full_export.py     # 导入 2500+ 真题
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger 文档入口：

```text
http://127.0.0.1:8000/docs
```

启动前端：

```bash
cd ../frontend
npm install
npm run dev
```

前端入口：

```text
http://127.0.0.1:5173
```

## 导入题库数据

项目附带了从 2011-2023 年真题中提取的 **2500+ 道题目**（`backend/data/full_export.json`）。

```bash
cd backend
python scripts/import_full_export.py
```

数据来源：
- 上午综合知识（选择题，每年 75 题左右）
- 下午案例分析（配置/填空题，每年 30-90 题）
- 通过 DeepSeek AI 从 PDF 真题自动提取并结构化
- 经过 AI 质量审查，已清理重复和错误题目

## PDF 批量提取（可选）

如需从原始 PDF 重新提取：

```bash
cd backend
git clone https://gitee.com/zaonai/network_engineer data/sources/gitee_zaonai_network_engineer
python scripts/extract_pdf_questions.py --import
python scripts/ocr_extract.py --import          # 扫描版 PDF 用 OCR
```

已提供 `backend/scripts/import_gitee_network_engineer.py`，用于处理你确认授权的 `https://gitee.com/zaonai/network_engineer` 仓库。脚本会从历年真题 PDF 抽取文本，交给 DeepSeek 结构化，并按年份、上/下半年、上午/下午卷别入库。

```bash
cd backend
git clone https://gitee.com/zaonai/network_engineer data/sources/gitee_zaonai_network_engineer
python scripts/import_gitee_network_engineer.py --years 2009-2024 --confirm-license --update-existing --skip-existing-exams --max-chars 20000
```

## AI 出题

前端提供 `AI 出题` 工作台，可按年份、上/下半年、卷别、题型、难度、知识点和参考文本生成模拟题草稿。生成结果默认标记为未人工校对，并通过 `POST /api/import/ai-generated` 以 `ai-generated` 批次类型入库。

## 合规声明

本项目仅用于个人学习、资料整理和题库管理。
真题内容、解析、PDF、扫描件等资料的版权归原权利方所有。
请仅导入自己整理、公开授权或合法取得的数据。
