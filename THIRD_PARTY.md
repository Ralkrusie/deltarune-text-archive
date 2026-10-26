# 第三方内容与来源

## JetBrains Mono NL

`web/fonts/JetBrainsMonoNL-Regular.ttf` 为 JetBrains Mono NL 2.304，原样取自 [官方发行包](https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304)。

下载位置与 SHA-256 见 [字体来源记录](web/fonts/SOURCE.json)，SIL Open Font License 见 [OFL.txt](web/fonts/OFL.txt)，构建时一并提供。字体适用自身的 OFL，不适用项目源码的 [MIT License](LICENSE)。

## 本地游戏与汉化素材

正式网站使用的素材由 [config/site-assets.json](config/site-assets.json) 明确列出；准备方法和复现限制见 [构建说明](docs/BUILDING.md)。原始导出及来源记录保存在忽略目录 `local/ui-assets/`，源码候选清单包含导出脚本，不包含这些素材文件。

| 用途 | 来源 |
|---|---|
| 标题 Logo、书台 | 原版 CH1 `IMAGE_LOGO`、CH2 `spr_castle_book_pillar` 第 0 帧 |
| 五色灵魂 | 战斗红魂 `spr_dodgeheart`、黄魂 `spr_yellowheart`、绿魂 `spr_greenheart`、橙魂 `spr_orangeheart2`、紫魂 `spr_purpleheart`；具体章节和帧见导出脚本与资源清单 |
| 黄魂子弹、蓄力与射击音效 | 原版 CH2，`tools/export_yellow_soul.csx` |
| 绿魂斧子、橙紫粒子与轮廓、相关音效 | 原版 CH4/CH5，`tools/export_extra_souls.csx` |
| 变色音效 `snd_great_shine` | 原版 CH2，`tools/export_soul_switch.csx` |
| 中文 main 字体 | 由汉化第一章 `fnt_main` 图集和字符表通过 `export_main_font.csx`、`font_woff.py` 转换，用于标题及还原入口占位文案 |

导出脚本只读游戏包。显示用 PNG 保留原始像素，网页缩放、朝向、动画属于前端适配；当前玩法及适配边界见 [互动说明](docs/INTERACTION.md)。未使用的旧帧不随正式网站发布。

游戏及汉化素材不适用 JetBrains 字体的 OFL，也不因项目源码开源而自动获得再分发许可。公开素材范围与源码许可证分别处理。

## 还原入口占位图

`Man_overworld_tree.gif` 来自 [DELTARUNE Wiki 的 Man 图片](https://deltarune.wiki/w/Man#/media/File:Man_overworld_tree.gif)，由用户提供，原样纳入 `web/assets/ui/placeholder/`。同目录 SOURCE.json 记录来源和 SHA-256。它只用于还原入口占位，不是台词还原素材；该图片不在本项目 MIT 源码授权范围内。

## 真实台词示例

`examples/input/ch1..ch5/` 为游戏及汉化语言表的少量原样节选，原始 key、版本和输入摘要见 [examples/source.json](examples/source.json)，使用说明见 [示例 README](examples/README.md)。

游戏文本及中文译文不是本项目原创内容，不适用 JetBrains OFL，也不在本项目 MIT 源码授权范围内。
