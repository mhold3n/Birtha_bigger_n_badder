"""Docker Engine client wrapper for container status/restart.

Requires mounting `/var/run/docker.sock` into the `api` service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import os

try:
    import docker  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    docker = None  # type: ignore


class DockerUnavailable(Exception):
    pass


def _client():
    if docker is None:
        raise DockerUnavailable("docker SDK not installed")
    # Ensure socket exists
    if not os.path.exists("/var/run/docker.sock"):
        raise DockerUnavailable("/var/run/docker.sock not mounted")
    return docker.from_env()


def list_service_containers(service: str) -> List[Dict[str, Any]]:
    client = _client()
    try:
        containers = client.containers.list(all=True, filters={"label": f"com.docker.compose.service={service}"})
        items: List[Dict[str, Any]] = []
        for c in containers:
            items.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "labels": c.labels,
                }
            )
        return items
    finally:
        try:
            client.close()
        except Exception:
            pass


def restart_service(service: str, timeout: int = 10) -> Dict[str, Any]:
    client = _client()
    restarted = []
    try:
        containers = client.containers.list(all=True, filters={"label": f"com.docker.compose.service={service}"})
        for c in containers:
            c.restart(timeout=timeout)
            restarted.append(c.name)
        return {"service": service, "restarted": restarted}
    finally:
        try:
            client.close()
        except Exception:
            pass

