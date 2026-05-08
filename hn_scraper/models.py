"""Pydantic domain models.

Slice 1 introduces ``Job``, ``ThreadMeta``, and ``Digest``.
``RunTelemetry`` lands in Slice 2 when ``hn-scraper compare`` reads
the JSONL log back.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WorkMode = Literal["remote", "hybrid", "onsite", "unspecified"]


class Job(BaseModel):
    company: str
    role: str
    location_text: str
    work_mode: WorkMode
    salary_range: str | None
    tech_stack: list[str] = Field(default_factory=list)
    contact: str | None
    raw_text: str


class ThreadMeta(BaseModel):
    item_id: int
    title: str
    url: str


class Digest(BaseModel):
    thread: ThreadMeta
    jobs: list[Job]
    generated_at: datetime
    wall_clock_seconds: float
    total_llm_cost_usd: float
    total_llm_calls: int
    candidate_comments: int
