"""
Anonymous product feedback.

No authentication, by design: the product is fully browsable without an
account, so feedback must be too. Nothing identifying is stored — see the
`feedback` table comment for the privacy posture.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimitRule, check_rate_limit
from app.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


def feedback_rule() -> RateLimitRule:
    """Feedback is cheap to serve but trivially spammable without an account,
    so it gets its own modest per-client budget."""
    return RateLimitRule(name="feedback", limit=5, window_seconds=60)


class FeedbackRequest(BaseModel):
    """Every field is optional. The only rule is that a submission must carry
    *something* — a bare ping is not feedback."""

    rating: Optional[int] = Field(None, ge=1, le=5, description="1-5 stars, optional")
    comment: Optional[str] = Field(None, max_length=2000, description="Optional free text")
    email: Optional[str] = Field(
        None, max_length=254, description="Optional, only if the user wants a reply"
    )
    page: Optional[str] = Field(None, max_length=120, description="Where it was submitted from")

    @field_validator("comment", "email", "page", mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        """The form submits "" for untouched fields; store NULL, not empty
        strings, so "no email given" is unambiguous in the data."""
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @field_validator("email")
    @classmethod
    def _plausible_email(cls, value: Optional[str]) -> Optional[str]:
        # Intentionally minimal: the address is optional and unverified, so the
        # goal is to catch a typo, not to enforce RFC 5322.
        if value is None:
            return None
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address, or leave it blank.")
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> "FeedbackRequest":
        if self.rating is None and not self.comment:
            raise ValueError("Add a rating or a comment before submitting.")
        return self


class FeedbackResponse(BaseModel):
    ok: bool = True
    message: str = "Thanks — your feedback was recorded."


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Record a piece of anonymous feedback.

    Deliberately stores only what the visitor typed. No user id, IP or
    user-agent is persisted — the rate limiter sees the client identity, the
    feedback row does not.
    """
    await check_rate_limit(db, feedback_rule(), request, None)

    try:
        await db.execute(
            text(
                """
                INSERT INTO public.feedback (rating, comment, email, page)
                VALUES (:rating, :comment, :email, :page)
                """
            ),
            {
                "rating": payload.rating,
                "comment": payload.comment,
                "email": payload.email,
                "page": payload.page,
            },
        )
        await db.commit()
    except Exception:
        await db.rollback()
        # Never surface the driver error: it can leak schema details, and the
        # visitor can do nothing with it either way.
        logger.exception("Failed to record feedback")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Couldn't record your feedback just now. Please try again shortly.",
        )

    return FeedbackResponse()
