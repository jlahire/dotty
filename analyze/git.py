"""
dotty v2 — git analysis
by jLaHire

finds deleted files, pulls commit history, builds timeline data.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from graph import Node, make_id

log = logging.getLogger(__name__)


def is_git_repo(path: str) -> bool:
    return (Path(path) / ".git").is_dir()


def analyze_git(repo_path: str) -> list[Node]:
    if not is_git_repo(repo_path):
        return []

    deleted = find_deleted_files(repo_path)
    nodes = []

    for file_path, info in deleted.items():
        full_path = str(Path(repo_path) / file_path)
        nodes.append(Node(
            id=make_id(f"deleted:{full_path}"),
            name=Path(file_path).name,
            path=full_path,
            kind="deleted",
            info={
                "extension": Path(file_path).suffix.lower(),
                "modified": info.get("date", ""),
                "deleted_by": info.get("author", ""),
                "delete_commit": info.get("commit", ""),
                "commit_message": info.get("message", ""),
                "relative": file_path,
            },
            is_deleted=True,
        ))

    return nodes


def find_deleted_files(repo_path: str) -> dict[str, dict]:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--diff-filter=D",
             "--summary", "--pretty=format:%H|%aI|%an|%s"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        log.error(f"git: {e}")
        return {}

    deleted = {}
    current_commit = {}

    for line in result.stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "|" in line and not line.startswith("delete"):
            parts = line.split("|", 3)
            if len(parts) >= 4:
                current_commit = {
                    "commit": parts[0], "date": parts[1],
                    "author": parts[2], "message": parts[3],
                }
        elif line.startswith("delete mode"):
            parts = line.split()
            if len(parts) >= 4:
                fp = " ".join(parts[3:])
                if fp not in deleted:
                    deleted[fp] = {**current_commit}

    return deleted


def get_file_history(repo_path: str) -> dict[str, list[dict]]:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "ls-files"],
            capture_output=True, text=True, timeout=10,
        )
        files = [f for f in result.stdout.strip().split("\n") if f][:100]
    except Exception:
        return {}

    history = {}
    for fp in files:
        commits = _file_log(repo_path, fp)
        if commits:
            history[fp] = commits
    return history


def _file_log(repo_path: str, file_path: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--follow",
             "--pretty=format:%H|%aI|%an|%s", "--", file_path],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line or "|" not in line:
            continue
        parts = line.split("|", 3)
        if len(parts) >= 4:
            commits.append({
                "commit": parts[0], "date": parts[1],
                "author": parts[2], "message": parts[3],
            })
    return commits


def get_timeline(repo_path: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log",
             "--pretty=format:%aI|%an|%s", "--all"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return []

    timeline = []
    for line in result.stdout.strip().split("\n"):
        if not line or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) >= 3:
            timeline.append({"date": parts[0], "author": parts[1], "message": parts[2]})
    return timeline
