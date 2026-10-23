"""Task 9: focused tests for the minimal local CLI demo runner. Fully
offline -- default behaviour uses only the deterministic stub adapters, no
AWS, no boto3, no real Bedrock, no real Decider.
"""

from __future__ import annotations

import inspect

import pytest

from strand_sentinel import cli
from strand_sentinel.constants import DISCLAIMER


def test_proceed_scenario_runs_tool_and_prints_disclaimer(tmp_path, capsys):
    exit_code = cli.main(["proceed", "--audit-dir", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Final route: proceed" in out
    assert "Simulated tool executed: True" in out
    assert DISCLAIMER in out
    assert any(tmp_path.iterdir())  # an audit file was written


def test_guide_scenario_blocks_tool_and_shows_follow_ups(tmp_path, capsys):
    exit_code = cli.main(["guide", "--audit-dir", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Final route: guide" in out
    assert "Simulated tool executed: False" in out
    assert "Follow-up questions:" in out
    assert DISCLAIMER in out


def test_escalate_scenario_blocks_tool_and_shows_summary(tmp_path, capsys):
    exit_code = cli.main(["escalate", "--audit-dir", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Final route: escalate" in out
    assert "Simulated tool executed: False" in out
    assert "Escalation summary:" in out
    assert DISCLAIMER in out


def test_invalid_scenario_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["not-a-real-scenario", "--audit-dir", str(tmp_path)])


def test_default_audit_dir_is_the_gitignored_audit_directory():
    source = inspect.getsource(cli)
    assert '"--audit-dir"' in source
    assert 'default="audit"' in source  # matches the .gitignore'd audit/ directory


def test_cli_module_never_imports_boto3_or_real_bedrock():
    # Prose in docstrings legitimately mentions "never uses boto3/Bedrock"
    # (see the module docstring) -- what matters is that no import or
    # construction of either actually happens anywhere in the module.
    source = inspect.getsource(cli)
    assert "import boto3" not in source
    assert "real_bedrock_client" not in source
    assert "RealBedrockClient" not in source


def test_audit_record_written_to_explicit_output_path(tmp_path, capsys):
    custom_dir = tmp_path / "custom-audit-location"
    exit_code = cli.main(["proceed", "--audit-dir", str(custom_dir)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert custom_dir.exists()
    assert any(custom_dir.iterdir())
    assert str(custom_dir) in out  # printed audit path reflects the explicit option


def test_real_decider_flag_is_opt_in_and_off_by_default():
    source = inspect.getsource(cli)
    assert "--real-decider" in source
    assert "action=\"store_true\"" in source  # off unless explicitly passed
    assert "local MLX inference" in source  # clearly labelled local-only
