import logging
import os
import re
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class SkillDocument:
    def __init__(self, name: str, description: str, body: str):
        self.name = name
        self.description = description
        self.body = body


class SkillRegistry:
    """Scans skills directory for SKILL.md files, parses frontmatter."""

    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)

    def __init__(self):
        self._documents: dict[str, SkillDocument] = {}

    def init(self):
        skills_dir = Path(settings.SKILLS_DIR)
        if not skills_dir.is_dir():
            logger.info("Skills dir not found: %s", skills_dir)
            return

        for sub_dir in skills_dir.iterdir():
            if not sub_dir.is_dir():
                continue
            skill_file = sub_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8")
                doc = self._parse_frontmatter(content, sub_dir.name)
                self._documents[doc.name] = doc
                logger.debug("Loaded skill: %s", doc.name)
            except Exception as e:
                logger.warning("Failed to parse skill: %s", skill_file, e)

        logger.info("Skills loaded: %d", len(self._documents))

    def _parse_frontmatter(self, content: str, default_name: str) -> SkillDocument:
        m = self.FRONTMATTER_PATTERN.match(content)
        if not m:
            return SkillDocument(default_name, "No description", content.strip())

        frontmatter = m.group(1)
        body = m.group(2).strip()

        name = default_name
        description = "No description"

        for line in frontmatter.split("\n"):
            colon_idx = line.find(":")
            if colon_idx < 0:
                continue
            key = line[:colon_idx].strip()
            value = line[colon_idx + 1:].strip()
            if key == "name":
                name = value
            elif key == "description":
                description = value

        return SkillDocument(name, description, body)

    def describe_available(self) -> str:
        if not self._documents:
            return "(无可用技能)"
        lines = [f"- {doc.name}: {doc.description}" for doc in self._documents.values()]
        return "\n".join(lines)

    def load_full_text(self, name: str) -> str:
        doc = self._documents.get(name)
        if doc is None:
            known = ", ".join(self._documents.keys()) or "(无)"
            return f"错误：未知技能 '{name}'。可用技能: {known}"
        return f'<skill name="{doc.name}">\n{doc.body}\n</skill>'


skill_registry = SkillRegistry()
