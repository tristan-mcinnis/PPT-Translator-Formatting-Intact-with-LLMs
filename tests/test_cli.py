"""Tests for CLI exit-code behaviour."""
from __future__ import annotations

from ppt_translator.cli import run_cli


def test_run_cli_reports_failure_when_processing_fails(tmp_path, monkeypatch):
    """A deck that cannot be parsed must produce a non-zero exit code."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"not a real pptx file")

    exit_code = run_cli([str(bad)])

    assert exit_code == 1