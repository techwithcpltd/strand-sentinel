"""Real Amazon Bedrock adapter (Task 8, gates A/B/C only).

Wraps the Bedrock Converse API behind the existing BedrockClient contract
(strand_sentinel.adapters.bedrock_client). This module does NOT import
`boto3`/`botocore` at module load time -- those imports happen lazily,
inside `__init__` or inside call methods -- so merely importing this file
never requires boto3 to be installed, and never touches AWS credentials.
No AWS session or client is ever constructed at module scope.

Status: offline/mock-verified only (Task 8 gates A, B, C). This adapter has
NOT been exercised against a live Bedrock endpoint -- no AWS credentials,
account, region, model access, Marketplace subscription, or live model ID
have been approved for use. See
patterns/evidence_groundedness_gate/INTEGRATION.md for the full status.

Confirmed facts this adapter is built against (official AWS documentation,
not assumed):
  - Converse requires `bedrock:InvokeModel` IAM permission; denying
    InvokeModel also blocks Converse.
  - A forced tool-use Converse call returns `stopReason == "tool_use"` and a
    `toolUse` content block with `name` and `input` (the tool's proposed
    arguments) -- this adapter never executes that tool itself; it only
    parses the request and hands a `ProposedToolCall` back to the caller.
    Execution remains exclusively in the application pipeline, gated on
    Strands Decider's routing decision (Requirement 4.4).
  - Structured-output support (`outputConfig.textFormat`) was seen only in
    the CLI parameter reference, not in a complete boto3 code example, so
    the two generation methods below deliberately use plain-text Converse
    calls with strict, self-validated parsing instead -- the more
    conservative choice per this task's instructions, not a guess at an
    unverified structured-output API shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from strand_sentinel.models import (
    FailureRecord,
    FailureStage,
    GateOutcome,
    ProposedToolCall,
    SyntheticReport,
)

_CREATE_ACTION_BRIEF_TOOL_NAME = "create_action_brief"
_CREATE_ACTION_BRIEF_FIELDS: tuple[str, ...] = (
    "issue_category",
    "location",
    "onset_or_duration",
    "urgency",
)

_CREATE_ACTION_BRIEF_TOOL_SPEC: dict[str, Any] = {
    "toolSpec": {
        "name": _CREATE_ACTION_BRIEF_TOOL_NAME,
        "description": (
            "Propose arguments for a human-triage action brief, grounded "
            "only in the given synthetic report."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {name: {"type": "string"} for name in _CREATE_ACTION_BRIEF_FIELDS},
                "required": list(_CREATE_ACTION_BRIEF_FIELDS),
                "additionalProperties": False,
            }
        },
    }
}

_TEXT_STOP_REASONS = ("end_turn", "stop_sequence", "max_tokens")


class BedrockClientConfigurationError(Exception):
    """Raised at construction time when RealBedrockClient is missing the
    explicit configuration required to invoke Bedrock safely. Never falls
    back to boto3's default credential/profile discovery.
    """


class RealBedrockClient:
    """Real Bedrock adapter. Requires explicit region, model ID, and either
    an explicit profile name or an explicit client factory -- construction
    fails loudly (requirement 6) rather than silently using boto3's default
    credential chain (requirement 2).

    `client_factory`, when provided, is called with no arguments and must
    return an object exposing a Bedrock-runtime-compatible `.converse(...)`
    method. This is the only path exercised by this project's tests
    (requirement: tests use injected mocked boto3 Session/client
    boundaries) -- it never touches boto3.Session or any credential file.

    `profile_name`, when provided instead, is the real-use path: it builds
    a `boto3.Session(profile_name=...)` and a bounded-timeout,
    standard-retry `bedrock-runtime` client from it. This path is not
    exercised by any test in this repository and requires separate
    approval (Task 8 gates D/E) before ever being used for a live call.
    """

    def __init__(
        self,
        *,
        region_name: str,
        model_id: str,
        profile_name: str | None = None,
        client_factory: Callable[[], Any] | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        max_attempts: int = 3,
    ) -> None:
        if not region_name:
            raise BedrockClientConfigurationError("region_name is required and must be explicit.")
        if not model_id:
            raise BedrockClientConfigurationError("model_id is required and must be explicit.")
        if not profile_name and client_factory is None:
            raise BedrockClientConfigurationError(
                "Either an explicit profile_name or an explicit client_factory must be "
                "provided. RealBedrockClient never falls back to boto3's default "
                "credential/profile discovery."
            )

        self._region_name = region_name
        self._model_id = model_id

        if client_factory is not None:
            self._client = client_factory()
        else:
            import boto3  # lazy: optional dependency, real-use path only
            from botocore.config import Config

            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            self._client = session.client(
                "bedrock-runtime",
                region_name=region_name,
                config=Config(
                    connect_timeout=connect_timeout,
                    read_timeout=read_timeout,
                    retries={"max_attempts": max_attempts, "mode": "standard"},
                ),
            )

    # --- BedrockClient contract ---

    def propose_tool_call(self, report: SyntheticReport) -> ProposedToolCall | FailureRecord:
        messages = [{"role": "user", "content": [{"text": _propose_prompt(report)}]}]
        tool_config = {
            "tools": [_CREATE_ACTION_BRIEF_TOOL_SPEC],
            "toolChoice": {"tool": {"name": _CREATE_ACTION_BRIEF_TOOL_NAME}},
        }
        result = self._converse(messages=messages, tool_config=tool_config)
        if isinstance(result, FailureRecord):
            return result
        return self._parse_tool_use(result)

    def draft_follow_up_questions(
        self,
        report: SyntheticReport,
        proposal: ProposedToolCall,
        target_arguments: tuple[str, ...],
    ) -> tuple[str, ...] | FailureRecord:
        if not target_arguments:
            return self._failure("no-target-arguments", "target_arguments was empty")

        messages = [
            {"role": "user", "content": [{"text": _followup_prompt(report, proposal, target_arguments)}]}
        ]
        result = self._converse(messages=messages)
        if isinstance(result, FailureRecord):
            return result
        return self._parse_follow_up_questions(result)

    def draft_conflict_summary(
        self,
        report: SyntheticReport,
        proposal: ProposedToolCall,
        gate_outcome: GateOutcome,
    ) -> str | FailureRecord:
        messages = [{"role": "user", "content": [{"text": _conflict_prompt(report, proposal, gate_outcome)}]}]
        result = self._converse(messages=messages)
        if isinstance(result, FailureRecord):
            return result
        return self._parse_conflict_summary(result)

    # --- internals ---

    def _converse(self, *, messages: list[dict], tool_config: dict | None = None) -> dict | FailureRecord:
        from botocore.exceptions import BotoCoreError, ClientError  # lazy

        kwargs: dict[str, Any] = {"modelId": self._model_id, "messages": messages}
        if tool_config is not None:
            kwargs["toolConfig"] = tool_config

        try:
            return self._client.converse(**kwargs)
        except ClientError as exc:
            error = getattr(exc, "response", {}).get("Error", {})
            return self._failure("client-error", error.get("Code", type(exc).__name__))
        except BotoCoreError as exc:
            # Covers transport errors and timeouts: botocore's Connect/Read
            # timeout exceptions are BotoCoreError subclasses.
            return self._failure("transport-error", type(exc).__name__)
        except Exception as exc:  # never silently guessed -- always a FailureRecord
            return self._failure("unexpected-error", type(exc).__name__)

    def _parse_tool_use(self, response: dict) -> ProposedToolCall | FailureRecord:
        stop_reason = response.get("stopReason")
        if stop_reason != "tool_use":
            return self._failure("unexpected-stop-reason", str(stop_reason))

        content = _message_content(response)
        if content is None:
            return self._failure("malformed-response-envelope", "missing output.message.content")

        tool_use_blocks = [block["toolUse"] for block in content if isinstance(block, dict) and "toolUse" in block]
        if len(tool_use_blocks) != 1:
            return self._failure("unexpected-tool-use-count", str(len(tool_use_blocks)))

        tool_use = tool_use_blocks[0]
        if tool_use.get("name") != _CREATE_ACTION_BRIEF_TOOL_NAME:
            return self._failure("wrong-tool-name", str(tool_use.get("name")))

        tool_input = tool_use.get("input")
        if not isinstance(tool_input, dict):
            return self._failure("malformed-tool-input", "input is not an object")

        missing = [f for f in _CREATE_ACTION_BRIEF_FIELDS if f not in tool_input]
        if missing:
            return self._failure("missing-fields", ",".join(missing))

        extra = [k for k in tool_input if k not in _CREATE_ACTION_BRIEF_FIELDS]
        if extra:
            return self._failure("extra-fields", ",".join(extra))

        non_string = [f for f in _CREATE_ACTION_BRIEF_FIELDS if not isinstance(tool_input[f], str)]
        if non_string:
            return self._failure("non-string-fields", ",".join(non_string))

        return ProposedToolCall(
            tool_name=_CREATE_ACTION_BRIEF_TOOL_NAME,
            issue_category=tool_input["issue_category"],
            location=tool_input["location"],
            onset_or_duration=tool_input["onset_or_duration"],
            urgency=tool_input["urgency"],
        )

    def _parse_follow_up_questions(self, response: dict) -> tuple[str, ...] | FailureRecord:
        text = self._single_text_block(response)
        if isinstance(text, FailureRecord):
            return text

        lines = [line.strip() for line in text.splitlines()]
        questions = tuple(line for line in lines if line)

        if not questions:
            return self._failure("empty-follow-up-questions", "no non-empty lines")

        non_questions = [q for q in questions if not q.endswith("?")]
        if non_questions:
            return self._failure(
                "malformed-follow-up-line", f"{len(non_questions)} line(s) did not end with '?'"
            )

        return questions

    def _parse_conflict_summary(self, response: dict) -> str | FailureRecord:
        text = self._single_text_block(response)
        if isinstance(text, FailureRecord):
            return text

        summary = text.strip()
        if not summary:
            return self._failure("empty-conflict-summary", "response text was empty")

        return summary

    def _single_text_block(self, response: dict) -> str | FailureRecord:
        stop_reason = response.get("stopReason")
        if stop_reason not in _TEXT_STOP_REASONS:
            return self._failure("unexpected-stop-reason", str(stop_reason))

        content = _message_content(response)
        if content is None:
            return self._failure("malformed-response-envelope", "missing output.message.content")

        text_blocks = [block["text"] for block in content if isinstance(block, dict) and "text" in block]
        if len(text_blocks) != 1:
            return self._failure("unexpected-text-block-count", str(len(text_blocks)))

        return text_blocks[0]

    def _failure(self, error_type: str, detail: str) -> FailureRecord:
        # Deliberately short and generic: never the prompt, the report text,
        # credentials, account IDs, or the raw provider response body.
        return FailureRecord(
            stage=FailureStage.BEDROCK,
            error_type=error_type,
            error_message=detail,
            occurred_at=datetime.now(timezone.utc),
        )


def _message_content(response: dict) -> list | None:
    output = response.get("output")
    if not isinstance(output, dict):
        return None
    message = output.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    return content


def _propose_prompt(report: SyntheticReport) -> str:
    return (
        "You are drafting proposed arguments for a human-triage action brief "
        "from a synthetic housing-condition report. Call the "
        f"'{_CREATE_ACTION_BRIEF_TOOL_NAME}' tool with your best proposed values "
        "for issue_category, location, onset_or_duration, and urgency, based "
        "only on this report:\n\n" + report.text
    )


def _followup_prompt(
    report: SyntheticReport, proposal: ProposedToolCall, target_arguments: tuple[str, ...]
) -> str:
    args_list = ", ".join(target_arguments)
    return (
        "The following proposed argument(s) could not be confirmed as explicitly "
        f"supported by the report: {args_list}. Write one focused follow-up "
        "question per argument, each on its own line, each ending in '?', and "
        "nothing else.\n\nReport:\n" + report.text + "\n\nProposed arguments:\n"
        + str(_proposal_as_dict(proposal))
    )


def _conflict_prompt(report: SyntheticReport, proposal: ProposedToolCall, gate_outcome: GateOutcome) -> str:
    return (
        "The report contains conflicting evidence relevant to the proposed "
        "action brief arguments. Write a short, neutral summary of the "
        "conflict for human review. Do not resolve the conflict yourself.\n\n"
        "Report:\n" + report.text + "\n\nProposed arguments:\n" + str(_proposal_as_dict(proposal))
    )


def _proposal_as_dict(proposal: ProposedToolCall) -> dict[str, str]:
    return {
        "issue_category": proposal.issue_category,
        "location": proposal.location,
        "onset_or_duration": proposal.onset_or_duration,
        "urgency": proposal.urgency,
    }
