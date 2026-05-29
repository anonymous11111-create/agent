import json
import logging
from pathlib import Path

from app.teams.bus import MessageBus
from app.teams.store import RequestStore

logger = logging.getLogger(__name__)

TEAM_DIR = Path.cwd() / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
REQUESTS_DIR = TEAM_DIR / "requests"


class TeammateManager:
    """Persistent teammate registry."""

    def __init__(self, team_dir: Path = None):
        self.dir = team_dir or TEAM_DIR
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"team_name": "default", "members": []}

    def _save_config(self):
        self.config_path.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _find_member(self, name: str) -> dict | None:
        for m in self.config["members"]:
            if m["name"] == name:
                return m
        return None

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find_member(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save_config()
        return f"Spawned '{name}' (role: {role})"

    def update_status(self, name: str, status: str) -> str:
        member = self._find_member(name)
        if not member:
            return f"Error: '{name}' not found"
        member["status"] = status
        self._save_config()
        return f"Updated '{name}' status to {status}"

    def list_all(self) -> str:
        if not self.config["members"]:
            return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        return [m["name"] for m in self.config["members"]]


# Global instances
BUS = MessageBus(INBOX_DIR)
REQUEST_STORE = RequestStore(REQUESTS_DIR)
TEAM = TeammateManager(TEAM_DIR)
