import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

import git


MEMORY_FILES = [
    "L0_identity.md",
    "L1_campaign.md",
    "L2_knowledge.md",
    "stories_bank.md",
    "resume_versions.md",
    "interview_log.md",
]

STUBS = {
    "L0_identity.md": "# L0 · Core Identity\n> Fill this out or run onboarding.\n\n## Who I am\n\n## Career narrative\n\n## Target role\n\n## Technical skills\n\n## Signature projects\n",
    "L1_campaign.md": "# L1 · Campaign State\n> Updated every session.\n\n## Status snapshot\n\n| Metric | Value |\n|---|---|\n| Active applications | 0 |\n\n## Weekly focus\n\n## Mindset check\n\n## Strategy notes\n",
    "L2_knowledge.md": "# L2 · Knowledge Base\n> Grows as you learn.\n\n## Job search strategy\n\n## Sourcing channels\n\n## Market intelligence\n\n## Interview prep learnings\n\n## Insights from content\n\n## Strategy iteration log\n",
    "stories_bank.md": "# Stories Bank\n\n## Quick-reference index\n\n| Theme | Stories |\n|---|---|\n\n## Coverage gaps\n\n- None yet.\n\n",
    "resume_versions.md": "# Resume Versions\n\n## Current version: v1.0\n\n**Created:** [DATE]\n**Status:** Active\n\n### Bullets\n\n",
    "interview_log.md": "# Interview Log\n\n## Active interviews\n\n## Cross-company patterns\n\n### Questions that keep coming up\n\n### My blind spots\n",
}


@dataclass
class AgentContext:
    identity: str = ""
    campaign: str = ""
    knowledge_section: str = ""
    stories: str = ""
    resume: str = ""
    interview_log: str = ""
    extra: dict = field(default_factory=dict)


class MemoryManager:
    def __init__(self, memory_dir: Path, git_auto_commit: bool = True):
        self.memory_dir = Path(memory_dir)
        self.git_auto_commit = git_auto_commit
        self._ensure_repo()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _ensure_repo(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        git_dir = self.memory_dir / ".git"
        if not git_dir.exists():
            repo = git.Repo.init(self.memory_dir)
            repo.config_writer().set_value("user", "name", "Futuro").release()
            repo.config_writer().set_value("user", "email", "futuro@local").release()
        for filename, stub in STUBS.items():
            path = self.memory_dir / filename
            if not path.exists():
                path.write_text(stub, encoding="utf-8")
        self._initial_commit()

    def _initial_commit(self) -> None:
        try:
            repo = git.Repo(self.memory_dir)
            if repo.is_dirty(untracked_files=True):
                repo.git.add(A=True)
                repo.index.commit("[futuro] init memory files")
        except Exception:
            pass

    # ── Reading ───────────────────────────────────────────────────────────────

    def read(self, filename: str) -> str:
        path = self.memory_dir / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def read_section(self, filename: str, section_header: str) -> str:
        """Extract a single ## section from a markdown file."""
        content = self.read(filename)
        pattern = rf"(^## {re.escape(section_header)}.*?)(?=^## |\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def last_modified(self, filename: str) -> datetime | None:
        path = self.memory_dir / filename
        if not path.exists():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime)

    def last_commit_message(self, filename: str) -> str | None:
        try:
            repo = git.Repo(self.memory_dir)
            commits = list(repo.iter_commits(paths=filename, max_count=1))
            return commits[0].message.strip() if commits else None
        except Exception:
            return None

    def git_log(self, max_entries: int = 20) -> list[dict]:
        try:
            repo = git.Repo(self.memory_dir)
            result = []
            for commit in repo.iter_commits(max_count=max_entries):
                result.append({
                    "hash": commit.hexsha[:7],
                    "message": commit.message.strip(),
                    "timestamp": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "files_changed": list(commit.stats.files.keys()),
                })
            return result
        except Exception:
            return []

    # ── Context loading ───────────────────────────────────────────────────────

    def load_context(self, agent_type: str) -> AgentContext:
        ctx = AgentContext(
            identity=self.read("L0_identity.md"),
            campaign=self.read("L1_campaign.md"),
        )
        if agent_type in ("BQ", "STORY", "DEBRIEF"):
            ctx.stories = self.read("stories_bank.md")
        if agent_type == "RESUME":
            ctx.resume = self.read("resume_versions.md")
        if agent_type in ("STRATEGY", "INTAKE"):
            ctx.knowledge_section = self.read_section("L2_knowledge.md", "Job search strategy")
        if agent_type == "DEBRIEF":
            ctx.interview_log = self.read("interview_log.md")
        return ctx

    # ── Writing ───────────────────────────────────────────────────────────────

    def write_full(self, filename: str, content: str, commit_msg: str) -> None:
        path = self.memory_dir / filename
        path.write_text(content, encoding="utf-8")
        if self.git_auto_commit:
            self._commit(filename, commit_msg)

    def apply_update(
        self,
        filename: str,
        section: str,
        action: str,
        content: str,
        reason: str,
    ) -> None:
        path = self.memory_dir / filename
        current = path.read_text(encoding="utf-8") if path.exists() else ""

        if action == "create":
            updated = current.rstrip() + "\n\n---\n\n" + content + "\n"
        elif action == "replace":
            updated = self._replace_section(current, section, content)
        else:  # append
            updated = self._append_to_section(current, section, content)

        path.write_text(updated, encoding="utf-8")
        if self.git_auto_commit:
            short_reason = reason[:60]
            self._commit(filename, f"[futuro] {short_reason}")

    def _append_to_section(self, content: str, header: str, new_text: str) -> str:
        """Append new_text to a named markdown section, or to the file end."""
        if not header.strip():
            return self._append_to_file(content, new_text)

        pattern = self._section_pattern(header)
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if not match:
            return content.rstrip() + f"\n\n## {header}\n\n{new_text}\n"
        section_text = match.group(1).rstrip()
        replacement = section_text + "\n" + new_text.strip()
        return content[: match.start()] + replacement + "\n" + content[match.end():]

    def _replace_section(self, content: str, header: str, new_text: str) -> str:
        if not header.strip():
            return new_text.strip() + "\n"

        pattern = self._section_pattern(header)
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            heading_line = match.group(1).splitlines()[0]
            replacement = f"{heading_line}\n\n{new_text.strip()}\n"
            return content[: match.start()] + replacement + content[match.end():]
        return content.rstrip() + f"\n\n## {header}\n\n{new_text}\n"

    def _append_to_file(self, content: str, new_text: str) -> str:
        new_text = new_text.strip()
        if not content.strip():
            return new_text + "\n"
        return content.rstrip() + "\n\n" + new_text + "\n"

    def _section_pattern(self, header: str) -> str:
        return rf"(^#{{2,6}}\s+{re.escape(header)}\s*$.*?)(?=^#{{2,6}}\s+|\Z)"

    def _commit(self, filename: str, message: str) -> None:
        try:
            repo = git.Repo(self.memory_dir)
            repo.index.add([filename])
            if repo.is_dirty(index=True):
                repo.index.commit(message)
        except Exception as exc:
            print(f"[memory] git commit failed: {exc}")
