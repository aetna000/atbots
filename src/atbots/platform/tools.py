"""Approved workspace file tools, not arbitrary command execution."""

from pathlib import Path

from atbots.platform.memory import screen_message


class WorkspaceTools:
    def __init__(self, root: Path, *, read=False, create=False):
        self.root, self.read_allowed, self.create_allowed = root.resolve(), read, create

    def path(self, relative: str):
        path = self.root / relative
        if (
            not relative
            or Path(relative).is_absolute()
            or not path.resolve().is_relative_to(self.root)
        ):
            raise PermissionError(
                "File path is outside this agent's approved workspace"
            )
        return path

    def read_file(self, path: str) -> str:
        """Read a UTF-8 file under the approved workspace, maximum 100 KB."""
        if not self.read_allowed:
            raise PermissionError("Workspace read permission is not granted")
        target = self.path(path)
        if not target.is_file() or target.stat().st_size > 100000:
            raise ValueError("Expected a regular workspace file no larger than 100 KB")
        text = target.read_text(encoding="utf-8")
        screen_message(text)
        return text

    def create_file(self, path: str, content: str) -> dict:
        """Create a new UTF-8 workspace artifact. Never overwrite an existing file."""
        if not self.create_allowed:
            raise PermissionError("Workspace create permission is not granted")
        if len(content.encode()) > 100000:
            raise ValueError("Artifact exceeds 100 KB")
        screen_message(content)
        target = self.path(path)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Revalidate after creating directories; callers cannot choose another root.
        self.path(path)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(content)
        return {"path": path, "bytes": target.stat().st_size}

    def tools(self):
        return ([self.read_file] if self.read_allowed else []) + (
            [self.create_file] if self.create_allowed else []
        )
