"""DashScope 2.x native video upload; one request, no retries or slicing."""

import importlib


def create_client(config, api_key):
    try:
        dashscope = importlib.import_module("dashscope")
    except ImportError as exc:
        raise RuntimeError("Install annotation_pipeline/requirements.txt (DashScope 2.0.1+) first") from exc
    if not hasattr(dashscope, "Client"):
        raise RuntimeError("DashScope 2.0.1+ with dashscope.Client is required")
    return dashscope.Client(
        api_key=api_key,
        base_url=config["base_url"],
        protocol="native",
        timeout=config["timeout_seconds"],
        max_retries=0,
    )


def extract_facts(client, config, video_path, prompt_text):
    # SDK syntax: file://D:/... on Windows, file:///... on POSIX.
    # Spaces remain literal: this is an SDK local-file input.
    video_uri = "file://" + video_path.resolve().as_posix()
    return client.multimodal.chat.create(
        model=config["model"],
        messages=[{"role": "user", "content": [
            {"video": video_uri, "fps": config["fps"]},
            {"text": prompt_text},
        ]}],
    )


def response_usage(response):
    usage = getattr(response, "usage", None)
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump(mode="json", exclude_none=True)
    if not isinstance(usage, dict):
        return None

    def numeric_fields(values):
        return {key: numeric_fields(value) if isinstance(value, dict) else value
                for key, value in values.items()
                if isinstance(value, (int, float, dict)) and not isinstance(value, bool)}

    return numeric_fields(usage)
