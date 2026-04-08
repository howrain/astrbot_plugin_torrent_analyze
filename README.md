<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_torrent_analyze?name=astrbot_plugin_torrent_analyze&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_torrent_analyze

_✨ 磁链验车与种子信息分析插件（AstrBot） ✨_

[![License](https://img.shields.io/badge/License-AGPLv3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.9.2%2B-orange.svg)](https://github.com/AstrBotDevs/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-howrain-blue)](https://github.com/howrain)

</div>

AstrBot 插件，迁移自 hoshinot 的 `torrent_analyze`，用于查询磁链或种子 hash 的基础信息，并可选返回截图拼图（支持高斯模糊）。

> 参考项目：<https://github.com/SlightDust/torrent_analyze_HoshinoBot>

## 效果示例

发送：

```text
/验车 magnet:?xt=urn:btih:32181995C9D274FCFBE0A5E427F047210E82A53D
```

机器人返回（文本模式）：

```text
种子哈希: 32181995C9D274FCFBE0A5E427F047210E82A53D
文件类型: VIDEO-MKV
种子名称: xxxxx
总大小: 12.34GB
文件总数: 8
```

当 `default_image_enabled = true` 且存在截图时，会返回“文本头 + 最多3张截图”的拼接图片。

## 指令

| 指令 | 说明 |
|------|------|
| `/验车 磁链或hash` | 查询种子信息 |
| `/种子分析 磁链或hash` | `/验车` 别名 |
| `/种子信息 磁链或hash` | `/验车` 别名 |
| `/种子详情 磁链或hash` | `/验车` 别名 |
| `/验车帮助` | 查看帮助说明 |
| `/验车配置` | 查看当前生效配置（只读） |

## 安装

推荐：在 AstrBot WebUI 的插件管理页面安装并启用。

手动安装：将插件目录放入 AstrBot 的 `data/plugins/` 目录，随后重启或热重载插件。

## 配置

配置仅通过 AstrBot WebUI 插件配置页面修改。

| 配置项 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| `default_blur_radius` | int | `10` | 截图返回时的默认高斯模糊等级，范围建议 `0~10` |
| `default_image_enabled` | bool | `true` | 是否默认返回截图拼图 |
| `request_retry_times` | int | `20` | 调用 whatslink API 的最大重试次数 |
| `request_retry_interval_sec` | float | `3.0` | 调用 whatslink API 的重试间隔（秒） |
| `font_dir` | string | `/AstrBot/data/fonts` | 字体查找目录，推荐固定使用该目录 |
| `font_filename` | string | `""` | 指定字体文件名；为空时默认优先查找 `font.ttf` |
| `maple_mono_font_order` | list | 见配置默认值 | 仅在指定字体与 `font.ttf` 都不存在时按顺序查找 |

### 中文乱码排查

如果图片中的中文显示为方框（口口口），通常是容器里没有可用的中文字体，或字体文件名与配置不一致。

建议：

1. 在运行环境安装 CJK 字体（例如 `fonts-noto-cjk`）。
2. 下载 Maple Mono 字体文件，推荐改名为 `font.ttf`。
3. 将字体放到指定目录：`/AstrBot/data/fonts/font.ttf`（即 `font_dir/font.ttf`）。
4. 如需指定其他文件名，可配置 `font_filename`（例如 `MapleMono-CN-Regular.ttf`）。
5. 若未设置 `font_filename`，插件默认优先查找 `font.ttf`。
6. 若仍未找到，会按 `maple_mono_font_order` 的顺序依次查找 MapleMono 文件。
7. 若仍未找到，将使用 Pillow 默认字体原样渲染（中文可能显示方框）。
8. 字体下载地址（官方）：<https://github.com/subframe7536/maple-font/releases/latest>。
9. 完成后重启 AstrBot 或热重载插件。

## 遗留问题
1. whatslink.info有频率限制。触发频率限制时，会反复调用`request_retry_times`次接口，每次间隔`request_retry_interval_sec`秒。

## 存储说明

遵循 AstrBot 插件存储规范，持久化数据写入：

`data/plugin_data/astrbot_plugin_torrent_analyze/`

主要文件：

- `torrent_info_cache.json`：种子信息缓存
- `rendered/`：截图拼图缓存输出目录

## 依赖

- Python >= 3.10
- AstrBot >= 4.9.2
- [httpx](https://pypi.org/project/httpx/)
- [Pillow](https://pypi.org/project/Pillow/)
