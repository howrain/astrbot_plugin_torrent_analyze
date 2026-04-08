from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class PluginDataStore:
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        data_root = Path(get_astrbot_data_path())
        self.base_dir = data_root / "plugin_data" / plugin_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = self.base_dir / "torrent_info_cache.json"
        self.render_dir = self.base_dir / "rendered"
        self.render_dir.mkdir(parents=True, exist_ok=True)

        self._io_lock = asyncio.Lock()
        self._ensure_json_file(self.cache_file)

    @staticmethod
    def clamp_blur(value: Any) -> int:
        try:
            ivalue = int(value)
        except Exception:
            ivalue = 10
        return max(0, min(ivalue, 10))

    async def get_cached_torrent(self, torrent_hash: str) -> Optional[dict[str, Any]]:
        cache = await self._read_json(self.cache_file)
        value = cache.get(torrent_hash)
        return value if isinstance(value, dict) else None

    async def save_cached_torrent(self, torrent_hash: str, payload: dict[str, Any]) -> None:
        cache = await self._read_json(self.cache_file)
        cache[torrent_hash] = payload
        await self._write_json(self.cache_file, cache)

    def _ensure_json_file(self, file_path: Path) -> None:
        if file_path.exists():
            return
        with file_path.open("w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False)

    async def _read_json(self, file_path: Path) -> dict[str, Any]:
        async with self._io_lock:
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                logger.warning(f"[{self.plugin_name}] 读取 {file_path.name} 失败，已回退为空字典")
            return {}

    async def _write_json(self, file_path: Path, data: dict[str, Any]) -> None:
        async with self._io_lock:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
