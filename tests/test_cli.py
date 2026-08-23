"""Tests for CLI exit-code behaviour."""
from __future__ import annotations

import pytest

from ppt_translator.cli import build_parser, run_cli


def test_run_cli_reports_failure_when_processing_fails(tmp_path, monkeypatch):
    """A deck that cannot be parsed must produce a non-zero exit code."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"not a real pptx file")

    exit_code = run_cli([str(bad)])

    assert exit_code == 1


def test_vision_audit_flag_requires_api_key(tmp_path, monkeypatch):
    """--vision-audit without DEEPSEEK_API_KEY must fail fast with a clear error."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    missing = tmp_path / "missing.pptx"

    with pytest.raises(SystemExit) as excinfo:
        run_cli(["--vision-audit", str(missing)])

    assert excinfo.value.code == 2


def test_vision_audit_flags_have_expected_defaults(capsys):
    parser = build_parser()
    args = parser.parse_args(["deck.pptx", "--vision-audit"])
    assert args.vision_audit is True
    assert args.vision_model == "deepseek-v4-flash-vision-exp"
    assert args.vision_dpi == 100

    default = parser.parse_args(["deck.pptx"])
    assert default.vision_audit is False
