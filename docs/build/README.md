# 构建

所有命令在项目根目录执行，相对路径以该目录为基准。命令中的 `PATH_TO_…` 是占位符，须换成自己的实际路径；路径含空格时保留引号。需要 Python 3.10+，检查另需 Node.js 18+；游戏读取使用 [UndertaleModCli](https://github.com/UnderminersTeam/UndertaleModTool)（UMT CLI，支持 `.exe` 或 `.dll`，后者需要 `dotnet`）。原版与汉化版游戏分开保存，工具只读游戏包。

## 1. 准备语言文件

统一输入为 `input/ch1/` 至 `input/ch5/`，每章五份文件：

| 文件名 | 内容与来源 |
|---|---|
| `lang_en.json` | 英文原版；第 1 章复制语言文件，第 2–5 章从脚本提取 |
| `lang_ja.json` | 原版各章 `lang/lang_ja.json` |
| `lang_zh.json` | 汉化各章 `lang/lang_en.json`，复制后改名 |
| `lang_zh_names.json` | 汉化各章 `lang/lang_en_names.json`，复制后改名 |
| `lang_zh_recruitable.json` | 汉化各章 `lang/lang_en_names_recruitable.json`，复制后改名 |

第 1 章英文复制原版 `chapter1_windows/lang/lang_en.json`。第 2–5 章的英文默认值位于 GML 文本调用中，运行：

```sh
python -m tools.text.extract_english --game "PATH_TO_ORIGINAL_GAME" --umt "PATH_TO_UMT/UndertaleModCli.exe" --out local/english-input
```

游戏目录采用 `chapterN_windows/` 布局。输出为 `local/english-input/ch2..ch5/lang_en.json`，已有输出目录不会覆盖。将各章文件复制到 `input/chN/`。若已有反编译 GML，可用 `--code "PATH_TO_GML"` 替代 `--game/--umt`，该目录内须含 `ch2/` 至 `ch5/`。

同 key 的不同默认文本按 `config/text/english-choices.json` 中的已审选择处理；新增冲突会停止并生成候选报告。语言须来自匹配版本，不在游戏安装目录中改名或覆盖。格式详见[文本契约](../data/TEXT.md)。

准备齐 25 份文件后导入：

```sh
python -m tools.text.import_texts --input input --out build/texts
```

## 2. 准备网站素材

```sh
python -m pip install -r requirements-assets.txt
python -m tools.assets.build_assets --game "PATH_TO_ORIGINAL_GAME" --zh-game "PATH_TO_PATCHED_GAME" --umt "PATH_TO_UMT/UndertaleModCli.exe"
```

导出 Logo、书台、互动贴图和音效，转换汉化第一章 `fnt_main` 为标题使用的 WOFF2。它不提供五章台词的完整字体还原。素材先在 `local/asset-build/<批次>/` 验证，再写入 `local/ui-assets/`；被替换文件保存在该批次，日志及机器路径仅留本地。

`config/site-assets.json` 决定发布哪些资源及其路径；不递归发布导出目录。JetBrains 字体和占位 GIF 已随仓库提供，来源见 [THIRD_PARTY](../../THIRD_PARTY.md)。仅有语言表不能完成当前完整站点构建。

## 3. 可选上下文与版本信息

自备匹配版本的 GML，按 `ch1..ch5/*.gml` 放置：

```sh
python -m tools.context.build_context_all --code "local/code" --texts build/texts --out local/context-all
python -m tools.context.verify_context_all --code "local/code" --texts build/texts --out local/context-all
```

更换语言或源码后重新生成。上下文为局部静态结构，边界和产物见[上下文契约](../data/CONTEXT.md)。

`local/release.json` 可填写 `game_version`、`game_release_date`、`translation_version`，以及当前 `build/texts/manifest.json` 的 SHA-256 字段 `text_manifest_sha256`；未绑定或摘要不符时页面显示版本待核对。

可选 Wiki 位置包放在 `local/source-links/`，格式见[文本契约](../data/TEXT.md)。缺少它不影响检索和上下文；链接目标的线上版本可能与本地源码不同。

## 4. 装配与检查

```sh
python -m tools.site.build_site
python -m tools.check --full-site
python -m tools.site.serve --port 8800
```

通过 <http://127.0.0.1:8800/> 使用，或运行 `preview.cmd` 启动本地预览。页面加载数据和 Worker 需要 HTTP，不能直接双击 HTML。

装配流程为 `input → build/texts → build/site-data → dist`，并加入已准备的素材和可选数据。构建会校验摘要、资源路径和输出清单；发现未知的 dist 文件时停止，不自动清空。

`python -m tools.check` 不需要游戏材料，运行代码层的 Python/JavaScript 检查；`--full-site` 增加对已有完整数据的检查，不负责构建。自动检查不能代替实际页面、声音和游戏语义核对。

`input/`、`local/`、`build/`、`dist/` 不提交。部署时使用构建后的 `dist/`；部署与源码推送分别安排。

## 5. 发布到 GitHub Pages

完整构建并检查通过后，提交源码并推送 `main`，再运行 `python -m tools.site.publish`。该命令核对构建清单和文件摘要，将网站成品发布到 `origin/gh-pages`，保留发布历史，不切换工作分支、不上传本地原料。要求工作区干净且本地 `main` 与远程一致；推送失败时不会强制覆盖远程。

首次在仓库 Settings → Pages 选择 Deploy from a branch、`gh-pages`、`/(root)`。以后更新该分支会自动发布；在 Actions 查看发布状态。`main` 存源码，`gh-pages` 存网站成品，因此只推送 `main` 不会更新网站。
