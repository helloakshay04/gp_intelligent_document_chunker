from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator, field_validator

Strategy = Literal["recursive", "fixed", "paragraph", "sentence", "table", "code", "semantic", "parent_child", "sliding_window"]
class ChunkingConfig(BaseModel):
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    overlap: int = Field(default=150, ge=0, le=2000)
    strategy: Strategy | Literal["auto"] = "auto"
    preview_count: int = Field(default=8, ge=5, le=10)
    @field_validator("strategy", mode="before")
    @classmethod
    def normalize_strategy(cls, value):
        if isinstance(value, str):
            aliases={"fixed_size":"fixed","fixed-size":"fixed","table_aware":"table","table-aware":"table","tableaware":"table","code_aware":"code","code-aware":"code","codeaware":"code","sliding-window":"sliding_window","parent-child":"parent_child","parentchild":"parent_child"}
            return aliases.get(value.strip().lower(),value.strip().lower())
        return value
    @model_validator(mode="after")
    def validate_overlap(self):
        if self.overlap >= self.chunk_size: raise ValueError("overlap must be smaller than chunk_size")
        if self.overlap > int(self.chunk_size * 0.5): raise ValueError("overlap must be at most 50% of chunk_size")
        return self
class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    extension: str
    file_type: str
    size_bytes: int
    content_type: str
    page_count: int | None = None
    sheet_names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
class StrategyRecommendation(BaseModel):
    strategy: str
    reason: str
    confidence: float = Field(ge=0, le=1)
    alternatives: list[str] = Field(default_factory=list)
    content_signals: dict[str, Any] = Field(default_factory=dict)
    candidate_scores: dict[str, float] = Field(default_factory=dict)
    scoring_method: str = "heuristic_quality_proxy"
    quality_note: str = "Scores estimate structural chunk quality; validate retrieval with labelled queries for true retrieval quality."
class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    index: int
    text: str
    char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
class ChunkingResult(BaseModel):
    sdk_version: str
    document: DocumentInfo
    recommendation: StrategyRecommendation
    config: ChunkingConfig
    extracted_text_preview: str
    total_characters: int
    total_chunks: int
    chunks: list[Chunk]
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any] = Field(default_factory=dict)
class ChunkPreview(BaseModel):
    sdk_version: str
    document: DocumentInfo
    recommendation: StrategyRecommendation
    config: ChunkingConfig
    total_characters: int
    estimated_total_chunks: int
    preview_chunks: list[Chunk]
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any] = Field(default_factory=dict)
