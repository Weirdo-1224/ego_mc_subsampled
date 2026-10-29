"""One DashScope backend for V0.2; no annotation or legacy-data imports."""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
from string import Template

from annotation_pipeline.scripts.validation import COMMON, FIELDS, parse_json, validate
from annotation_pipeline.scripts.common import load_api_key, now, prompt_snapshot, save


class VideoBackend:
    def __init__(self, config, run_dir, video, report, checkpoint):
        self.config, self.run_dir, self.video = config, Path(run_dir), video
        self.report, self.checkpoint = report, checkpoint
        self.prompts = prompt_snapshot(config)
        self.provenance = {k: config[k] for k in ("provider", "model", "prompt_version")}
        self.provenance["run_id"] = self.run_dir.name
        self.events, self.dependencies = {}, {}

    def stage_provenance(self, stage):
        provenance = dict(self.provenance)
        digest = hashlib.sha256((self.prompts["system"]["sha256"] + self.prompts[stage]["sha256"]).encode()).hexdigest()[:12]
        provenance["prompt_version"] += ":" + stage + ":" + digest
        return provenance

    def prompt(self, name, **values):
        return Template(self.prompts[name]["text"]).substitute({k: str(v) for k, v in values.items()})

    def clip(self, start, end, fps):
        # ffmpeg input seeking preserves only this interval; local time is documented.
        path = self.run_dir / "clips" / f"{start:.3f}_{end:.3f}_{fps:g}fps.mp4"
        manifest = path.with_suffix(".json")
        expected = {"source_sha256": self.video["sha256"], "video_id": self.video["video_id"],
                    "interval": {"start": start, "end": end}, "sampling_fps": fps,
                    "width": self.config["video_width"], "timestamp_offset_seconds": start}
        if manifest.exists():
            previous = parse_json(manifest.read_text(encoding="utf-8"))
            if any(previous[k] != v for k, v in expected.items()) or hashlib.sha256(path.read_bytes()).hexdigest() != previous["sha256"]:
                raise ValueError("Clip cache mismatch")
            return path
        if path.exists():
            raise ValueError("Incomplete clip exists; preserve it and use a new run ID")
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-nostdin", "-n", "-ss", str(start),
            "-i", self.video["path"], "-t", str(end - start), "-an", "-map_metadata", "-1",
            "-vf", f"fps={fps},scale={self.config['video_width']}:-2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path),
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if result.returncode or result.stderr.strip() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Clip extraction/decode failed: " + result.stderr.strip())
        expected["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        expected["file"] = path.relative_to(self.run_dir).as_posix()
        save(manifest, expected)
        return path

    def request(self, name, prompt, clips, provenance=None):
        key = load_api_key(self.config)
        content = [{"type": "text", "text": prompt}]
        manifests = []
        for clip in clips:
            manifest = parse_json(clip.with_suffix(".json").read_text(encoding="utf-8"))
            manifests.append(manifest)
            video_content = {"type": "video_url", "video_url": {
                "url": "data:video/mp4;base64," + base64.b64encode(clip.read_bytes()).decode("ascii"),
            }}
            if self.config["video_fps_parameter"]:
                video_content["fps"] = manifest["sampling_fps"]
            content += [
                {"type": "text", "text": "Next video original-time mapping: " + json.dumps(manifest)},
                video_content,
            ]
        payload = {"model": self.config["model"], "messages": [{"role": "user", "content": content}],
                   "max_tokens": self.config["max_tokens"], "response_format": {"type": "json_object"},
                   **self.config["request_options"]}
        body = json.dumps(payload).encode("utf-8")
        fingerprint = hashlib.sha256(body).hexdigest()
        raw_path = self.run_dir / "raw" / (name + ".json")
        if raw_path.exists():
            cached = parse_json(raw_path.read_text(encoding="utf-8"))
            if cached["request_sha256"] != fingerprint:
                raise ValueError("Request cache mismatch; use a new run ID")
            if cached["http_status"] != 200:
                raise ValueError("Cached API failure: use a new run after resolving provider error")
            self.report["cache_hits"] += 1
            self.checkpoint()
            response = parse_json(cached["body"])
        else:
            if any(c["request_sha256"] == fingerprint for c in self.report["calls"]):
                raise PermissionError("Previous request has no saved response; outcome/billing unknown. No automatic resubmission.")
            if not key:
                raise PermissionError("Missing " + self.config["api_key_env"])
            reserve = self.config["cost_reserve_per_call_cny"]
            if self.report["api_attempts"] >= self.config["max_calls"] or self.report["reserved_cost_cny"] + reserve > self.config["budget_cny"]:
                raise PermissionError("Configured call/cost budget exhausted")
            record = {"name": name, "started_at": now(), "status": "SENDING", "usage": None,
                      "estimated_cost_cny": None, "request_sha256": fingerprint}
            self.report["api_attempts"] += 1
            self.report["reserved_cost_cny"] += reserve
            self.report["calls"].append(record)
            self.checkpoint()
            save(self.run_dir / "raw" / (name + "_request.json"), {
                "prompt": prompt, "clips": manifests, "request_sha256": fingerprint,
                "source_sha256": self.video["sha256"], "provenance": provenance or self.provenance,
                "model": self.config["model"], "max_tokens": self.config["max_tokens"],
                "request_options": self.config["request_options"],
                "response_format": {"type": "json_object"}, "transport_retries": 0,
            })
            request = urllib.request.Request(self.config["base_url"] + "/chat/completions", body, {
                "Content-Type": "application/json", "Authorization": "Bearer " + key,
            })
            try:
                with urllib.request.urlopen(request, timeout=self.config["timeout_seconds"]) as result:
                    raw, status = result.read().decode("utf-8"), result.status
            except urllib.error.HTTPError as exc:
                raw, status = exc.read().decode("utf-8", errors="replace"), exc.code
            except OSError as exc:
                record.update(status="TRANSPORT_ERROR", error=str(exc).replace(key, "[REDACTED]"), finished_at=now())
                self.checkpoint()
                raise
            raw = raw.replace(key, "[REDACTED]")
            save(raw_path, {"http_status": status, "body": raw, "received_at": now(),
                            "request_sha256": fingerprint})
            record.update(status=status, finished_at=now())
            self.checkpoint()
            if status != 200:
                raise PermissionError(f"API HTTP {status}: {raw}")
            response = parse_json(raw)
            usage = response.get("usage")
            record["usage"] = usage
            self.report["successful_calls"] += 1
            if clips:
                self.report["successful_video_calls"] += 1
            if usage:
                pt, ct = usage["prompt_tokens"], usage["completion_tokens"]
                prices = self.config["price_cny_per_million"] if self.config["model"] == self.config["pricing_model"] else None
                tier = next((p for p in prices or [] if pt <= p[0]), None)
                if tier:
                    record["estimated_cost_cny"] = (pt * tier[1] + ct * tier[2]) / 1_000_000
                self.report["usage"]["prompt_tokens"] += pt
                self.report["usage"]["completion_tokens"] += ct
            estimates = [c["estimated_cost_cny"] for c in self.report["calls"] if c["estimated_cost_cny"] is not None]
            self.report["estimated_cost_cny"] = sum(estimates) if estimates else None
            self.report["cost_estimate_complete"] = len(estimates) == self.report["api_attempts"]
            self.checkpoint()
        choice = response["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Incomplete model output: " + str(choice.get("finish_reason")))
        return choice["message"]["content"]

    def structured(self, stage, name, instruction, clips, model_fields=None, transform=None, **context):
        provenance = self.stage_provenance(stage)
        self.report.setdefault("prompt_versions", {})[stage] = provenance["prompt_version"]
        self.checkpoint()
        fields = sorted(model_fields or FIELDS[stage] | {"id"})
        prompt = self.prompt("system", stage=stage, fields_json=json.dumps(fields),
                             video_id=self.video["video_id"], id_prefix=name + "_") + "\n" + instruction
        last_error = None
        retained = []
        for attempt in range(self.config["structure_retries"] + 1):
            repair = "" if attempt == 0 else "\nPrevious structural failure: " + str(last_error) + ". Return corrected records grounded in the videos, or an empty array."
            raw = self.request(name + f"_try{attempt}", prompt + repair, clips, provenance)
            try:
                parsed = parse_json(raw)
                if not isinstance(parsed, dict) or set(parsed) != {stage} or not isinstance(parsed[stage], list):
                    raise ValueError("Expected a single stage array")
                records = parsed[stage]
                for row in records:
                    if not isinstance(row, dict) or any(k in row for k in COMMON - {"id"}):
                        raise ValueError("Model supplied protected metadata")
                    if model_fields and set(row) != set(model_fields):
                        raise ValueError("Unexpected fields in compact model response")
                if stage == "dependencies" and transform:
                    valid_rows, rejected = [], []
                    for row in records:
                        try:
                            expanded = transform([row])
                            expanded[0].update(video_id=self.video["video_id"], maturity="CANDIDATE",
                                               review_status="PENDING", provenance=provenance)
                            validate(stage, expanded, self.video, provenance,
                                     window=self.config["current_window_seconds"], **context)
                            valid_rows.extend(expanded)
                        except (ValueError, KeyError, TypeError) as exc:
                            rejection = {"request": name, "attempt": attempt, "id": row.get("id"),
                                         "decision": "REJECT", "reason": str(exc)}
                            rejected.append(rejection)
                            archive = self.report.setdefault("invalid_model_records", [])
                            if rejection not in archive:
                                archive.append(rejection)
                    if not rejected:
                        return validate(stage, valid_rows, self.video, provenance,
                                        window=self.config["current_window_seconds"], **context)
                    retained.extend(valid_rows)
                    # Keep the original first error so a cached repair request has
                    # exactly the same fingerprint as the request actually sent.
                    raise ValueError(rejected[0]["reason"])
                if transform:
                    records = transform(records)
                for row in records:
                    row.update(video_id=self.video["video_id"], maturity="CANDIDATE", review_status="PENDING", provenance=provenance)
                return validate(stage, records, self.video, provenance,
                                window=self.config["current_window_seconds"], **context)
            except (ValueError, KeyError, TypeError) as exc:
                last_error = exc
                self.report["validation_errors"].append({"request": name, "attempt": attempt, "error": str(exc)})
                self.checkpoint()
        if retained:
            unique = {}
            for row in retained:
                unique.setdefault(row["id"], row)
            self.report.setdefault("stage_salvage", {})[stage] = {
                "valid_records_retained": len(unique),
                "note": "Only individually validated records retained from real responses; invalid records rejected and raw responses preserved",
            }
            self.checkpoint()
            return validate(stage, list(unique.values()), self.video, provenance,
                            window=self.config["current_window_seconds"], **context)
        raise ValueError(f"{name} invalid after one structural repair: {last_error}")

    def discover_events(self, video):
        output = []
        duration, step = video["duration_seconds"], self.config["discovery_segment_seconds"]
        for n, start in enumerate(range(0, int(duration) + 1, step)):
            if start >= duration:
                continue
            end = min(start + step, duration)
            if end - start < 1 / self.config["discovery_fps"]:
                self.report["discovery_short_tail"] = {
                    "start": start, "end": end,
                    "note": "Shorter than one coarse sampling period; included in full-video dependency/verification context, no atomic event inferred from tail",
                }
                self.checkpoint()
                continue
            clip = self.clip(start, end, self.config["discovery_fps"])
            records = self.structured("events", f"events{n}",
                self.prompt("events", start=start, end=end), [clip])
            if any(e["interval"]["start"] < start or e["interval"]["end"] > end for r in records for e in r["evidence"]):
                raise ValueError("Event timestamp outside inspected segment")
            output.extend(records)
        self.events = {r["id"]: r for r in output}
        validate("events", output, video, self.stage_provenance("events"))
        return output

    def mine_dependencies(self, video, events):
        self.events = {r["id"]: r for r in events}
        clip = self.clip(0, video["duration_seconds"], self.config["discovery_fps"])
        # Anchors are arithmetic constraints, not constructed questions or answers.
        # Preserve the successful event cache; revise only this failed-stage prompt.
        by_slot = {}
        for event in events:
            query = max(e["interval"]["end"] for e in event["evidence"])
            start = max(0, query - self.config["current_window_seconds"])
            eligible = [r["id"] for r in events if all(e["interval"]["end"] < start for e in r["evidence"])]
            if eligible:
                by_slot[int(query // 30)] = {
                    "query_time": query, "current_window": {"start": start, "end": query},
                    "recent_event_ref": event["id"], "eligible_history_event_refs": eligible,
                }
        if not by_slot:
            return []
        anchors = {f'A{i}': anchor for i, anchor in enumerate(by_slot.values())}

        def expand(rows):
            output = []
            for row in rows:
                if row['anchor_ref'] not in anchors:
                    raise ValueError('Unknown anchor_ref; choose an exact supplied A identifier')
                anchor = anchors[row['anchor_ref']]
                refs = row['history_event_refs']
                if not isinstance(refs, list) or not refs or any(
                    ref not in anchor['eligible_history_event_refs'] for ref in refs
                ) or len(refs) != len(set(refs)):
                    raise ValueError('history_event_refs must be a nonempty unique subset of this anchor eligible list')
                expanded = {k: v for k, v in row.items() if k not in {'anchor_ref', 'history_event_refs'}}
                expanded.update(query_time=anchor['query_time'], current_window=anchor['current_window'],
                                event_refs=refs + [anchor['recent_event_ref']],
                                history_evidence=[e for ref in refs for e in self.events[ref]['evidence']])
                output.append(expanded)
            return output

        return self.structured(
            'dependencies', 'dependencies_refs1',
            self.prompt('dependencies', window_seconds=self.config['current_window_seconds'],
                        events_json=json.dumps(events, ensure_ascii=False), anchors_json=json.dumps(anchors)),
            [clip], model_fields={'id', 'anchor_ref', 'history_event_refs', 'dependency_explanation',
                                  'dependency_type', 'recent_insufficiency', 'alternative_evidence_risk', 'priority'},
            transform=expand, events=self.events,
        )

    def construct_tasks(self, video, dependencies):
        self.dependencies = {r["id"]: r for r in dependencies}
        return self.structured("tasks", "tasks",
            self.prompt('tasks', target_candidates=self.config['target_candidates'],
                        dependencies_json=json.dumps(dependencies, ensure_ascii=False)),
            [], dependencies=self.dependencies)

    def verify_evidence(self, video, tasks):
        # One independent request, no event summaries, teacher answers or explanations.
        # Coarse full-video context is private verification input; no runtime Agent is built.
        selected = tasks[:self.config["max_verifications"]]
        if not selected:
            return []
        coarse = self.clip(0, video["duration_seconds"], self.config["discovery_fps"])
        clips, questions = [coarse], []
        seen = {coarse}
        for task in selected:
            intervals = [e["interval"] for e in task["necessary_history_evidence"]] + [task["current_window"]]
            questions.append({"task_ref": task["id"], "question": task["question"],
                              "query_time": task["query_time"], "checked_intervals": intervals})
            for span in intervals:
                path = self.clip(span["start"], span["end"], self.config["verification_fps"])
                if path not in seen:
                    clips.append(path)
                    seen.add(path)
        return self.structured("verifications", "verification",
            self.prompt('verifications', questions_json=json.dumps(questions, ensure_ascii=False)),
            clips, tasks={r["id"]: r for r in selected})
