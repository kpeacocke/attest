"""Waiver schema (REQ-5.1)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class Waiver(BaseModel):
    """An exception granted for one or more controls."""

    id: str
    control_ids: list[str] = Field(min_length=1)
    justification: str
    owner: str = ""
    expiry: date
    reference: HttpUrl | None = None
    scope: str = ""  # host/group/env predicate (future use)

    def is_active(self, as_of: date | None = None) -> bool:
        """Return True if the waiver has not yet expired."""
        check_date = as_of or date.today()
        return self.expiry >= check_date

    def is_expired(self, as_of: date | None = None) -> bool:
        return not self.is_active(as_of)
