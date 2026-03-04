import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"
STATUS_PATH = ROOT / "data" / "status.json"
HISTORY_PATH = ROOT / "data" / "history.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config() -> Dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    apis = data.get("apis", [])
    settings = data.get("settings", {})
    if not isinstance(apis, list) or len(apis) == 0:
        raise ValueError("config.yaml 中 apis 不能为空。")

    return {
        "apis": apis,
        "settings": {
            "check_timeout": int(settings.get("check_timeout", 30)),
            "max_history_days": int(settings.get("max_history_days", 90)),
            "user_message": str(settings.get("user_message", "ping")),
        },
    }


def read_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return fallback


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_url(base_url: str, endpoint: str = "/v1/chat/completions") -> str:
    return f"{base_url.rstrip('/')}{endpoint}"


def get_api_keys_map() -> Dict[str, str]:
    raw = os.getenv("API_KEYS_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def resolve_api_key(key_env: str, api_keys_map: Dict[str, str]) -> str:
    direct = os.getenv(key_env, "").strip()
    if direct:
        return direct
    return api_keys_map.get(key_env, "").strip()


def check_one_api(
    api: Dict[str, Any], timeout_sec: int, user_message: str, api_keys_map: Dict[str, str]
) -> Dict[str, Any]:
    name = api["name"]
    base_url = api["base_url"]
    model = api["model"]
    key_env = api["api_key_env"]
    endpoint = api.get("endpoint", "/v1/chat/completions")
    url = normalize_url(base_url, endpoint)
    api_key = resolve_api_key(key_env, api_keys_map)

    now = utc_now_iso()
    result: Dict[str, Any] = {
        "name": name,
        "base_url": base_url,
        "endpoint": endpoint,
        "model": model,
        "status": "down",
        "response_time_ms": None,
        "http_status": None,
        "last_checked": now,
        "error": None,
    }

    if not api_key:
        result["error"] = f"Missing env: {key_env}"
        return result

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": user_message}],
        "max_tokens": 1,
        "temperature": 0,
    }

    start = time.perf_counter()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        result["response_time_ms"] = elapsed_ms
        result["http_status"] = response.status_code

        if response.status_code == 200:
            body = response.json()
            if isinstance(body, dict) and body.get("choices"):
                result["status"] = "up"
            else:
                result["status"] = "degraded"
                result["error"] = "200 but invalid response body"
        elif 500 <= response.status_code <= 599:
            result["status"] = "down"
            result["error"] = f"Server error: HTTP {response.status_code}"
        else:
            result["status"] = "degraded"
            result["error"] = f"Unexpected HTTP {response.status_code}"

    except requests.Timeout:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        result["response_time_ms"] = elapsed_ms
        result["error"] = "Request timeout"
    except requests.RequestException as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        result["response_time_ms"] = elapsed_ms
        result["error"] = f"Network error: {str(e)}"
    except ValueError:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        result["response_time_ms"] = elapsed_ms
        result["status"] = "degraded"
        result["error"] = "Invalid JSON response"

    return result


def compute_overall_status(results: List[Dict[str, Any]]) -> str:
    statuses = [r["status"] for r in results]
    if any(s == "down" for s in statuses):
        return "partial_outage"
    if any(s == "degraded" for s in statuses):
        return "degraded_performance"
    if all(s == "up" for s in statuses):
        return "operational"
    return "unknown"


def prune_checks(checks: List[Dict[str, Any]], retention_days: int) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept: List[Dict[str, Any]] = []
    for c in checks:
        ts = c.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt >= cutoff:
            kept.append(c)
    return kept


def update_incidents(
    incidents: List[Dict[str, Any]], results: List[Dict[str, Any]], now_iso: str
) -> List[Dict[str, Any]]:
    open_map: Dict[str, Dict[str, Any]] = {
        i["api_name"]: i for i in incidents if i.get("status") == "open"
    }

    for r in results:
        api_name = r["name"]
        current_status = r["status"]
        open_incident = open_map.get(api_name)
        is_bad = current_status in ("down", "degraded")

        if is_bad and not open_incident:
            incidents.append(
                {
                    "id": str(uuid.uuid4()),
                    "api_name": api_name,
                    "start_time": now_iso,
                    "end_time": None,
                    "status": "open",
                    "severity": current_status,
                    "last_error": r.get("error"),
                    "last_http_status": r.get("http_status"),
                }
            )
        elif is_bad and open_incident:
            open_incident["severity"] = current_status
            open_incident["last_error"] = r.get("error")
            open_incident["last_http_status"] = r.get("http_status")
        elif (not is_bad) and open_incident:
            open_incident["status"] = "resolved"
            open_incident["end_time"] = now_iso
            open_incident["last_error"] = None
            open_incident["last_http_status"] = r.get("http_status")
            start_dt = datetime.fromisoformat(open_incident["start_time"])
            end_dt = datetime.fromisoformat(now_iso)
            duration_minutes = max(1, int((end_dt - start_dt).total_seconds() // 60))
            open_incident["duration_minutes"] = duration_minutes

    incidents.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return incidents


def main() -> None:
    config = load_config()
    apis = config["apis"]
    timeout_sec = config["settings"]["check_timeout"]
    retention_days = config["settings"]["max_history_days"]
    user_message = config["settings"]["user_message"]
    now_iso = utc_now_iso()
    api_keys_map = get_api_keys_map()

    results: List[Dict[str, Any]] = []
    for api in apis:
        results.append(check_one_api(api, timeout_sec, user_message, api_keys_map))

    overall_status = compute_overall_status(results)
    status_payload = {
        "generated_at": now_iso,
        "overall_status": overall_status,
        "apis": results,
    }

    history = read_json(
        HISTORY_PATH, {"retention_days": retention_days, "checks": [], "incidents": []}
    )
    checks = history.get("checks", [])
    incidents = history.get("incidents", [])
    if not isinstance(checks, list):
        checks = []
    if not isinstance(incidents, list):
        incidents = []

    checks.append(
        {
            "timestamp": now_iso,
            "results": [
                {
                    "name": r["name"],
                    "status": r["status"],
                    "response_time_ms": r["response_time_ms"],
                }
                for r in results
            ],
        }
    )
    checks = prune_checks(checks, retention_days)
    incidents = update_incidents(incidents, results, now_iso)

    history_payload = {
        "retention_days": retention_days,
        "checks": checks,
        "incidents": incidents,
    }

    write_json(STATUS_PATH, status_payload)
    write_json(HISTORY_PATH, history_payload)

    up_count = len([r for r in results if r["status"] == "up"])
    print(
        f"[{now_iso}] Checked {len(results)} APIs, up={up_count}, overall={overall_status}"
    )


if __name__ == "__main__":
    main()
