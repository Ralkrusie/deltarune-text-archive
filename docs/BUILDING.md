# 完整站点构建

先按根 README 导入三语语言表。正式构建需要本地游戏素材；在网页设置里关闭彩蛋不会免除这些构建输入。只验证文本功能可使用不含游戏素材的示例站。

## 一键准备游戏素材与字体

需要原版游戏、安装中文补丁后的另一份游戏，以及 **UndertaleModCli**（UMT 的命令行版，GUI 程序不能替代）。工具不随仓库捆绑；从 [UndertaleModTool](https://github.com/UnderminersTeam/UndertaleModTool) 获取 CLI，并满足所用版本的 .NET 运行环境要求。支持传入 `.exe` 或 `.dll`；后者由 `dotnet` 启动。

在项目根目录安装可选依赖（只做示例或文本构建不需要）：

```sh
python -m pip install -r requirements-assets.txt
```

一条命令导出本网站使用的贴图、音效，并生成中文 main 网页字体：

```sh
python tools/build_assets.py --game "D:/Games/DELTARUNE" --zh-game "D:/Games/DELTARUNE_zh" --umt "C:/Tools/UMT/UndertaleModCli.exe"
```

路径仅为示例，换成自己的安装位置。两个游戏根目录需包含 `chapterN_windows` 子目录；原版使用第 1、2、4、5 章，汉化版使用第 1 章的 `fnt_main`。UMT 通过 `load` 和 `-s` 执行只读导出，不传保存游戏包的 `-o` 参数。

如果已经准备好统一语言输入 `input/`，末尾加 `--build-site` 可继续导入文本并构建整个网站：

```sh
python tools/build_assets.py --game "D:/Games/DELTARUNE" --zh-game "D:/Games/DELTARUNE_zh" --umt "C:/Tools/UMT/UndertaleModCli.exe" --build-site
```

它不会自动反编译 GML 或重做上下文。可选上下文/源码映射存在时仍会核对文本摘要，过期则报错，按下面说明重新生成。

## 输出与校验

- 先导出到 `local/asset-build/<批次>/`，包含日志、字体图集/字符表和输入摘要。失败时保留诊断；导出或校验失败不会替换现有素材。
- 通过网站资源清单和字体检查后，仅更新 `local/ui-assets/` 中实际需要的文件。被替换的旧文件保存在该批次的 `previous/` 下；不清理原有未使用帧。
- `local/ui-assets/asset-build.json` 记录当前构建来源，含本机路径，仅留本地。工具核对导出前后游戏文件摘要。
- `web/assets/ui/placeholder/Man_overworld_tree.gif` 已随仓库提供，来源见同目录 SOURCE.json；不再需要手工下载或复制到 local。
- 站点装配只按 [资源映射](../config/site-assets.json) 复制文件，不递归发布原料和记录。目录约定见 [ASSETS](ASSETS.md)。

`tools/font_woff.py` 把字体图集中每个实心像素转换为矩形轮廓，保留既有基线与 main 字距规则，并固定时间戳，使相同输入与依赖重复生成相同 WOFF2。当前只构建用于站点标题和占位文案的中文 main，不代表已经完成五章全部字体选择或台词还原。

本轮使用现有 UMT CLI（net10.0 构建）和 requirements-assets.txt 中的依赖完成原版/汉化包实测；不同 UMT 版本可能存在脚本 API 差异，失败详情见对应批次日志。语言和素材版本由使用者提供的文件决定，不会自动下载或更新游戏。

单项导出脚本仍可用于排查：Logo 用 `export_brand_assets.csx`，书台用 `export_book_asset.csx`，基础灵魂用 `export_soul_assets.csx`，黄魂用 `export_yellow_soul.csx`，变色声音用 `export_soul_switch.csx`，其余互动素材用 `export_extra_souls.csx`，main 图集用 `export_main_font.csx`。统一工具负责这些脚本的章节和环境变量配置。

## 可选数据

- 上下文：按 [上下文说明](CONTEXT_INDEPENDENT.md) 生成 `local/context-all`，优先于旧的 `local/context-files`。
- 源码链接：`tools/prepare_source_links.py --database /path/to/data.sqlite --code /path/to/code --texts build/texts --out local/source-links` 从旧项目格式的 SQLite 数据库迁移位置，再用指定 GML 核验。它不是直接从游戏生成源码位置的工具。正式构建仅读取生成的 `local/source-links`，不读取旧数据库；没有该映射仍可检索和查看已生成的上下文，但不提供这组 wiki 源码跳转。
- 版本：`local/release.json` 可包含 `text_manifest_sha256`、`game_version`、`game_release_date`、`translation_version`。摘要须绑定当前 `build/texts/manifest.json`，否则显示待核对，不沿用旧版本。

`tools/prepare_inputs.py` 仅为已有语言导出与汉化游戏目录的复制/改名便利工具；手动准备同一 input 契约也可用。来源记录保存在 local，机器路径不进入公开输入。

## 构建与检查

```sh
python tools/build_site.py
python tools/serve.py --port 8800
```

Windows 也可在构建后运行 `preview.cmd`；它启动本机服务并打开浏览器，不负责构建。默认绑定 127.0.0.1，不是公网部署。

```sh
python -m unittest discover -s tests -p test_site_assets.py
python tools/check_demo.py
```

第一项用合成文件检查资源白名单、路径和重复目标；第二项验证独立示例，不需要 local。正式站点还需检查实际图片、字体和声音加载，灵魂逻辑检查见 [互动说明](INTERACTION.md)。

构建校验输入和上下文摘要，按明确清单写入产物；缺失素材、越界路径、重复目标会报错。dist 出现未知文件仍停止供人工检查，不自动清空。更新输入后应重建绑定该输入的上下文和来源映射。改资源路径时先核对并归档旧输出，见 ASSETS。

正式网站构建与公开部署分别处理。完整游戏、原料、反编译源码、机器路径、日志和存档不属于网站发布包；真实游戏资源和源码的许可证/公开范围也须分别决定。
