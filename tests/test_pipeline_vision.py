"""Tests for the vision audit step of the pipeline."""
from __future__ import annotations

import pytest

from ppt_translator import pipeline
from ppt_translator.vision_audit import VisionAuditError, VisionAuditor


def test_run_vision_audit_skips_gracefully_when_rendering_fails(tmp_path, capsys, monkeypatch):
    """A missing renderer must not abort the pipeline or crash the audit."""
    def _boom(*args, **kwargs):
        raise VisionAuditError("Visual audit needs external tools that were not found")

    monkeypatch.setattr(pipeline, "render_deck_to_images", _boom)
    deck = tmp_path / "deck_translated.pptx"
    deck.write_bytes(b"placeholder")

    pipeline.run_vision_audit(deck, tmp_path, vision_auditor=VisionAuditor(client=object()))

    out = capsys.readouterr().out
    assert "Visual audit skipped" in out
    assert not (tmp_path / "deck_translated_audit_images").exists()


def test_run_vision_audit_writes_report_and_summary(tmp_path, capsys, monkeypatch):
    """A successful audit writes the markdown report and prints findings."""
    images = [tmp_path / "slide-1.png"]

    class FakeAuditor:
        model = "test-vision"

        def audit_deck(self, image_paths, *, expected_texts_by_slide=None):
            assert list(image_paths) == images
            return [
                {"slide": 1, "severity": "high", "type": "truncated", "description": "clipped text"},
            ]

    monkeypatch.setattr(pipeline, "render_deck_to_images", lambda *a, **k: images)
    monkeypatch.setattr(pipeline, "collect_slide_texts", lambda path: {1: ["你好"]})
    deck = tmp_path / "deck_translated.pptx"
    deck.write_bytes(b"placeholder")

    pipeline.run_vision_audit(
        deck, tmp_path, vision_auditor=FakeAuditor(), cleanup_images=False
    )

    report = tmp_path / "deck_translated_vision_audit.md"
    assert report.exists()
    assert "clipped text" in report.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "HIGH slide 1" in out and "report saved" in out