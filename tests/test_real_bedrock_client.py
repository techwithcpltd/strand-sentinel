"""Task 8 (gates A/B/C only): unit tests for RealBedrockClient with the
boto3 client boundary fully mocked via an injected `client_factory` -- no
real boto3.Session, no credential file access, no network call, no AWS
contact of any kind. Every test that constructs the adapter monkeypatches
`boto3.Session` to raise if it's ever called, proving the default
credential-discovery path is never touched.
"""

from __future__ import annotations

import pytest

boto3 = pytest.importorskip("boto3")

from botocore.exceptions import BotoCoreError, ClientError, ConnectTimeoutError  # noqa: E402

from strand_sentinel.adapters.real_bedrock_client import (  # noqa: E402
    BedrockClientConfigurationError,
    RealBedrockClient,
)
from strand_sentinel.models import FailureRecord, FailureStage, GateOutcome, GroundednessAnswer, ProposedToolCall, SyntheticReport  # noqa: E402

REPORT = SyntheticReport(report_id="bedrock-test", text="Synthetic test report text only.")
PROPOSAL = ProposedToolCall(
    tool_name="create_action_brief",
    issue_category="water leak",
    location="Flat 12",
    onset_or_duration="two days ago",
    urgency="urgent",
)
GATE_OUTCOME = GateOutcome(
    overall_answer=GroundednessAnswer(question_id="overall", value="conflicting_evidence", confidence=0.9),
    per_argument_answers=(),
    ungrounded_arguments=(),
    lowest_confidence=0.9,
)


def _forbid_real_session(monkeypatch):
    """If RealBedrockClient's client_factory path ever touches boto3.Session,
    this makes the test fail loudly instead of silently succeeding."""

    def _raise(*args, **kwargs):
        raise AssertionError("boto3.Session must not be constructed when client_factory is provided")

    monkeypatch.setattr(boto3, "Session", _raise)


class _FakeBedrockRuntime:
    """Stands in for a boto3 bedrock-runtime client. Returns a fixed
    response (or raises a fixed exception) from .converse() and records
    every call made."""

    def __init__(self, response_or_exc):
        self._response_or_exc = response_or_exc
        self.converse_calls: list[dict] = []

    def converse(self, **kwargs):
        self.converse_calls.append(kwargs)
        if isinstance(self._response_or_exc, Exception):
            raise self._response_or_exc
        return self._response_or_exc


def _client(monkeypatch, response_or_exc, **kwargs) -> tuple[RealBedrockClient, _FakeBedrockRuntime]:
    _forbid_real_session(monkeypatch)
    fake = _FakeBedrockRuntime(response_or_exc)
    client = RealBedrockClient(
        region_name="us-east-1",
        model_id="us.anthropic.claude-sonnet-5",
        client_factory=lambda: fake,
        **kwargs,
    )
    return client, fake


def _tool_use_response(input_dict: dict) -> dict:
    return {
        "stopReason": "tool_use",
        "output": {
            "message": {
                "content": [
                    {"toolUse": {"toolUseId": "t1", "name": "create_action_brief", "input": input_dict}}
                ]
            }
        },
    }


def _text_response(text: str, stop_reason: str = "end_turn") -> dict:
    return {"stopReason": stop_reason, "output": {"message": {"content": [{"text": text}]}}}


VALID_INPUT = {
    "issue_category": "water leak",
    "location": "Flat 12",
    "onset_or_duration": "two days ago",
    "urgency": "urgent",
}


# --- Construction / configuration safety ---


def test_missing_region_name_raises_configuration_error(monkeypatch):
    _forbid_real_session(monkeypatch)
    with pytest.raises(BedrockClientConfigurationError):
        RealBedrockClient(region_name="", model_id="x", client_factory=lambda: _FakeBedrockRuntime({}))


def test_missing_model_id_raises_configuration_error(monkeypatch):
    _forbid_real_session(monkeypatch)
    with pytest.raises(BedrockClientConfigurationError):
        RealBedrockClient(region_name="us-east-1", model_id="", client_factory=lambda: _FakeBedrockRuntime({}))


def test_missing_profile_and_client_factory_raises_configuration_error(monkeypatch):
    _forbid_real_session(monkeypatch)
    with pytest.raises(BedrockClientConfigurationError):
        RealBedrockClient(region_name="us-east-1", model_id="us.anthropic.claude-sonnet-5")


def test_client_factory_path_never_touches_boto3_session(monkeypatch):
    # _forbid_real_session makes boto3.Session raise; constructing via
    # client_factory must succeed anyway, proving the session path is
    # never reached.
    client, fake = _client(monkeypatch, _tool_use_response(VALID_INPUT))
    assert client is not None
    assert fake.converse_calls == []  # nothing called yet, just constructed


# --- propose_tool_call: successful parsing ---


def test_propose_tool_call_success(monkeypatch):
    client, fake = _client(monkeypatch, _tool_use_response(VALID_INPUT))

    result = client.propose_tool_call(REPORT)

    assert isinstance(result, ProposedToolCall)
    assert result.issue_category == "water leak"
    assert result.location == "Flat 12"
    assert len(fake.converse_calls) == 1
    assert fake.converse_calls[0]["toolConfig"]["toolChoice"] == {"tool": {"name": "create_action_brief"}}


# --- propose_tool_call: every malformed/unexpected case from requirement 10 ---


def test_propose_tool_call_unexpected_stop_reason(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("not a tool call"))
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.stage is FailureStage.BEDROCK
    assert result.error_type == "unexpected-stop-reason"


def test_propose_tool_call_no_tool_use_blocks(monkeypatch):
    response = {"stopReason": "tool_use", "output": {"message": {"content": [{"text": "oops"}]}}}
    client, _ = _client(monkeypatch, response)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "unexpected-tool-use-count"


def test_propose_tool_call_multiple_tool_use_blocks(monkeypatch):
    block = {"toolUse": {"toolUseId": "t1", "name": "create_action_brief", "input": VALID_INPUT}}
    response = {"stopReason": "tool_use", "output": {"message": {"content": [block, block]}}}
    client, _ = _client(monkeypatch, response)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "unexpected-tool-use-count"


def test_propose_tool_call_wrong_tool_name(monkeypatch):
    response = _tool_use_response(VALID_INPUT)
    response["output"]["message"]["content"][0]["toolUse"]["name"] = "some_other_tool"
    client, _ = _client(monkeypatch, response)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "wrong-tool-name"


def test_propose_tool_call_missing_fields(monkeypatch):
    incomplete = dict(VALID_INPUT)
    del incomplete["urgency"]
    client, _ = _client(monkeypatch, _tool_use_response(incomplete))
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "missing-fields"
    assert "urgency" in result.error_message


def test_propose_tool_call_extra_fields(monkeypatch):
    extra = dict(VALID_INPUT, unexpected_field="surprise")
    client, _ = _client(monkeypatch, _tool_use_response(extra))
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "extra-fields"


def test_propose_tool_call_non_string_field(monkeypatch):
    bad = dict(VALID_INPUT, urgency=42)
    client, _ = _client(monkeypatch, _tool_use_response(bad))
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "non-string-fields"


def test_propose_tool_call_malformed_envelope(monkeypatch):
    response = {"stopReason": "tool_use", "output": {}}  # missing message entirely
    client, _ = _client(monkeypatch, response)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "malformed-response-envelope"


def test_propose_tool_call_tool_input_not_an_object(monkeypatch):
    response = _tool_use_response(VALID_INPUT)
    response["output"]["message"]["content"][0]["toolUse"]["input"] = "not-a-dict"
    client, _ = _client(monkeypatch, response)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "malformed-tool-input"


# --- error mapping: ClientError, BotoCoreError, timeout, unexpected exceptions ---


def test_client_error_maps_to_failure_record(monkeypatch):
    exc = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Converse")
    client, _ = _client(monkeypatch, exc)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "client-error"
    assert result.error_message == "ThrottlingException"


def test_botocore_error_maps_to_failure_record(monkeypatch):
    client, _ = _client(monkeypatch, BotoCoreError())
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "transport-error"


def test_timeout_error_maps_to_failure_record(monkeypatch):
    # ConnectTimeoutError is a BotoCoreError subclass -- confirms the timeout
    # case is covered by the same transport-error branch.
    exc = ConnectTimeoutError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com")
    client, _ = _client(monkeypatch, exc)
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "transport-error"


def test_unexpected_exception_maps_to_failure_record(monkeypatch):
    client, _ = _client(monkeypatch, ValueError("something unrelated broke"))
    result = client.propose_tool_call(REPORT)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "unexpected-error"
    assert "something unrelated broke" not in result.error_message  # no raw detail leaked


# --- draft_follow_up_questions ---


def test_follow_up_questions_success(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("When did it start?\nHow urgent is it?"))
    result = client.draft_follow_up_questions(REPORT, PROPOSAL, ("onset_or_duration", "urgency"))
    assert result == ("When did it start?", "How urgent is it?")


def test_follow_up_questions_malformed_line_not_a_question(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("When did it start?\nThis is a statement."))
    result = client.draft_follow_up_questions(REPORT, PROPOSAL, ("onset_or_duration",))
    assert isinstance(result, FailureRecord)
    assert result.error_type == "malformed-follow-up-line"


def test_follow_up_questions_empty_response(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("   \n  "))
    result = client.draft_follow_up_questions(REPORT, PROPOSAL, ("onset_or_duration",))
    assert isinstance(result, FailureRecord)
    assert result.error_type == "empty-follow-up-questions"


def test_follow_up_questions_no_target_arguments(monkeypatch):
    client, fake = _client(monkeypatch, _text_response("irrelevant"))
    result = client.draft_follow_up_questions(REPORT, PROPOSAL, ())
    assert isinstance(result, FailureRecord)
    assert result.error_type == "no-target-arguments"
    assert fake.converse_calls == []  # never even called Bedrock


# --- draft_conflict_summary ---


def test_conflict_summary_success(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("The two accounts conflict and need human review."))
    result = client.draft_conflict_summary(REPORT, PROPOSAL, GATE_OUTCOME)
    assert result == "The two accounts conflict and need human review."


def test_conflict_summary_empty_response(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("   "))
    result = client.draft_conflict_summary(REPORT, PROPOSAL, GATE_OUTCOME)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "empty-conflict-summary"


def test_conflict_summary_unexpected_stop_reason(monkeypatch):
    client, _ = _client(monkeypatch, _text_response("partial", stop_reason="tool_use"))
    result = client.draft_conflict_summary(REPORT, PROPOSAL, GATE_OUTCOME)
    assert isinstance(result, FailureRecord)
    assert result.error_type == "unexpected-stop-reason"


# --- the adapter never executes the proposed tool ---


def test_adapter_never_calls_tool_execution_function(monkeypatch):
    import strand_sentinel.tool as tool_module

    calls: list = []
    monkeypatch.setattr(tool_module, "create_action_brief", lambda *a, **kw: calls.append((a, kw)))

    client, _ = _client(monkeypatch, _tool_use_response(VALID_INPUT))
    result = client.propose_tool_call(REPORT)

    assert isinstance(result, ProposedToolCall)  # parsed, not executed
    assert calls == []  # create_action_brief was never invoked by the adapter
