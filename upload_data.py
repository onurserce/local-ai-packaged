
#!/usr/bin/env python3
"""
Copy files from the Windows filesystem into the shared folder that lives inside WSL.

Examples
--------
Copy the whole default data directory:
    python upload_data.py

Copy only PDFs and Excel files into shared/reports and overwrite if needed:
    python upload_data.py --patterns "*.pdf" "reports/**/*.xlsx" --dest shared/reports --overwrite

Copy specific files (relative to the source root) without touching anything else:
    python upload_data.py --names notes/summary.txt data/raw/input.csv
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import List, Sequence

DEFAULT_WINDOWS_SOURCE = os.environ.get(
    "WINDOWS_SOURCE_PATH",
    r"C:\Users\OnurSerçe\HMNC Holding GmbH\Biomarker - Documents\_00_Biomarker Team\SCAI\Deliverables pilot Project Knowledge Graph",
)
SCRIPT_ROOT = Path(__file__).resolve().parent


class CliError(RuntimeError):
    """Raised when the user passed invalid CLI arguments."""


@dataclass(frozen=True)
class Target:
    absolute: Path
    relative: Path


@dataclass
class CopyStats:
    files: int = 0
    directories: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy selected files or folders from a Windows path into the `shared` directory inside WSL."
        )
    )
    parser.add_argument(
        "-s",
        "--source",
        default=DEFAULT_WINDOWS_SOURCE,
        help=("Windows or WSL path that acts as the source root. "
              "Defaults to the WINDOWS_SOURCE_PATH env var or the built-in path."),
    )
    parser.add_argument(
        "-d",
        "--dest",
        default="shared",
        help="Destination directory. Relative paths are resolved from the repository root (where this script lives).",
    )
    parser.add_argument(
        "-n",
        "--names",
        nargs="+",
        help="Specific files or directories relative to the source root to copy.",
    )
    parser.add_argument(
        "-p",
        "--patterns",
        nargs="+",
        help="Glob patterns relative to the source root (e.g. '*.pdf' or 'reports/**/*.xlsx').",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination files when they already exist. Defaults to stopping on conflicts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied without writing any files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every step. Implied when --dry-run is used.",
    )
    return parser.parse_args()


def looks_like_windows_path(value: str) -> bool:
    """Return True when the string looks like `C:\\something`."""
    return len(value) >= 2 and value[0].isalpha() and value[1] == ":"


def windows_to_wsl(path_str: str) -> Path:
    """Convert a Windows path (C:\\foo) to its /mnt/c/foo representation."""
    pure = PureWindowsPath(path_str)
    if not pure.drive:
        raise CliError(f"Cannot convert Windows path without a drive letter: {path_str!r}")
    drive_letter = pure.drive.rstrip(":").lower()
    converted = Path("/mnt") / drive_letter
    for part in pure.parts[1:]:
        converted /= part
    return converted


def normalize_input_path(value: str, *, default_base: Path) -> Path:
    """Normalize a CLI path argument."""
    text = value.strip().strip('"')
    if not text:
        raise CliError("Encountered an empty path.")
    if looks_like_windows_path(text):
        candidate = windows_to_wsl(text)
    else:
        candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (default_base / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def normalize_relative(value: str) -> Path:
    """Normalize relative CLI arguments by replacing backslashes."""
    return Path(value.replace("\\", "/"))


def collect_targets(
    source_root: Path,
    names: Sequence[str] | None,
    patterns: Sequence[str] | None,
) -> List[Target]:
    """Select which paths should be copied."""
    resolved_root = source_root.resolve()
    if not resolved_root.exists():
        raise CliError(f"Source path does not exist: {resolved_root}")

    targets: dict[Path, Target] = {}

    def record(path: Path) -> None:
        absolute = path.resolve()
        if not absolute.exists():
            raise CliError(f"Requested path does not exist: {absolute}")
        try:
            relative = absolute.relative_to(resolved_root)
        except ValueError as exc:
            raise CliError(
                f"Requested path {absolute} is outside of the source root {resolved_root}"
            ) from exc
        targets[absolute] = Target(absolute=absolute, relative=relative)

    if names:
        for entry in names:
            rel_path = normalize_relative(entry)
            if rel_path.is_absolute():
                raise CliError(f"--names entries must be relative to the source root: {entry}")
            record(resolved_root / rel_path)

    if patterns:
        for pattern in patterns:
            normalized_pattern = pattern.replace("\\", "/")
            matches = list(resolved_root.glob(normalized_pattern))
            if not matches:
                print(f"[warn] pattern '{pattern}' matched nothing", file=sys.stderr)
                continue
            for match in matches:
                record(match)

    if targets:
        return list(targets.values())

    if resolved_root.is_dir():
        return [Target(absolute=resolved_root, relative=Path("."))]
    return [Target(absolute=resolved_root, relative=Path(resolved_root.name))]


def ensure_destination(dest_root: Path, *, dry_run: bool) -> None:
    """Create the destination root unless we are in dry run mode."""
    if dry_run:
        return
    dest_root.mkdir(parents=True, exist_ok=True)


def copy_file(
    source: Path,
    dest: Path,
    *,
    overwrite: bool,
    dry_run: bool,
    verbose: bool,
    stats: CopyStats,
) -> None:
    """Copy a single file."""
    if dest.exists() and dest.is_dir():
        raise CliError(f"Cannot overwrite directory with file: {dest}")
    if dest.exists() and not overwrite:
        raise CliError(f"{dest} already exists. Use --overwrite to replace it.")

    if verbose or dry_run:
        prefix = "[dry-run]" if dry_run else "[copy]"
        print(f"{prefix} FILE {source} -> {dest}")

    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    stats.files += 1


def copy_directory(
    source: Path,
    dest: Path,
    *,
    overwrite: bool,
    dry_run: bool,
    verbose: bool,
    stats: CopyStats,
) -> None:
    """Recursively copy a directory tree."""
    for root, _, files in os.walk(source):
        root_path = Path(root)
        try:
            relative_root = root_path.relative_to(source)
        except ValueError:
            relative_root = Path(".")
        current_dest = dest if relative_root == Path(".") else dest / relative_root
        if verbose or dry_run:
            prefix = "[dry-run]" if dry_run else "[copy]"
            print(f"{prefix} DIR  {root_path} -> {current_dest}")
        if not dry_run:
            current_dest.mkdir(parents=True, exist_ok=True)
        stats.directories += 1
        for filename in files:
            src_file = root_path / filename
            dest_file = current_dest / filename
            copy_file(
                src_file,
                dest_file,
                overwrite=overwrite,
                dry_run=dry_run,
                verbose=verbose,
                stats=stats,
            )


def destination_for(target: Target, dest_root: Path) -> Path:
    """Compute the destination path for the given target."""
    if target.relative == Path("."):
        if target.absolute.is_dir():
            return dest_root
        return dest_root / target.absolute.name
    return dest_root / target.relative


def run() -> None:
    args = parse_args()
    verbose = args.verbose or args.dry_run

    source_root = normalize_input_path(args.source, default_base=Path.cwd())
    dest_root = normalize_input_path(args.dest, default_base=SCRIPT_ROOT)

    if not source_root.exists():
        raise CliError(f"Source path does not exist: {source_root}")

    ensure_destination(dest_root, dry_run=args.dry_run)

    targets = collect_targets(source_root, args.names, args.patterns)
    stats = CopyStats()

    print(f"Source:      {source_root}")
    print(f"Destination: {dest_root}")
    if args.dry_run:
        print("Running in dry-run mode; nothing will be modified.")

    for target in targets:
        final_dest = destination_for(target, dest_root)
        if target.absolute.is_dir():
            copy_directory(
                target.absolute,
                final_dest,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                verbose=verbose,
                stats=stats,
            )
        else:
            copy_file(
                target.absolute,
                final_dest,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                verbose=verbose,
                stats=stats,
            )

    info = f"Prepared {stats.files} file(s)."
    if stats.directories:
        plural = "y" if stats.directories == 1 else "ies"
        info += f" Traversed {stats.directories} director{plural}."
    if args.dry_run:
        info += " This was a dry run."
    print(info)


def main() -> None:
    try:
        run()
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
