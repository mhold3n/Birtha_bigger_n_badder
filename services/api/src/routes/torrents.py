from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..clients.qbittorrent import QBittorrentClient


router = APIRouter(prefix="/api/torrents", tags=["Torrents"])


class AddTorrentRequest(BaseModel):
    urls: List[str] = Field(..., description="List of magnet URLs or .torrent URLs")


class TorrentHashesRequest(BaseModel):
    hashes: Optional[List[str]] = Field(
        default=None, description="Specific torrent hashes; omit for all"
    )


def _qb_client() -> QBittorrentClient:
    if not settings.qb_password:
        # Intentionally allow empty passwords in dev but make it explicit
        pass
    return QBittorrentClient(
        base_url=settings.qb_base_url,
        username=settings.qb_username,
        password=settings.qb_password,
    )


@router.get("/")
async def list_torrents() -> Dict[str, Any]:
    try:
        async with _qb_client() as qb:
            items = await qb.list_torrents()
            return {"items": items}
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=502, detail=f"Failed to list torrents: {e}")


@router.post("/add")
async def add_torrents(req: AddTorrentRequest) -> Dict[str, Any]:
    if not req.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    try:
        async with _qb_client() as qb:
            res = await qb.add(req.urls)
            return res
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=502, detail=f"Failed to add torrent(s): {e}")


@router.post("/pause")
async def pause_torrents(req: TorrentHashesRequest) -> Dict[str, Any]:
    try:
        async with _qb_client() as qb:
            return await qb.pause(req.hashes or [])
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=502, detail=f"Failed to pause torrents: {e}")


@router.post("/resume")
async def resume_torrents(req: TorrentHashesRequest) -> Dict[str, Any]:
    try:
        async with _qb_client() as qb:
            return await qb.resume(req.hashes or [])
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=502, detail=f"Failed to resume torrents: {e}")

