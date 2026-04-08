from __future__ import annotations

import asyncio
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from astrbot.api import logger

from .config_store import PluginDataStore

API_URL = "https://whatslink.info/api/v1/link"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://whatslink.info/",
    "Cache-Control": "no-cache",
}
HASH_RE = re.compile(r"^[0-9a-zA-Z]{32}$|^[0-9a-zA-Z]{40}$")
MAGNET_RE = re.compile(r"magnet:\?xt=urn:btih:([0-9a-zA-Z]{32}|[0-9a-zA-Z]{40})")


@dataclass
class TorrentAnalyzeResult:
    ok: bool
    text: str
    screenshot_urls: list[str]


class TorrentService:
    def __init__(self, data_store: PluginDataStore):
        self.data_store = data_store
        self.plugin_name = data_store.plugin_name

    async def analyze(
        self, torrent_input: str, retry_times: int, retry_interval_sec: float
    ) -> TorrentAnalyzeResult:
        valid, magnet_url, torrent_hash = self._parse_torrent_input(torrent_input)
        if not valid or magnet_url is None or torrent_hash is None:
            return TorrentAnalyzeResult(
                ok=False,
                text="这不是一个有效的磁链或种子hash。",
                screenshot_urls=[],
            )

        payload = await self.data_store.get_cached_torrent(torrent_hash)
        if payload is None:
            payload = await self._request_torrent_info(
                magnet_url=magnet_url,
                retry_times=retry_times,
                retry_interval_sec=retry_interval_sec,
            )
            if payload is None:
                return TorrentAnalyzeResult(
                    ok=False,
                    text="分析失败，请稍后再试。",
                    screenshot_urls=[],
                )
            if payload.get("error") == "" and payload.get("type", "").strip() != "UNKNOWN":
                await self.data_store.save_cached_torrent(torrent_hash, payload)

        text_message = self._format_torrent_text(torrent_hash, payload)
        screenshot_urls = self._extract_screenshot_urls(payload, limit=3)
        return TorrentAnalyzeResult(ok=True, text=text_message, screenshot_urls=screenshot_urls)

    async def _request_torrent_info(
        self, magnet_url: str, retry_times: int, retry_interval_sec: float
    ) -> Optional[dict[str, Any]]:
        retries = max(1, min(int(retry_times), 60))
        interval = max(0.5, min(float(retry_interval_sec), 30.0))
        encoded = urllib.parse.quote(magnet_url, safe="")
        url = f"{API_URL}?url={encoded}"

        async with httpx.AsyncClient(timeout=10) as client:
            for idx in range(retries):
                try:
                    response = await client.get(url, headers=REQUEST_HEADERS)
                    response.raise_for_status()
                    data = response.json()
                except Exception as exc:
                    logger.warning(f"[{self.plugin_name}] 请求失败({idx + 1}/{retries}): {exc}")
                    if idx < retries - 1:
                        await asyncio.sleep(interval)
                    continue

                if data.get("error") in ("", None):
                    return data

                if data.get("error") == "quota_limited" and idx < retries - 1:
                    await asyncio.sleep(interval)
                    continue
                return data

        return None

    def _parse_torrent_input(
        self, torrent_input: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        text = torrent_input.strip()
        if HASH_RE.fullmatch(text):
            return True, f"magnet:?xt=urn:btih:{text}", text

        magnet_match = MAGNET_RE.search(text)
        if magnet_match:
            return True, text, magnet_match.group(1)
        return False, None, None

    def _extract_screenshot_urls(
        self, payload: dict[str, Any], limit: int = 3
    ) -> list[str]:
        screenshots = payload.get("screenshots", [])
        if not isinstance(screenshots, list):
            return []

        urls: list[str] = []
        for item in screenshots[:limit]:
            if isinstance(item, dict):
                url = item.get("screenshot")
                if isinstance(url, str) and url:
                    urls.append(url)
        return urls

    def _format_torrent_text(self, torrent_hash: str, payload: dict[str, Any]) -> str:
        if payload.get("error"):
            return f"分析失败: {payload.get('error')}"

        name = str(payload.get("name", "未知"))
        type_name = str(payload.get("type", "UNKNOWN"))
        file_type = str(payload.get("file_type", "UNKNOWN"))
        count = payload.get("count", "未知")
        size_value = payload.get("size", 0)

        lines = [
            f"种子哈希: {torrent_hash}",
            f"文件类型: {type_name}-{file_type}",
            f"种子名称: {name}",
            f"总大小: {self._human_size(size_value)}",
            f"文件总数: {count}",
        ]
        return "\n".join(lines)

    def _human_size(self, value: Any) -> str:
        try:
            size = float(value)
        except Exception:
            return "未知"

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        for unit in units:
            if size < 1024:
                return f"{size:.2f}{unit}"
            size /= 1024
        return f"{size:.2f}EB"

