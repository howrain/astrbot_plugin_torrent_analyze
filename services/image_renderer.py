from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from astrbot.api import logger

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://whatslink.info/",
    "Cache-Control": "no-cache",
}


class TorrentImageRenderer:
    def __init__(
        self,
        output_dir: Path,
        font_dir: str = "/AstrBot/data/fonts",
        preferred_font_filename: str = "",
        maple_mono_font_order: Optional[list[str]] = None,
    ):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.font_dir = Path(font_dir)
        self.preferred_font_filename = (preferred_font_filename or "").strip()
        self.maple_mono_font_order = (
            maple_mono_font_order[:] if maple_mono_font_order else self._default_maple_order()
        )

    async def render_torrent_image(
        self, text_message: str, image_urls: list[str], blur_radius: int
    ) -> Optional[Path]:
        text_image = self._create_text_image(text_message)
        images = await self._fetch_images(image_urls, blur_radius)
        if not images:
            return None

        final_image = self._concatenate_images(text_image, images)
        filename = f"torrent_{abs(hash((text_message, tuple(image_urls))))}.jpg"
        output_path = self.output_dir / filename
        final_image.save(output_path, format="JPEG", quality=90)
        return output_path

    async def _fetch_images(self, image_urls: list[str], blur_radius: int) -> list[Image.Image]:
        async with httpx.AsyncClient(timeout=15) as client:
            tasks = [
                self._fetch_image_with_blur(client, url, blur_radius=blur_radius)
                for url in image_urls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        images: list[Image.Image] = []
        for result in results:
            if isinstance(result, Image.Image):
                images.append(result)
        return images

    async def _fetch_image_with_blur(
        self, client: httpx.AsyncClient, url: str, blur_radius: int
    ) -> Optional[Image.Image]:
        try:
            response = await client.get(url, headers=REQUEST_HEADERS)
            response.raise_for_status()
        except Exception as exc:
            logger.warning(f"[torrent_analyze] 获取截图失败: {url} {exc}")
            return None

        content_type = response.headers.get("Content-Type", "")
        if "image" not in content_type:
            return None

        try:
            image = Image.open(BytesIO(response.content)).convert("RGB")
            if blur_radius > 0:
                return image.filter(ImageFilter.GaussianBlur(blur_radius))
            return image
        except Exception as exc:
            logger.warning(f"[torrent_analyze] 处理截图失败: {url} {exc}")
            return None

    def _create_text_image(
        self, text: str, font_size: int = 24, line_spacing: int = 10, margin: int = 20
    ) -> Image.Image:
        font = self._pick_font(font_size)
        lines = text.split("\n")

        temp_image = Image.new("RGB", (1, 1), color=(255, 255, 255))
        draw = ImageDraw.Draw(temp_image)

        max_width = 0
        total_height = margin * 2
        for line in lines:
            left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
            width = right - left
            height = bottom - top
            max_width = max(max_width, width)
            total_height += height + line_spacing

        image = Image.new("RGB", (max_width + margin * 2, total_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        y = margin
        for line in lines:
            left, top, right, bottom = draw.textbbox((margin, y), line, font=font)
            draw.text((margin, y), line, fill=(0, 0, 0), font=font)
            y += (bottom - top) + line_spacing
        return image

    def _pick_font(
        self, font_size: int
    ) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        candidates = self._build_font_candidates()
        for font_path in candidates:
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), size=font_size)
                except Exception:
                    continue
        logger.warning(
            "[torrent_analyze] 未找到配置字体/font.ttf/MapleMono 字体，已回退默认字体原样渲染。"
        )
        return ImageFont.load_default()

    def _build_font_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if self.preferred_font_filename:
            candidates.append(self.font_dir / self.preferred_font_filename)
        else:
            candidates.append(self.font_dir / "font.ttf")

        for font_name in self.maple_mono_font_order:
            name = str(font_name).strip()
            if name:
                candidates.append(self.font_dir / name)
        return candidates

    @staticmethod
    def _default_maple_order() -> list[str]:
        return [
            "MapleMono-CN-Regular.ttf",
            "MapleMono-CN-Medium.ttf",
            "MapleMono-CN-Light.ttf",
            "MapleMono-NF-CN-Regular.ttf",
            "MapleMono-NF-CN-Medium.ttf",
            "MapleMono-NF-CN-Light.ttf",
            "MapleMono-Regular.ttf",
        ]

    def _concatenate_images(
        self, text_image: Image.Image, images: list[Image.Image], margin: int = 20
    ) -> Image.Image:
        text_width, text_height = text_image.size
        total_height = text_height + margin
        resized_images: list[Image.Image] = []

        for image in images:
            ratio = image.height / image.width
            new_height = int(text_width * ratio)
            resized = image.resize((text_width, new_height))
            resized_images.append(resized)
            total_height += new_height + margin

        final_image = Image.new("RGB", (text_width, total_height), color=(255, 255, 255))
        final_image.paste(text_image, (0, 0))
        y = text_height + margin
        for image in resized_images:
            final_image.paste(image, (0, y))
            y += image.height + margin
        return final_image
