from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.star import Context, Star, register

from .services.config_store import PluginDataStore
from .services.image_renderer import TorrentImageRenderer
from .services.torrent_service import TorrentService

PLUGIN_NAME = "astrbot_plugin_torrent_analyze"
DEFAULT_HELP_MSG = (
    "[验车 磁链] 查询磁链信息\n"
    "支持别名: 种子分析 / 种子信息 / 种子详情\n"
    "配置项请在 AstrBot 插件管理页面修改:\n"
    "- default_blur_radius (默认10)\n"
    "- default_image_enabled (默认开)"
)


@register(PLUGIN_NAME, "howrain", "磁链验车/种子分析（支持截图与高斯）", "1.0.0")
class TorrentAnalyzePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        plugin_name = getattr(self, "name", PLUGIN_NAME)
        self.data_store = PluginDataStore(plugin_name=plugin_name)
        self.torrent_service = TorrentService(self.data_store)
        self.image_renderer = TorrentImageRenderer(output_dir=self.data_store.render_dir)

    @filter.command("验车", alias={"种子分析", "种子信息", "种子详情"})
    async def check_torrent(self, event: AstrMessageEvent, torrent_input: str = ""):
        """验车: 查询磁链或种子 hash 信息。"""
        torrent_input = (torrent_input or "").strip()
        if not torrent_input:
            yield event.plain_result("请输入种子链接或hash。")
            return

        yield await self._handle_query_cmd(torrent_input, event)

    @filter.command("验车帮助")
    async def torrent_help(self, event: AstrMessageEvent):
        """查看验车插件帮助。"""
        yield event.plain_result(DEFAULT_HELP_MSG)

    @filter.command("验车配置")
    async def torrent_config(self, event: AstrMessageEvent):
        """查看当前生效的验车配置。"""
        blur_radius = self._default_blur_radius()
        image_enabled = self._default_image_enabled()
        retry_times = self._max_retry_times()
        retry_interval_sec = self._retry_interval_sec()
        msg = (
            "当前验车配置:\n"
            f"- 默认高斯: {blur_radius}\n"
            f"- 默认图片返回: {'开' if image_enabled else '关'}\n"
            f"- 请求重试次数: {retry_times}\n"
            f"- 请求重试间隔(秒): {retry_interval_sec}\n"
            "配置修改方式: AstrBot 插件管理 -> 本插件配置"
        )
        yield event.plain_result(msg)

    async def _handle_query_cmd(
        self, torrent_input: str, event: AstrMessageEvent
    ) -> MessageEventResult:
        image_enabled = self._default_image_enabled()
        blur_radius = self._default_blur_radius()

        analysis = await self.torrent_service.analyze(
            torrent_input=torrent_input,
            retry_times=self._max_retry_times(),
            retry_interval_sec=self._retry_interval_sec(),
        )
        if not analysis.ok:
            return event.plain_result(analysis.text)

        if not image_enabled or not analysis.screenshot_urls:
            return event.plain_result(analysis.text)

        try:
            output_path = await self.image_renderer.render_torrent_image(
                text_message=analysis.text,
                image_urls=analysis.screenshot_urls,
                blur_radius=blur_radius,
            )
            if output_path is None:
                return event.plain_result(analysis.text)
            return event.image_result(str(output_path))
        except Exception as exc:
            logger.warning(f"[{PLUGIN_NAME}] 渲染图片失败，回退文本: {exc}")
            return event.plain_result(analysis.text)

    def _default_blur_radius(self) -> int:
        return self.data_store.clamp_blur(self.config.get("default_blur_radius", 10))

    def _default_image_enabled(self) -> bool:
        return bool(self.config.get("default_image_enabled", True))

    def _max_retry_times(self) -> int:
        value = self.config.get("request_retry_times", 20)
        try:
            times = int(value)
        except Exception:
            return 20
        return max(1, min(times, 60))

    def _retry_interval_sec(self) -> float:
        value = self.config.get("request_retry_interval_sec", 3.0)
        try:
            interval = float(value)
        except Exception:
            return 3.0
        return max(0.5, min(interval, 30.0))
