from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..clients.proxmox import ProxmoxClient


router = APIRouter(prefix="/api/vms", tags=["VMs"])


def _pmx_client() -> ProxmoxClient:
    return ProxmoxClient(
        base_url=settings.proxmox_base_url,
        token_id=settings.proxmox_token_id,
        token_secret=settings.proxmox_token_secret,
        verify_ssl=settings.proxmox_verify_ssl,
    )


@router.get("/")
async def list_vms() -> Dict[str, List[Dict[str, Any]]]:
    """Return VMs/LXCs from Proxmox cluster resources.

    If Proxmox credentials are missing, returns an informative error.
    """
    if not settings.proxmox_token_id or not settings.proxmox_token_secret:
        raise HTTPException(status_code=501, detail="Proxmox credentials not configured")

    async with _pmx_client() as client:
        try:
            vms = await client.list_vms()
            return {"items": vms}
        except Exception as e:  # pragma: no cover - I/O wrapper
            raise HTTPException(status_code=502, detail=f"Failed to list VMs: {e}")


@router.post("/{vmid}/start")
async def start_vm(vmid: int) -> Dict[str, Any]:
    if not settings.proxmox_token_id or not settings.proxmox_token_secret:
        raise HTTPException(status_code=501, detail="Proxmox credentials not configured")
    async with _pmx_client() as client:
        try:
            return await client.start_vm(vmid)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:  # pragma: no cover - I/O wrapper
            raise HTTPException(status_code=502, detail=f"Failed to start VM: {e}")


@router.post("/{vmid}/stop")
async def stop_vm(vmid: int) -> Dict[str, Any]:
    if not settings.proxmox_token_id or not settings.proxmox_token_secret:
        raise HTTPException(status_code=501, detail="Proxmox credentials not configured")
    async with _pmx_client() as client:
        try:
            return await client.stop_vm(vmid)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:  # pragma: no cover - I/O wrapper
            raise HTTPException(status_code=502, detail=f"Failed to stop VM: {e}")

