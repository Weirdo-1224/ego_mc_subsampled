"""Local configuration, replaceable prompts and separate credentials."""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from string import Template
from urllib.parse import urlsplit

from annotation_pipeline.scripts.validation import parse_json

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE
DEFAULT_CONFIG = PACKAGE / "configs/config.example.json"
PROMPTS = ("system", "events", "dependencies", "tasks", "verifications", "probe")


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def config_path(config, field):
    value = Path(config[field])
    return (value if value.is_absolute() else Path(config["_config_dir"]) / value).resolve()


def load_config(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    baseline = parse_json(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    supplied = parse_json(path.read_text(encoding="utf-8"))
    if not isinstance(supplied, dict) or set(supplied) - set(baseline):
        raise ValueError("Unknown config fields; store API keys in environment or credentials.local.json")
    config = baseline | supplied
    for env, field in (("ANNOTATION_MODEL", "model"), ("ANNOTATION_BASE_URL", "base_url"),
                       ("ANNOTATION_API_KEY_ENV", "api_key_env")):
        if os.environ.get(env):
            config[field] = os.environ[env]
    for field in ("provider", "model", "prompt_version", "video_path", "output_dir", "prompts_dir", "credentials_file"):
        if not isinstance(config[field], str) or not config[field].strip():
            raise ValueError("Expected nonempty config field: " + field)
    endpoint = urlsplit(config["base_url"])
    if endpoint.scheme != "https" or not endpoint.netloc or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("base_url must be HTTPS without embedded credentials/query/fragment")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config["api_key_env"]):
        raise ValueError("api_key_env must be an environment variable NAME")
    if config["video_id"] != "GX010029" or Path(config["video_path"]).suffix.lower() != ".mp4":
        raise ValueError("V0.2 supports only the explicit GX010029 MP4, not batch datasets")
    if config["transport_retries"] != 0 or config["structure_retries"] != 1:
        raise ValueError("V0.2 uses no automatic transport retries and one structural repair")
    bounds = {
        "max_calls": (1, 100), "budget_cny": (0.01, 1000), "cost_reserve_per_call_cny": (0.01, 1000),
        "max_tokens": (128, 32768), "timeout_seconds": (1, 600), "current_window_seconds": (1, 600),
        "discovery_segment_seconds": (10, 600), "discovery_fps": (0.1, 10),
        "verification_fps": (0.1, 10), "video_width": (320, 1920),
        "target_candidates": (1, 10), "max_verifications": (1, 4),
    }
    for field, (low, high) in bounds.items():
        value = config[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError("Invalid numeric config field: " + field)
    for field in ("max_calls", "max_tokens", "discovery_segment_seconds", "video_width", "target_candidates", "max_verifications"):
        if type(config[field]) is not int:
            raise ValueError("Expected integer config field: " + field)
    if type(config["video_fps_parameter"]) is not bool:
        raise ValueError("video_fps_parameter must be true or false")
    if not isinstance(config["request_options"], dict) or set(config["request_options"]) - {
        "temperature", "top_p", "enable_thinking", "thinking", "reasoning_effort",
    }:
        raise ValueError("Unsupported request_options; authentication/messages/model are controlled separately")
    prices = config["price_cny_per_million"]
    if prices is not None and (not isinstance(prices, list) or not prices or any(
        not isinstance(row, list) or len(row) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in row)
        for row in prices
    )):
        raise ValueError("price_cny_per_million must be null or threshold/input/output rows")
    config["_config_dir"] = str(path.parent)
    return config


def load_api_key(config):
    name = config["api_key_env"]
    key = os.environ.get(name)
    if key and key.strip():
        return key.strip()
    path = config_path(config, "credentials_file")
    if not path.is_file():
        return None
    try:
        values = parse_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("Cannot parse local credentials file") from None
    if not isinstance(values, dict):
        raise ValueError("Credentials file must map environment variable names to keys")
    key = values.get(name)
    if key is None:
        return None
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Configured local credential is empty or invalid")
    return key.strip()


def prompt_snapshot(config):
    root = config_path(config, "prompts_dir")
    result = {}
    for name in PROMPTS:
        content = (root / (name + ".md")).read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError("Empty prompt: " + name)
        result[name] = {"text": content, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
    return result


def render_prompt(config, name, **values):
    content = (config_path(config, "prompts_dir") / (name + ".md")).read_text(encoding="utf-8")
    return Template(content).substitute({k: str(v) for k, v in values.items()})
