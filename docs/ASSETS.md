# 网站资源约定

`dist/assets` 是构建产物，不能手动往里放文件。实际发布清单由 [config/site-assets.json](../config/site-assets.json) 管理，构建器只复制明确列出的文件。清单使用项目相对路径，不含机器路径。

## 发布目录

```text
assets/
  ui/
    brand/       # 标题 logo、书台等站点界面贴图
    fonts/       # 标题及还原预留页使用的 main 字体
    placeholder/ # 还原入口的等待 GIF
  soul/
    sprites/     # 五色灵魂、斧子、子弹、粒子、蓄力轮廓
    audio/       # 变色、射击、蓄力、冲刺、换线音效
```

文件范围以资源清单为准。保留游戏资源名及帧号，避免重命名后失去源码对应关系；发布目录按用途分组，不使用原料导出批次名 `yellow/`、`extra/`。

JetBrains Mono NL 是随源码分发的第三方字体，从 `web/fonts/` → `dist/fonts/`，与 OFL 和来源记录一起复制；示例站也使用这份字体。它与自备游戏素材的入口不同。

## 原料与发布分开

| 层次 | 位置 | 用途 |
|---|---|---|
| 原始导出 | `local/ui-assets/` 及其 `yellow/`、`extra/` | 保持现有导出批次和来源记录；包含未使用帧，不直接发布 |
| 构建映射 | `config/site-assets.json` | 一项 `source` 对应一项 `target`，决定正式网站用什么、放哪里 |
| 网站产物 | `dist/assets/ui/`、`dist/assets/soul/` | 仅实际消费的文件，无来源记录、绝对路径或未使用帧 |
| 构建记录 | `build/site-build.json` | 每个输出文件的大小和 SHA-256，用于核对发布包 |

导出脚本继续写原料目录；不需要为排版整理重新导出游戏。`local/ui-assets` 是沿用的历史入口名，当前不把它当作未来全部游戏素材的统一仓库。未来还原素材应使用独立的 `local/dialogue-assets/` 原料入口，并届时扩展构建验证。

当前不发布 `spr_heart_0.png`、旧的 `spr_orangeheart_0.png`、独立描边 `spr_orangeheart2_3.png`、顶层重复黄魂帧。橙魂使用黑边完整的 `spr_orangeheart2_0.png`。黄橙蓄力声字节一致，发布时共用一份 `soul/audio/snd_chargeshot_charge.wav`；原料中的两份及其来源均保留。

## 还原模式的预留边界

未来使用独立命名空间，尚未创建空目录或接入还原功能：

```text
assets/dialogue/<资源包ID>/ch<章节>/<语言>/
  sprites/
  fonts/
  audio/
```

资源包 ID 应绑定游戏版本，以及适用时的汉化补丁版本。英语观察不能直接当成汉化素材：同名资源在不同章节、版本、语言中可能不同，不能仅按文件名去重。

还原模式的素材索引应保留原资源名、帧号、尺寸、原点、摘要和适用版本；台词用法通过资源 ID 引用它。位置、缩放、颜色和运动属于具体使用时的属性，不应烘焙到贴图或写进文件名。

灵魂互动是站点彩蛋，不是还原模式素材目录。未来即使两者使用同一图，也先保留用途与版本对应关系，确认内容一致后再决定共享，避免把这里的网页旋转、缩放、裁切当成游戏台词的证据。

## 增加或调整资源

1. 按 [BUILDING](BUILDING.md) 准备本地导出，来源记录留在 local。
2. 在 `config/site-assets.json` 增加明确的 source/target，更新消费代码。当前构建器允许 `local/ui-assets/` 和 `web/assets/` 来源；预留的还原入口需随正式功能一起接入。
3. 运行构建并检查图像、声音和相关页面。缺文件、越界路径、重复目标会报错，不会递归复制整个原料目录。
4. 改路径时核对旧构建记录，再归档旧输出；构建器仍拒绝未知的 dist 文件，不自动删除它们。

`Man_overworld_tree.gif` 是还原入口占位图，原样保存在 `web/assets/ui/placeholder/` 并随源码仓库提供；同目录 SOURCE.json 记录 Wiki 来源与摘要。它不属于台词还原素材索引，也不是游戏导出脚本的输出。游戏素材及 main 字体可通过 `tools/build_assets.py` 一键生成，命令见 BUILDING。
