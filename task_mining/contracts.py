"""Provisional JSON-serializable intermediate types, separate from benchmark Schema.

TypedDict describes interfaces only; it does not validate model responses at runtime.
No model implementation, automatic approval, benchmark export or Gold type exists here.
"""

from typing import Literal, Protocol, TypedDict


class Interval(TypedDict):
    start: float
    end: float


class VideoInput(TypedDict):
    video_id: str
    path: str
    sha256: str
    duration_seconds: float


class Provenance(TypedDict):
    provider: str
    model: str
    prompt_version: str
    run_id: str


class Candidate(TypedDict):
    id: str
    video_id: str
    maturity: Literal["CANDIDATE"]
    review_status: Literal["PENDING"]
    provenance: Provenance


class VideoEvidence(TypedDict):
    id: str
    video_id: str
    interval: Interval
    claim: str


class EventCandidate(Candidate):
    description: str
    evidence: list[VideoEvidence]


class DependencyCandidate(Candidate):
    event_refs: list[str]
    query_time: float
    current_window: Interval
    history_evidence: list[VideoEvidence]
    dependency_explanation: str


class HistoryMask(TypedDict):
    operation: Literal["omit_video_intervals"]
    intervals: list[Interval]
    preserve_timestamps: Literal[True]
    comparison: Literal["full_history_vs_masked_history"]


class TaskCandidate(Candidate):
    track: Literal["T1", "T2", "T3"]
    dependency_refs: list[str]
    query_time: float
    current_window: Interval
    question: str
    proposed_answer: str
    necessary_history_evidence: list[VideoEvidence]
    dependency_explanation: str
    history_mask: HistoryMask


class VerificationResult(Candidate):
    task_ref: str
    inspected_evidence: list[VideoEvidence]
    verdict: Literal["SUPPORTED", "UNSUPPORTED", "UNCERTAIN"]
    notes: str


class FilteringDecision(Candidate):
    task_ref: str
    verification_refs: list[str]
    decision: Literal["SEND_TO_HUMAN", "REJECT", "NEEDS_MORE_EVIDENCE"]
    reasons: list[str]


class MiningBackend(Protocol):
    """First extension point for a real video model; methods are not implemented."""

    def discover_events(self, video: VideoInput) -> list[EventCandidate]: ...

    def mine_dependencies(
        self, video: VideoInput, events: list[EventCandidate],
    ) -> list[DependencyCandidate]: ...

    def construct_tasks(
        self, video: VideoInput, dependencies: list[DependencyCandidate],
    ) -> list[TaskCandidate]: ...

    def verify_evidence(
        self, video: VideoInput, tasks: list[TaskCandidate],
    ) -> list[VerificationResult]: ...
