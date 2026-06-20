from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class TextSpan(BaseModel):
    text: str
    pageNumber: int
    bbox: BoundingBox
    fontSize: float
    fontName: str
    isBold: bool


class TextBlock(BaseModel):
    text: str
    pageStart: int
    pageEnd: int
    bbox: BoundingBox
    fontSize: float
    isBold: bool
    blockType: Literal["text", "heading"]


class ExtractedTable(BaseModel):
    pageNumber: int
    bbox: BoundingBox | None = None
    rows: list[list[str]]
    markdown: str


class ExtractedPage(BaseModel):
    number: int
    text: str
    spans: list[TextSpan]
    ocrUsed: bool = False
    ocrConfidence: float | None = None
    warnings: list[str] = Field(default_factory=list)


class ExtractedDocument(BaseModel):
    fileName: str
    sha256: str
    pageCount: int
    extractionMethod: Literal["pymupdf", "pymupdf_ocr"]
    rawText: str
    markdown: str
    pages: list[ExtractedPage]
    blocks: list[TextBlock]
    tables: list[ExtractedTable]
    warnings: list[str] = Field(default_factory=list)

