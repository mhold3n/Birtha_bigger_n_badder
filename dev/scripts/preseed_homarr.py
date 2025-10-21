#!/usr/bin/env python3
import json
import sys
import uuid
from pathlib import Path


def new_app(name, url, icon, x_lg, y_lg, x_md, y_md, x_sm, y_sm, width_lg=2, width_md=1, width_sm=1):
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "url": url,
        "behaviour": {
            "onClickUrl": url,
            "externalUrl": url,
            "isOpeningNewTab": True,
        },
        "network": {
            "enabledStatusChecker": False,
            "statusCodes": ["200", "302", "307"],
        },
        "appearance": {
            "iconUrl": icon,
            "appNameStatus": "normal",
            "positionAppName": "row-reverse",
            "lineClampAppName": 1,
        },
        "integration": {"type": None, "properties": []},
        "area": {"type": "wrapper", "properties": {"id": "default"}},
        "shape": {
            "md": {
                "location": {"x": x_md, "y": y_md},
                "size": {"width": width_md, "height": 1},
            },
            "sm": {
                "location": {"x": x_sm, "y": y_sm},
                "size": {"width": width_sm, "height": 1},
            },
            "lg": {
                "location": {"x": x_lg, "y": y_lg},
                "size": {"width": width_lg, "height": 1},
            },
        },
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: preseed_homarr.py <default.json path> <server_ip>")
        return 2
    cfg_path = Path(sys.argv[1])
    server_ip = sys.argv[2]

    data = json.loads(cfg_path.read_text())
    apps = data.get("apps", [])

    entries = [
        (
            "API (FastAPI)",
            f"http://{server_ip}:8080",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons@master/png/fastapi.png",
            0,
            4,
            0,
            6,
            0,
            8,
        ),
        (
            "Router",
            f"http://{server_ip}:8000",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons@master/png/python.png",
            2,
            4,
            1,
            6,
            1,
            8,
        ),
        (
            "Grafana",
            f"http://{server_ip}:3000",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons@master/png/grafana.png",
            4,
            4,
            2,
            6,
            2,
            8,
        ),
        (
            "Prometheus",
            f"http://{server_ip}:9090",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons@master/png/prometheus.png",
            6,
            4,
            3,
            6,
            0,
            9,
        ),
        (
            "Pi-hole",
            f"http://{server_ip}:8081/admin",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons@master/png/pihole.png",
            8,
            4,
            4,
            6,
            1,
            9,
        ),
    ]

    existing_names = {a.get("name") for a in apps}
    for name, url, icon, xlg, ylg, xmd, ymd, xsm, ysm in entries:
        if name not in existing_names:
            apps.append(new_app(name, url, icon, xlg, ylg, xmd, ymd, xsm, ysm))

    data["apps"] = apps
    cfg_path.write_text(json.dumps(data, indent=2))
    print(f"[HOMARR_CONFIG_UPDATED] {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

