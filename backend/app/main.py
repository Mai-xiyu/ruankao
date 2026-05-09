from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.routers import admin, ai, auth, exams, favorites, importing, practice, questions, records, sources, stats, subjects, tags

settings = get_settings()

app = FastAPI(
    title="软考多科目题库管理系统",
    description="多级别科目、题库管理、导入清理、刷题、错题本、收藏、用户系统与 AI 辅助 API。",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/data", StaticFiles(directory=str(BASE_DIR / "data")), name="data")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(subjects.router)
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
        "name": "软考多科目题库管理系统",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
