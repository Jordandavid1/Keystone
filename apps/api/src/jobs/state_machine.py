"""
KEYSTONE Job State Machine Engine
Implements the 13 discrete job states, 4 terminal states, transition matrix,
idempotent transitions, bounded retries, and cognitive replan loops.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class JobState(str, enum.Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    PLANNING = "PLANNING"
    AUTHORIZING = "AUTHORIZING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING_OUTPUT = "VALIDATING_OUTPUT"
    RETRY_PENDING = "RETRY_PENDING"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


STATES: List[str] = [s.value for s in JobState]

TERMINAL_STATES: List[str] = [
    JobState.COMPLETED.value,
    JobState.FAILED.value,
    JobState.CANCELLED.value,
    JobState.REJECTED.value,
]

ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    JobState.CREATED.value: [
        JobState.VALIDATING.value,
        JobState.CANCELLED.value,
        JobState.REJECTED.value,
    ],
    JobState.VALIDATING.value: [
        JobState.PLANNING.value,
        JobState.FAILED.value,
        JobState.CANCELLED.value,
        JobState.REJECTED.value,
    ],
    JobState.PLANNING.value: [
        JobState.AUTHORIZING.value,
        JobState.FAILED.value,
        JobState.CANCELLED.value,
    ],
    JobState.AUTHORIZING.value: [
        JobState.QUEUED.value,
        JobState.REJECTED.value,
        JobState.CANCELLED.value,
        JobState.PLANNING.value,
    ],
    JobState.QUEUED.value: [
        JobState.RUNNING.value,
        JobState.CANCELLED.value,
        JobState.FAILED.value,
    ],
    JobState.RUNNING.value: [
        JobState.VALIDATING_OUTPUT.value,
        JobState.RETRY_PENDING.value,
        JobState.FAILED.value,
        JobState.CANCELLED.value,
    ],
    JobState.VALIDATING_OUTPUT.value: [
        JobState.COMPLETED.value,
        JobState.RETRY_PENDING.value,
        JobState.REPLAN_REQUIRED.value,
        JobState.FAILED.value,
    ],
    JobState.RETRY_PENDING.value: [
        JobState.QUEUED.value,
        JobState.FAILED.value,
        JobState.CANCELLED.value,
    ],
    JobState.REPLAN_REQUIRED.value: [
        JobState.PLANNING.value,
        JobState.FAILED.value,
        JobState.CANCELLED.value,
    ],
    JobState.COMPLETED.value: [],
    JobState.FAILED.value: [],
    JobState.CANCELLED.value: [],
    JobState.REJECTED.value: [],
}

# Worker lifecycle aliases mapping to canonical states
LIFECYCLE_ALIASES: Dict[str, str] = {
    "COMPILING_PROMPT": "VALIDATING",
    "PROPOSED_ACTION_PENDING": "PLANNING",
    "AWAITING_AUTHORIZATION": "AUTHORIZING",
    "ENVELOPE_ISSUED": "QUEUED",
    "DISPATCHED_TO_WORKER": "RUNNING",
    "WORKER_RUNNING": "RUNNING",
    "EVALUATING_OUTPUT": "VALIDATING_OUTPUT",
}


def normalize_state(state: str) -> str:
    """Resolves worker aliases or lowercase strings to canonical uppercase states."""
    s = state.strip().upper()
    return LIFECYCLE_ALIASES.get(s, s)


def transition(current_state: str, next_state: str) -> str:
    """
    Executes a deterministic state transition according to the Keystone Job State Machine.

    Raises:
        ValueError: UNKNOWN_CURRENT_STATE if current_state is unrecognized
        ValueError: UNKNOWN_NEXT_STATE if next_state is unrecognized
        ValueError: ILLEGAL_TRANSITION if transitioning out of terminal state or illegal jump
    """
    if current_state not in STATES:
        raise ValueError(f"UNKNOWN_CURRENT_STATE: {current_state}")
    if next_state not in STATES:
        raise ValueError(f"UNKNOWN_NEXT_STATE: {next_state}")

    # Idempotent no-op
    if current_state == next_state:
        return current_state

    # Guard terminal states
    if current_state in TERMINAL_STATES:
        raise ValueError(f"ILLEGAL_TRANSITION: Cannot transition out of terminal state {current_state}")

    # Verify transition matrix
    allowed = ALLOWED_TRANSITIONS.get(current_state, [])
    if next_state not in allowed:
        raise ValueError(f"ILLEGAL_TRANSITION: Transition from {current_state} to {next_state} is not permitted")

    return next_state


class JobStateMachine:
    """Instance state machine managing job lifecycle transitions and history."""

    STATES = STATES
    TERMINAL_STATES = TERMINAL_STATES
    ALLOWED_TRANSITIONS = ALLOWED_TRANSITIONS

    def __init__(
        self,
        job_id: str,
        initial_state: str = "CREATED",
        max_attempts: int = 3
    ) -> None:
        self.job_id = job_id
        self.current_state = normalize_state(initial_state)
        self.max_attempts = max_attempts
        self.current_attempt = 1
        self.history: List[Dict[str, Any]] = [
            {
                "state": self.current_state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Job initialized"
            }
        ]

    def transition(self, next_state: str, reason: Optional[str] = None) -> str:
        """Transitions job to next state, updating history."""
        target = normalize_state(next_state)
        self.current_state = transition(self.current_state, target)
        self.history.append({
            "state": self.current_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason or "State transition"
        })
        return self.current_state

    def can_retry(self) -> bool:
        return self.current_attempt < self.max_attempts

    def increment_attempt(self) -> int:
        self.current_attempt += 1
        return self.current_attempt

    @property
    def is_terminal(self) -> bool:
        return self.current_state in TERMINAL_STATES
