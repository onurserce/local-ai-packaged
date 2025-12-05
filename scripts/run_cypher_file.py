#!/usr/bin/env python3
"""
Execute Cypher statements from a file against Neo4j, buffering multi-line statements.

- Reads credentials from .env via python-dotenv:
    * Prefer NEO4J_AUTH in the form "user/password"
    * Or NEO4J_USER and NEO4J_PASSWORD
- Treats ';' as the statement terminator; supports multiple statements per line.
- Skips blank lines and lines starting with '//' or '#'.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, basic_auth


def parse_auth() -> tuple[str, str]:
    """Load Neo4j credentials from .env."""
    load_dotenv()
    auth_env = os.getenv("NEO4J_AUTH", "")

    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")

    if "/" in auth_env:
        user, password = auth_env.split("/", 1)

    user = user or "neo4j"
    if not password:
        raise RuntimeError(
            "Neo4j password is missing. Set NEO4J_AUTH or NEO4J_PASSWORD in .env."
        )
    return user, password


def run_cypher_file(
    path: str | Path,
    *,
    uri: str = "bolt://localhost:7687",
    progress_interval: int = 10,
) -> None:
    """
    Execute Cypher statements from a file.
    Buffers across multiple lines until a semicolon, supports multiple statements per line.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Cypher file not found: {file_path}")

    user, password = parse_auth()
    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    try:
        with driver.session() as session, file_path.open("r", encoding="utf-8") as fh:
            buffer: list[str] = []
            line_no = 0
            for raw in fh:
                line_no += 1
                line = raw.strip()
                if not line or line.startswith("//") or line.startswith("#"):
                    if progress_interval > 0 and line_no % progress_interval == 0:
                        print(f"[info] processed {line_no} lines")
                    continue

                parts = line.split(";")
                for idx, part in enumerate(parts):
                    if part.strip():
                        buffer.append(part.strip())
                    if idx < len(parts) - 1:
                        stmt = " ".join(buffer).strip()
                        if stmt:
                            session.run(stmt)
                        buffer.clear()
                if progress_interval > 0 and line_no % progress_interval == 0:
                    print(f"[info] processed {line_no} lines")

            tail = " ".join(buffer).strip()
            if tail:
                session.run(tail)
    finally:
        driver.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute Cypher statements from a file (multi-line aware)."
    )
    parser.add_argument(
        "file",
        help="Path to the Cypher file.",
    )
    parser.add_argument(
        "--uri",
        default="bolt://localhost:7687",
        help="Neo4j Bolt URI (default: %(default)s).",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10,
        help="Print a progress message every N lines read (0 to disable).",
    )
    args = parser.parse_args(argv)

    try:
        run_cypher_file(args.file, uri=args.uri, progress_interval=args.progress_interval)
    except Exception as exc:  # pragma: no cover - simple CLI reporting
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
