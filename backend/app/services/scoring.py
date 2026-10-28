"""Validate model output before it can become employee performance data."""
import json
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import llm

Risk = Literal["customer_data_shared", "confidential_data_shared", "unreviewed_output", "policy_unaware"]


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    score: float = Field(ge=1, le=5, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=2000)
    flags: list[Risk] = Field(max_length=4)


class ScoringError(Exception):
    def __init__(self, message="AI evaluation failed validation; no answers were saved.", status=502):
        self.status = status
        super().__init__(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def parse_evaluation(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 20_000:
        raise ScoringError()
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\s*```", raw.strip(), flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    try:
        result = Evaluation.model_validate(json.loads(raw, object_pairs_hook=_unique_object))
        if not result.reason.strip() or len(result.flags) != len(set(result.flags)):
            raise ScoringError()
        return result.model_dump()
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ScoringError() from exc


def score_open_answer(question_text: str, answer: str) -> dict:
    try:
        return parse_evaluation(llm.score_answer(question_text, answer))
    except ScoringError:
        raise
    except httpx.TimeoutException as exc:
        raise ScoringError("AI evaluation timed out; no answers were saved. Try again.", 504) from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ScoringError("AI provider unavailable; no answers were saved. Try again.", 502) from exc
