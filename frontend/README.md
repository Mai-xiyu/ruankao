# 软考多科目题库前端

Vue 3 + Vite + TypeScript + Element Plus 前端，用于管理题库、刷题、导入数据和调用 DeepSeek v4 辅助整理。

## 启动

```bash
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

开发环境通过 Vite proxy 将 `/api` 转发到：

```text
http://127.0.0.1:8000
```

请先启动后端：

```bash
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
