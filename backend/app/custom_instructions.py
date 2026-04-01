import json
from pathlib import Path


INSTRUCTION_KEYS = [
    "global",
    "GENERAL",
    "BQ",
    "STORY",
    "RESUME",
    "DEBRIEF",
    "STRATEGY",
    "SCOUT",
    "INTAKE",
]


DEFAULT_CUSTOM_INSTRUCTIONS = {key: "" for key in INSTRUCTION_KEYS}


class CustomInstructionManager:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(DEFAULT_CUSTOM_INSTRUCTIONS, indent=2) + "\n",
                encoding="utf-8",
            )

    def load(self) -> dict[str, str]:
        self._ensure_file()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

        data = DEFAULT_CUSTOM_INSTRUCTIONS.copy()
        if isinstance(raw, dict):
            for key in INSTRUCTION_KEYS:
                value = raw.get(key, "")
                data[key] = value.strip() if isinstance(value, str) else ""
        return data

    def save(self, updates: dict[str, str]) -> dict[str, str]:
        current = self.load()
        for key in INSTRUCTION_KEYS:
            value = updates.get(key, current[key])
            current[key] = value.strip() if isinstance(value, str) else ""
        self.path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        return current
