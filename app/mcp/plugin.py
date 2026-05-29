import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Load plugins from .claude-plugin/ directories.

    Teaching version implements the smallest useful plugin flow:
    read a manifest, discover MCP server configs, and register them.
    """

    def __init__(self, search_dirs: list = None):
        self.search_dirs = search_dirs or [Path.cwd()]
        self.plugins = {}  # name -> manifest

    def scan(self) -> list:
        """Scan directories for .claude-plugin/plugin.json manifests."""
        found = []
        for search_dir in self.search_dirs:
            plugin_dir = Path(search_dir) / ".claude-plugin"
            manifest_path = plugin_dir / "plugin.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    name = manifest.get("name", plugin_dir.parent.name)
                    self.plugins[name] = manifest
                    found.append(name)
                except (json.JSONDecodeError, OSError) as e:
                    logger.error("Plugin load failed %s: %s", manifest_path, e)
        return found

    def get_mcp_servers(self) -> dict:
        """
        Extract MCP server configs from loaded plugins.
        Returns {server_name: {command, args, env}}.
        """
        servers = {}
        for plugin_name, manifest in self.plugins.items():
            for server_name, config in manifest.get("mcpServers", {}).items():
                # Avoid redundant double-naming when plugin and server names match
                key = f"{plugin_name}__{server_name}" if plugin_name != server_name else server_name
                servers[key] = config
        return servers
