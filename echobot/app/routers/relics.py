from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/relics", tags=["relics"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


def _get_relic_service(request: Request):
    runtime = request.app.state.runtime
    relic_service = getattr(runtime, "_relic_service", None)
    if relic_service is None or not relic_service.available:
        raise HTTPException(
            status_code=503,
            detail="Relic knowledge base not available (RELIC_DATABASE_URL not configured)",
        )
    return relic_service


@router.get("")
async def list_relics(
    request: Request,
    dynasty: str | None = None,
    category: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    svc = _get_relic_service(request)
    return await svc.list_relics(dynasty=dynasty, category=category, offset=offset, limit=limit)


@router.get("/random")
async def random_relics(
    request: Request,
    limit: int = Query(default=1, ge=1, le=10),
):
    svc = _get_relic_service(request)
    return await svc.get_random(limit=limit)


@router.get("/{relic_id}")
async def get_relic(request: Request, relic_id: int):
    svc = _get_relic_service(request)
    relic = await svc.get_relic(relic_id)
    if relic is None:
        raise HTTPException(status_code=404, detail="Relic not found")
    return relic


@router.post("/search")
async def search_relics(request: Request, body: SearchRequest):
    svc = _get_relic_service(request)
    return await svc.search(body.query, limit=body.limit)
