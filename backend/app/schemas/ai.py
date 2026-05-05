from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.exam import ExamCreate


class AIExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=60000)
    exam: ExamCreate | None = None
    use_reasoning_model: bool = False


class AIGenerateQuestionsRequest(BaseModel):
    exam: ExamCreate
    question_count: int = Field(default=5, ge=1, le=30)
    question_types: list[str] = Field(default_factory=lambda: ["single_choice"])
    difficulty: int = Field(default=3, ge=1, le=5)
    knowledge_areas: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_text: str | None = Field(default=None, max_length=60000)
    extra_requirements: str | None = Field(default=None, max_length=4000)
    use_reasoning_model: bool = False

    @model_validator(mode="after")
    def compact_lists(self) -> "AIGenerateQuestionsRequest":
        self.question_types = [item.strip() for item in self.question_types if item and item.strip()]
        self.knowledge_areas = [item.strip() for item in self.knowledge_areas if item and item.strip()]
        self.tags = [item.strip() for item in self.tags if item and item.strip()]
        if not self.question_types:
            self.question_types = ["single_choice"]
        return self


class AISuggestTagsRequest(BaseModel):
    stem: str = Field(min_length=1, max_length=20000)
    answer: str | None = None
    analysis: str | None = None
    use_reasoning_model: bool = False


class AIImproveAnalysisRequest(BaseModel):
    stem: str = Field(min_length=1, max_length=20000)
    answer: str | None = None
    analysis: str | None = None
    use_reasoning_model: bool = False


class AISourceAuditRequest(BaseModel):
    url: str = Field(max_length=1000)
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=60000)
    exam: ExamCreate | None = None
    year: int | None = Field(default=None, ge=1990, le=2100)
    season: str | None = None
    paper_type: str | None = None
    use_reasoning_model: bool = False


class AISourceAuditResult(BaseModel):
    relevant: bool
    can_structure: bool
    risk_level: str
    license_signal: str
    can_auto_import: bool
    reason: str
    suggested_action: str
    extracted_year: int | None = None
    extracted_season: str | None = None


class SourcePreviewRequest(BaseModel):
    text: str | None = Field(default=None, max_length=60000)
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def require_source(self) -> "SourcePreviewRequest":
        if not self.text and not self.url:
            raise ValueError("text 或 url 必须提供一个")
        return self


class SourceConfirmRequest(SourcePreviewRequest):
    legal_confirmation: bool
    exam: ExamCreate | None = None
    use_reasoning_model: bool = False
