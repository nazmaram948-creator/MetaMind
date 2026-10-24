"""Verify the configured RunPod endpoint without logging credentials."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    base_url = os.getenv("RUNPOD_BASE_URL")
    proof_path = Path("data/runpod_verification_proof.json")
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof = {
        "provider": "runpod-serverless",
        "configured": bool(api_key and (endpoint_id or base_url)),
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint_id_present": bool(endpoint_id),
        "request_status": "not_attempted",
    }
    if not proof["configured"]:
        proof["request_status"] = "not_configured"
    else:
        url = base_url or f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
        payload = json.dumps({"input": {"task": "health_check", "text": "ping"}}).encode()
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                proof["request_status"] = "ok" if 200 <= response.status < 300 else f"http_{response.status}"
        except (OSError, urllib.error.URLError) as error:
            proof["request_status"] = "error"
            proof["error_type"] = type(error).__name__
    proof_path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2))
    raise SystemExit(0 if proof["request_status"] in {"ok", "not_configured"} else 1)


if __name__ == "__main__":
    main()
