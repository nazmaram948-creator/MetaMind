from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import settings


def configured() -> bool:
    return bool(
        settings.runpod_api_key
        and (settings.runpod_endpoint_id or settings.runpod_base_url)
    )


def provider_status() -> dict[str, str | bool]:
    return {
        "compute_provider": "runpod-serverless" if configured() else "local-deterministic",
        "runpod_configured": configured(),
    }


def extract_skill_ids(text: str) -> list[str] | None:
    """Ask RunPod for candidate IDs; callers must apply their own allowlist."""
    if not configured():
        return None
    url = settings.runpod_base_url or (
        f"https://api.runpod.ai/v2/{settings.runpod_endpoint_id}/runsync"
    )
    payload = json.dumps({"input": {"text": text, "task": "extract_skill_ids"}}).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.runpod_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.runpod_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    output = body.get("output", body)
    ids = output.get("skill_ids") if isinstance(output, dict) else None
    return [value for value in ids if isinstance(value, str)] if isinstance(ids, list) else None
