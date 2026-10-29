"""Configuration and local files for full-video fact extraction only."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


PACKAGE = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PACKAGE / "configs" / "config.example.json"
PROMPT = PACKAGE / "prompts" / "video_facts.md"
TASK_RULES = PACKAGE / "prompts" / "task_rules.md"
PROMPT_VERSION = "Video Fact Extraction V1"
DEFAULTS = {
    "provider": "dashscope",
    "model": "qwen3.8-max",
    "base_url": "https://maas.qianwenaiapi.com/api/v1",
    "api_key_env": "DASHSCOPE_API_KEY",
    "fps": 1.0,
    "timeout_seconds": 300,
    "output_dir": "../runs",
    "ffprobe": "ffprobe",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def positive_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def run_directory(config, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
        raise ValueError("run_id must use 1-128 ASCII letters, digits, underscores or hyphens")
    output = Path(config["output_dir"]).resolve()
    run = output / run_id
    if run.is_symlink() or run.resolve().parent != output:
        raise ValueError("Run directory must be directly inside output_dir")
    return run


def load_config(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    supplied = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(supplied, dict) or set(supplied) - set(DEFAULTS):
        raise ValueError("Unsupported configuration; use the new config.example.json (no literal API keys)")
    config = DEFAULTS | supplied
    for name in ("provider", "model", "base_url", "api_key_env", "output_dir", "ffprobe"):
        if not isinstance(config[name], str) or not config[name].strip():
            raise ValueError(f"{name} must be a nonempty string")
    if config["provider"] != "dashscope" or config["model"] != "qwen3.8-max":
        raise ValueError("This pipeline requires dashscope / qwen3.8-max")
    endpoint = urlsplit(config["base_url"])
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment or not endpoint.path.rstrip("/").endswith("/api/v1")):
        raise ValueError("base_url must be an HTTPS native /api/v1 endpoint without credentials or query")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config["api_key_env"]):
        raise ValueError("api_key_env must name an environment variable")
    positive_number(config["fps"], "fps")
    positive_number(config["timeout_seconds"], "timeout_seconds")
    config["base_url"] = config["base_url"].rstrip("/")
    config["output_dir"] = str((path.parent / config["output_dir"]).resolve())
    return config


def save_manifest(path, value):
    """Atomic checkpoints within a newly reserved run directory."""
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
