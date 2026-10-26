"""Reviewed local skill bundles with pinned content hashes; no code auto-execution."""

import hashlib
import json
import shutil
from pathlib import Path

from atbots.platform.memory import screen_message
from atbots.platform.models import agent_name


class Skills:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def review(self, source: str):
        root = Path(source).resolve(strict=True)
        if not root.is_dir() or not (root / "SKILL.md").is_file():
            raise ValueError("Skill source needs a directory containing SKILL.md")
        files = sorted(root.rglob("*"))
        if len(files) > 100:
            raise ValueError("Skill exceeds review limit of 100 entries")
        digest = hashlib.sha256()
        executable = []
        for path in files:
            if path.is_symlink():
                raise ValueError("Skill bundles may not contain symlinks")
            if path.is_file():
                if path.stat().st_size > 100000:
                    raise ValueError("Skill file exceeds 100 KB review limit")
                digest.update(
                    str(path.relative_to(root)).encode() + b"\0" + path.read_bytes()
                )
                if path.suffix in {".py", ".sh", ".js", ".ts", ".exe", ".bat", ".ps1"}:
                    executable.append(str(path.relative_to(root)))
        text = (root / "SKILL.md").read_text()
        screen_message(text)
        return {
            "source": str(root),
            "sha256": digest.hexdigest(),
            "code_files": executable,
            "instructions": text,
        }

    def install(self, name, source, expected_digest, *, allow_code=False):
        agent_name(name)
        review = self.review(source)
        if review["sha256"] != expected_digest:
            raise ValueError("Skill changed after review; re-review before approval")
        if review["code_files"] and not allow_code:
            raise PermissionError(
                "Executable resources require a separate explicit code grant"
            )
        target = self.root / name
        if target.exists():
            raise ValueError("Skill already exists; no automatic overwrite")
        shutil.copytree(review["source"], target)
        copied = self.review(str(target))
        if copied["sha256"] != expected_digest:
            raise ValueError(
                "Copied skill differs from reviewed source; do not grant it"
            )
        (self.root / (name + ".approval.json")).write_text(
            json.dumps(
                {
                    "sha256": expected_digest,
                    "source": review["source"],
                    "allow_code": allow_code,
                }
            )
        )
        return {"name": name, "sha256": review["sha256"], "code_auto_executed": False}

    def list_skills(self):
        return [
            {"name": p.name}
            for p in sorted(self.root.iterdir())
            if p.is_dir() and not p.is_symlink() and (p / "SKILL.md").is_file()
        ]

    def load_skill(self, name: str) -> str:
        """Load approved skill instructions on demand; resources are not executed."""
        agent_name(name)
        approval = json.loads((self.root / (name + ".approval.json")).read_text())
        if self.review(str(self.root / name))["sha256"] != approval["sha256"]:
            raise PermissionError(
                "Installed skill changed since approval; review it again"
            )
        path = self.root / name / "SKILL.md"
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise PermissionError("Skill path escapes approved bundle root")
        text = path.read_text()
        screen_message(text)
        return text
