"""The three required synthetic demo fixtures (Requirement 8).

Each fixture pairs a fabricated SyntheticReport with the scripted
ProposedToolCall and GroundednessAnswers that StubBedrockClient and
StubDeciderClient return in tests. Nothing here is produced by a real
model — these are fixed, hand-authored values proving the intended outcome
through the already-tested router (strand_sentinel.routing.route).
"""

from __future__ import annotations

from pathlib import Path

from strand_sentinel.models import GroundednessAnswer, ProposedToolCall, SyntheticReport

_FIXTURES_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    return (_FIXTURES_DIR / filename).read_text(encoding="utf-8")


def question_id(fixture_id: str, part: str) -> str:
    """Shared naming convention for a fixture's questions: 'overall' or one
    of the four argument names. Used both to build scripted answers here and
    to build GroundednessQuestion objects in tests, so the two always agree.
    """

    return f"{fixture_id}:{part}"


PROCEED_FIXTURE_ID = "proceed"
GUIDE_FIXTURE_ID = "guide"
ESCALATE_FIXTURE_ID = "escalate"

PROCEED_REPORT = SyntheticReport(report_id=PROCEED_FIXTURE_ID, text=_load("proceed.txt"))
GUIDE_REPORT = SyntheticReport(report_id=GUIDE_FIXTURE_ID, text=_load("guide.txt"))
ESCALATE_REPORT = SyntheticReport(report_id=ESCALATE_FIXTURE_ID, text=_load("escalate.txt"))

ALL_REPORTS = (PROCEED_REPORT, GUIDE_REPORT, ESCALATE_REPORT)

# --- Scripted Bedrock proposals (what Bedrock would propose for each report) ---

PROCEED_PROPOSAL = ProposedToolCall(
    tool_name="create_action_brief",
    issue_category="plumbing leak (kitchen sink)",
    location="Unit 4B, 12 Birchwood Close — kitchen",
    onset_or_duration="3 days",
    urgency="high",
)

GUIDE_PROPOSAL = ProposedToolCall(
    tool_name="create_action_brief",
    issue_category="mould (bathroom ceiling)",
    location="Unit 7, 48 Elm Street — bathroom",
    onset_or_duration="not stated",
    urgency="not stated",
)

ESCALATE_PROPOSAL = ProposedToolCall(
    tool_name="create_action_brief",
    issue_category="heating outage",
    location="Unit 2, 9 Maple Road",
    onset_or_duration="conflicting: about a week vs. about an hour yesterday",
    urgency="conflicting: dangerously cold vs. resolved, not urgent",
)

# --- Scripted Decider answers, keyed by question_id(fixture_id, part) ---

PROCEED_ANSWERS: dict[str, GroundednessAnswer] = {
    question_id(PROCEED_FIXTURE_ID, "overall"): GroundednessAnswer(
        question_id=question_id(PROCEED_FIXTURE_ID, "overall"), value="grounded", confidence=0.95
    ),
    question_id(PROCEED_FIXTURE_ID, "issue_category"): GroundednessAnswer(
        question_id=question_id(PROCEED_FIXTURE_ID, "issue_category"), value="yes", confidence=0.93
    ),
    question_id(PROCEED_FIXTURE_ID, "location"): GroundednessAnswer(
        question_id=question_id(PROCEED_FIXTURE_ID, "location"), value="yes", confidence=0.94
    ),
    question_id(PROCEED_FIXTURE_ID, "onset_or_duration"): GroundednessAnswer(
        question_id=question_id(PROCEED_FIXTURE_ID, "onset_or_duration"), value="yes", confidence=0.90
    ),
    question_id(PROCEED_FIXTURE_ID, "urgency"): GroundednessAnswer(
        question_id=question_id(PROCEED_FIXTURE_ID, "urgency"), value="yes", confidence=0.91
    ),
}

GUIDE_ANSWERS: dict[str, GroundednessAnswer] = {
    question_id(GUIDE_FIXTURE_ID, "overall"): GroundednessAnswer(
        question_id=question_id(GUIDE_FIXTURE_ID, "overall"), value="missing_evidence", confidence=0.88
    ),
    question_id(GUIDE_FIXTURE_ID, "issue_category"): GroundednessAnswer(
        question_id=question_id(GUIDE_FIXTURE_ID, "issue_category"), value="yes", confidence=0.92
    ),
    question_id(GUIDE_FIXTURE_ID, "location"): GroundednessAnswer(
        question_id=question_id(GUIDE_FIXTURE_ID, "location"), value="yes", confidence=0.90
    ),
    question_id(GUIDE_FIXTURE_ID, "onset_or_duration"): GroundednessAnswer(
        question_id=question_id(GUIDE_FIXTURE_ID, "onset_or_duration"), value="no", confidence=0.85
    ),
    question_id(GUIDE_FIXTURE_ID, "urgency"): GroundednessAnswer(
        question_id=question_id(GUIDE_FIXTURE_ID, "urgency"), value="no", confidence=0.85
    ),
}

ESCALATE_ANSWERS: dict[str, GroundednessAnswer] = {
    question_id(ESCALATE_FIXTURE_ID, "overall"): GroundednessAnswer(
        question_id=question_id(ESCALATE_FIXTURE_ID, "overall"),
        value="conflicting_evidence",
        confidence=0.90,
    ),
    question_id(ESCALATE_FIXTURE_ID, "issue_category"): GroundednessAnswer(
        question_id=question_id(ESCALATE_FIXTURE_ID, "issue_category"), value="yes", confidence=0.90
    ),
    question_id(ESCALATE_FIXTURE_ID, "location"): GroundednessAnswer(
        question_id=question_id(ESCALATE_FIXTURE_ID, "location"), value="yes", confidence=0.90
    ),
    # Deliberately low confidence on the conflicting arguments: proves the
    # conflicting_evidence branch wins over the low-confidence Guide fallback.
    question_id(ESCALATE_FIXTURE_ID, "onset_or_duration"): GroundednessAnswer(
        question_id=question_id(ESCALATE_FIXTURE_ID, "onset_or_duration"), value="no", confidence=0.30
    ),
    question_id(ESCALATE_FIXTURE_ID, "urgency"): GroundednessAnswer(
        question_id=question_id(ESCALATE_FIXTURE_ID, "urgency"), value="no", confidence=0.30
    ),
}

# --- Scripted Bedrock outputs for the Guide and Escalate (conflicting-
# evidence) paths — Task 4 additions, used by the pipeline's second Bedrock
# call on each of those two paths. ---

GUIDE_FOLLOW_UP_QUESTIONS: tuple[str, ...] = (
    "When did the mould on the bathroom ceiling first appear?",
    "How urgent does the tenant consider this issue to be?",
)

ESCALATE_CONFLICT_SUMMARY: str = (
    "The tenant gave two different accounts of the heating outage's duration "
    "and severity during the same visit: one describing roughly a week of "
    "dangerously cold conditions, and another describing a single one-hour "
    "outage that has since been resolved. These accounts conflict and have "
    "not been reconciled; human review is needed to determine which, if "
    "either, is accurate."
)
