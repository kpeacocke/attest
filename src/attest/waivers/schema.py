"""Waiver schema (REQ-5.1)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, model_validator


class Waiver(BaseModel):
    """An exception granted for one or more controls."""

    id: str
    control_ids: list[str] = Field(min_length=1)
    justification: str = Field(min_length=1)
    owner: str = ""
    expiry: date
    reference: HttpUrl | None = None
    scope: str = ""  # host/group/env predicate (future use)

    @model_validator(mode="before")
    @classmethod
    def _normalise_control_ids(cls, data: Any) -> Any:
        """Support control_id or control_ids in waiver documents."""
        if not isinstance(data, dict):
            return data

        if "control_ids" in data:
            return data

        control_id = data.get("control_id")
        if isinstance(control_id, str) and control_id:
            new_data = dict(data)
            new_data["control_ids"] = [control_id]
            return new_data

        return data

    def is_active(self, as_of: date | None = None) -> bool:
        """Return True if the waiver has not yet expired."""
        check_date = as_of or date.today()
        return self.expiry >= check_date

    def is_expired(self, as_of: date | None = None) -> bool:
        return not self.is_active(as_of)

    def to_report_dict(self) -> dict[str, Any]:
        """Return stable waiver metadata for canonical reporting."""
        return {
            "id": self.id,
            "control_ids": sorted(self.control_ids),
            "justification": self.justification,
            "owner": self.owner,
            "expiry": self.expiry.isoformat(),
            "reference": str(self.reference) if self.reference is not None else None,
            "scope": self.scope,
        }


def load_waivers(path: Path | str) -> list[Waiver]:
    """Load waivers from YAML file, returning a deterministic list by ID."""
    path_obj = Path(path)
    raw = yaml.safe_load(path_obj.read_text(encoding="utf-8"))
    if raw is None:
        return []

    records: Iterable[Any]
    if isinstance(raw, dict) and isinstance(raw.get("waivers"), list):
        records = raw["waivers"]
    elif isinstance(raw, list):
        records = raw
    else:
        raise ValueError(
            f"Waiver file '{path_obj}' must contain a list or a top-level 'waivers' list."
        )

    waivers = [Waiver.model_validate(record) for record in records]
    return sorted(waivers, key=lambda waiver: waiver.id)
