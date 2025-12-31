#!/usr/bin/env python
"""Create a snapshot (wheel file) of the current py-draughts version."""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_git_info() -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True,
        ).stdout.strip())
        return {"commit": commit, "branch": branch, "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}


def main():
    project_root = Path(__file__).parent.parent
    snapshots_dir = project_root / "snapshots"
    snapshots_dir.mkdir(exist_ok=True)

    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    print("Building wheel...")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        cwd=project_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Build failed:\n{result.stderr}")
        sys.exit(1)

    wheel_path = list(dist_dir.glob("*.whl"))[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = snapshots_dir / f"snapshot_{timestamp}"
    snapshot_dir.mkdir()

    shutil.copy(wheel_path, snapshot_dir / wheel_path.name)

    git_info = get_git_info()
    (snapshot_dir / "metadata.json").write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "wheel": wheel_path.name,
        "git": git_info,
    }, indent=2))

    dirty = " (dirty)" if git_info.get("dirty") else ""
    git_str = f" [{git_info.get('branch')}@{git_info.get('commit')}{dirty}]" if git_info else ""
    print(f"\n✓ Snapshot: {snapshot_dir.name}{git_str}")


if __name__ == "__main__":
    main()
