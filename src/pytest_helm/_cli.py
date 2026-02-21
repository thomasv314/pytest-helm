"""Command-line interface for pytest-helm."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from textwrap import dedent

SCAFFOLD_DIRECTORY = "test"

CONFTEST_TEMPLATE = dedent(
    """\
    from pytest_helm import manifest_fixture

    # Update this command for your chart path and values files.
    chart_manifest = manifest_fixture(
        "chart_manifest",
        ["helm", "template", "."],
    )
    """
)

DEPLOYMENTS_TEMPLATE = dedent(
    """\
    def test_deployment_uses_apps_v1(chart_manifest):
        deployment = chart_manifest.get("apps/v1/deployment/example")
        assert deployment.apiVersion == "apps/v1"
    """
)


def scaffold_tests(*, root: Path, force: bool = False) -> list[Path]:
    """Create sample pytest-helm test files."""
    test_dir = root / SCAFFOLD_DIRECTORY
    files = {
        test_dir / "conftest.py": CONFTEST_TEMPLATE,
        test_dir / "test_deployments.py": DEPLOYMENTS_TEMPLATE,
    }

    existing = [path for path in files if path.exists()]
    if existing and not force:
        existing_paths = ", ".join(
            str(path.relative_to(root)) for path in sorted(existing)
        )
        raise FileExistsError(
            "Refusing to overwrite existing files: "
            f"{existing_paths}. Re-run with --force to overwrite."
        )

    test_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
        created.append(path)

    return created


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytest-helm",
        description="Helpers for bootstrapping pytest-helm tests.",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Scaffold sample test files under test/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite scaffold files if they already exist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the pytest-helm CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.init:
        parser.print_help()
        return 2

    try:
        created = scaffold_tests(root=Path.cwd(), force=args.force)
    except FileExistsError as exc:
        print(exc)
        return 1

    print("Scaffolded files:")
    for path in created:
        print(f"- {path.relative_to(Path.cwd())}")

    return 0
