"""Command line interface for the PPT translator."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .providers import ProviderConfigurationError, create_provider, list_providers
from .translation import TranslationService
from .pipeline import process_ppt_file
from .utils import clean_path, iter_presentation_files
from .vision_audit import DEFAULT_VISION_MODEL, VisionAuditError, build_default_vision_auditor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate PowerPoint decks using modern LLM providers.")
    parser.add_argument("path", help="Path to a PPT/PPTX file or a directory containing presentations.")
    parser.add_argument("--source-lang", default="zh", help="Source language code (default: zh).")
    parser.add_argument("--target-lang", default="en", help="Target language code (default: en).")
    parser.add_argument(
        "--provider",
        default="deepseek",
        choices=list_providers(),
        help="Model provider to use for translation (default: deepseek, model deepseek-v4-flash).",
    )
    parser.add_argument("--model", help="Optional model override for the chosen provider.")
    parser.add_argument(
        "--max-chunk-size",
        type=int,
        default=1000,
        help="Maximum characters per translation request.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Number of worker threads used while reading slides.",
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep intermediate XML files instead of deleting them.",
    )
    parser.add_argument(
        "--vision-audit",
        action="store_true",
        help=(
            "After translation, render every slide of the rebuilt deck and "
            f"inspect it with the DeepSeek vision model ({DEFAULT_VISION_MODEL}) "
            "for overflow, truncation or garbled text. Requires DEEPSEEK_API_KEY."
        ),
    )
    parser.add_argument(
        "--vision-model",
        default=DEFAULT_VISION_MODEL,
        help=f"Vision model used with --vision-audit (default: {DEFAULT_VISION_MODEL}).",
    )
    parser.add_argument(
        "--vision-dpi",
        type=int,
        default=100,
        help="Resolution used to render slides for the visual audit (default: 100).",
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target_path = Path(clean_path(args.path)).expanduser().resolve()

    try:
        provider = create_provider(args.provider, model=args.model)
    except ProviderConfigurationError as exc:
        parser.error(str(exc))
    except ValueError as exc:
        parser.error(str(exc))

    translator = TranslationService(provider, max_chunk_size=args.max_chunk_size)

    vision_auditor = None
    if args.vision_audit:
        try:
            vision_auditor = build_default_vision_auditor(model=args.vision_model)
        except VisionAuditError as exc:
            parser.error(str(exc))

    files = list(iter_presentation_files(target_path))
    if not files:
        print("No PowerPoint files were found at the provided location.")
        return 1

    exit_code = 0
    for ppt_file in files:
        try:
            result = process_ppt_file(
                ppt_file,
                translator=translator,
                source_lang=args.source_lang,
                target_lang=args.target_lang,
                max_workers=args.max_workers,
                cleanup=not args.keep_intermediate,
                vision_auditor=vision_auditor,
                vision_dpi=args.vision_dpi,
            )
            if result is None:
                print(f"Failed to process {ppt_file}.")
                exit_code = 1
        except Exception as exc:  # pragma: no cover - CLI logging
            print(f"Error processing {ppt_file}: {exc}")
            exit_code = 1
    return exit_code


def main() -> None:
    sys.exit(run_cli())
