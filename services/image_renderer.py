from __future__ import annotations

import asyncio
import os
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
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
        candidates = []

        # Common places when user manually uploads fonts on AstrBot/Linux.
        common_roots = [
            Path("/AstrBot/data/fonts"),
            Path("/AstrBot/data"),
            Path("/usr/local/share/fonts"),
            Path("/usr/share/fonts"),
            Path.home() / ".local" / "share" / "fonts",
            Path.cwd(),
        ]
        maple_names = [
            "MapleMono-CN-Regular.ttf",
            "MapleMono-CN-Medium.ttf",
            "MapleMono-CN-Light.ttf",
            "MapleMono-NF-CN-Regular.ttf",
            "MapleMono-NF-CN-Medium.ttf",
            "MapleMono-NF-CN-Light.ttf",
            "MapleMono-Regular.ttf",
        ]
        for root in common_roots:
            for name in maple_names:
                candidates.append(root / name)
                candidates.append(root / "fonts" / name)

        # Env override for container runtime.
        env_font_path = (
            os.getenv("ASTRBOT_FONT_PATH", "").strip()
            or os.getenv("ASTRBOT_PLUGIN_FONT_PATH", "").strip()
        )
        if env_font_path:
            candidates.insert(0, Path(env_font_path))

        candidates.extend(
            [
            Path(__file__).resolve().parents[1] / "SourceHanSerifSC-Light.otf",
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("/usr/share/fonts/truetype/arphic/ukai.ttc"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            ]
        )
        for font_path in candidates:
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), size=font_size)
                except Exception:
                    continue
        logger.warning("[torrent_analyze] 未找到可用中文字体，图片中文可能显示为方框。")
        return ImageFont.load_default()

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
