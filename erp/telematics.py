import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

from django.conf import settings


@dataclass
class TelematicsStatus:
    ok: bool
    message: str
    positions: list


def _build_headers():
    headers = {"Accept": "application/json"}
    auth_header = getattr(settings, "TRACCAR_AUTH_HEADER", "")
    token = getattr(settings, "TRACCAR_TOKEN", "")
    if auth_header:
        headers["Authorization"] = auth_header
    elif token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_json(path):
    base_url = getattr(settings, "TRACCAR_BASE_URL", "")
    if not base_url:
        raise ValueError("TRACCAR_BASE_URL n'est pas configuré.")
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = urllib.request.Request(url, headers=_build_headers())
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_traccar_positions():
    try:
        devices = _fetch_json("/api/devices")
        positions = _fetch_json("/api/positions")
        positions_by_device = {pos.get("deviceId"): pos for pos in positions}
        payload = []
        for device in devices:
            pos = positions_by_device.get(device.get("id"))
            payload.append(
                {
                    "device_id": device.get("id"),
                    "name": device.get("name"),
                    "status": device.get("status"),
                    "last_update": device.get("lastUpdate"),
                    "position": pos or {},
                }
            )
        return TelematicsStatus(ok=True, message="OK", positions=payload)
    except ValueError as exc:
        return TelematicsStatus(ok=False, message=str(exc), positions=[])
    except urllib.error.HTTPError as exc:
        return TelematicsStatus(ok=False, message=f"Erreur Traccar HTTP {exc.code}", positions=[])
    except Exception:
        return TelematicsStatus(ok=False, message="Erreur de connexion à Traccar.", positions=[])
