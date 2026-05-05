from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ai, exams, favorites, importing, practice, questions, records, sources, stats, tags


app = FastAPI(
    title="软考中级网络工程师题库管理系统",
    description="题库管理、JSON 导入、刷题、错题本、收藏、统计与 DeepSeek v4 辅助导入 API。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exams.router)
app.include_router(questions.router)
app.include_router(importing.router)
app.include_router(practice.router)
app.include_router(records.router)
app.include_router(favorites.router)
app.include_router(tags.router)
app.include_router(stats.router)
app.include_router(ai.router)
app.include_router(sources.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "软考中级网络工程师题库管理系统",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

