from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[])


class BatchSubmitRequest(BaseModel):
    count: int = Field(ge=1, le=500)
    job_type: str


def require_local_token(authorization: Annotated[str | None, Header()] = None) -> None:
    api_token = os.environ.get("API_TOKEN")
    if api_token and authorization != f"Bearer {api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@router.post(
    "/batch",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_local_token)],
)
async def submit_batch_route(_request: BatchSubmitRequest) -> dict[str, str]:
    return {"status": "accepted"}


@router.get("/runs/{run_id}/status", dependencies=[Depends(require_local_token)])
async def run_status_route(run_id: str) -> dict[str, str]:
    return {"run_id": run_id, "status": "pending"}
