# DELTARUNE Text Archive

DELTARUNE 台词库：用于检索、对照英文／日文／中文文本，并查看原始字符串和局部对话上下文的非官方工具。

当前支持第 1–5 章。本仓库提供源码与示例，尚未部署公开网站；说话人、头像、文字运动等属性尚未接入此版本。

## 功能

- 三语检索、章节多选、大小写／整词／正则匹配和结果高亮；显示语言不限制搜索语言。
- **源码模式**显示 key 对应的原始字符串及控制串；**简洁模式**提供便于阅读的文本。源码模式不是完整 GML 浏览器。
- 中文人名“不译／仅译招揽／翻译”及智能对照，支持横排、纵排和窄屏布局。
- 复制 key 或整条结果；可选源码位置链接。
- 可选静态上下文：展示同文件文本、局部选择与条件分支；无法确定的连接保留为独立块。窗口可从右下角拖动调整大小。
- 完整站点包含可关闭的灵魂主题与桌面互动彩蛋，详见[灵魂互动说明](docs/INTERACTION.md)。
- “还原”模式目前只有占位展示，尚未实现实际台词样式还原。

简洁模式不是游戏渲染器：图片和动态参数可能显示占位，未确认控制串保留原样。上下文不等于完整执行路径，未观察或无源码引用也不代表文本不可达。

## 快速开始：40 条真实台词示例

需要 **Python 3.10+**；运行 JavaScript 检查另需 **Node.js 18+**（本轮使用 Node 24 验证）。示例与文本管线无需 npm 或第三方 Python 包；从游戏导出素材另需 UMT 和字体转换依赖。

在项目根目录执行：

```sh
python tools/build_demo.py
python -m http.server 8801 --bind 127.0.0.1 --directory build/open-source-demo
```

打开 <http://127.0.0.1:8801/>，停止服务按 Ctrl+C。端口被占用时可换一个数字。请通过 HTTP 使用，不要直接双击 HTML：浏览器的数据加载和 Worker 需要 HTTP 环境。

示例从五章输入各摘录 8 条真实文本，保留原始 key、控制串和中文译法，没有游戏贴图、音效或上下文包。不需要完整游戏安装或旧项目。游戏版本为 v0.0.253（2026-07-31），中文为好人汉化组 V261024；来源摘要见 [examples/source.json](examples/source.json)。示例是游戏／汉化内容，不是本项目原创文本。详见[示例说明](examples/README.md)。

## 使用自己的完整输入

准备一个目录，每章五份 UTF-8 JSON：

```text
input/
  ch1/
    lang_en.json
    lang_ja.json
    lang_zh.json
    lang_zh_names.json
    lang_zh_recruitable.json
  ch2/  # 相同五个文件
  ch3/
  ch4/
  ch5/
```

每份文件保持 `key → 字符串` 格式。中文补丁中的 `lang_en.json` 可能实际上是中文，需手动区分并改名；不要覆盖原游戏文件。缺失翻译省略 key，空字符串原样保留。

```sh
python tools/import_texts.py --input input --out build/texts
```

接着按[完整站点构建说明](docs/BUILDING.md)一键导出游戏素材和中文 main 字体，再构建：

```sh
python tools/build_site.py
python tools/serve.py --port 8800
```

**完整构建需要自备素材，只有语言表还不够。** 只想验证文本导入和网页显示可先使用上面的示例。输入格式见[输入契约](docs/INPUTS.md)，显示规则见[显示契约](docs/TEXT_DISPLAY.md)。

### 可选：生成上下文

准备与文本版本对应的反编译 GML 目录（包含 `ch1..ch5`），在正式网站构建前执行：

```sh
python tools/build_context_all.py --code /path/to/code --texts build/texts --out local/context-all
python tools/verify_context_all.py --code /path/to/code --texts build/texts --out local/context-all
```

将 `/path/to/code` 替换为实际目录，Windows 路径有空格时加引号。解析工具已包含在本仓库中；不需要旧项目目录。源码不随仓库提供，本工具也不负责反编译。更新语言输入后需重新生成上下文。机制、边界和验收见[上下文说明](docs/CONTEXT_INDEPENDENT.md)。

## 检查

```sh
python tools/check_demo.py
# 已经构建完整站点时，再检查全量字段与真实搜索样本：
python tools/check_demo.py --full-site
```

第一条运行全部 Python 测试、可独立运行的 JS 检查并构建示例；第二条还检查已有完整站点的复制、搜索及字段往返。它们不会重建正式 dist，也不验证所有真实游戏状态。只有示例时不要使用 `--full-site`。灵魂专项检查见[对应说明](docs/INTERACTION.md)。

## 可以复现到什么程度

| 拿到的材料 | 可复现内容 |
|---|---|
| 本仓库及示例 | 40 条真实节选的检索、三语对照、源码／简洁显示和常规自动检查 |
| 再提供五章语言表 | 完整文本导入与网页数据包；完整站点构建还需下列视觉素材 |
| 再提供匹配版本的 GML | 自行生成五章静态上下文；不需要旧分析器或旧项目 |
| 再提供资源清单所需素材 | 当前完整网站与灵魂互动；可用统一工具导出素材并转换 main 字体；占位 GIF 已随仓库提供 |
| 旧格式来源数据库与 GML（可选） | 迁移 Wiki 源码位置链接；仅有语言表和 GML 尚不能用此迁移工具重建同样的链接包 |

运行时采集、人工广义说话人审阅和真实样式还原不在本次可复现功能内。源码仓库、完整输入、网站发布包分别管理。

## 项目结构

| 目录 | 内容 |
|---|---|
| `web/` | 原生 HTML、CSS、JavaScript、附来源的占位 GIF 与附许可证的 JetBrains 字体 |
| `tools/` | 导入、构建、源码解析、验证和素材导出工具 |
| `tests/` | 自动检查 |
| `examples/` | 小型真实台词示例及来源 |
| `config/` | 上下文选择、网站资源映射与公开候选清单 |
| `docs/` | 输入、显示和构建说明 |
| `input/`、`local/` | 自备原料、界面素材和本地证据，不提交 |
| `build/`、`dist/` | 中间产物和网站发布包，不提交源码仓库 |

管线为 `input → import_texts → build/texts → build_site_data → build/site-data → build_site → dist`；可选的 GML 上下文和本地视觉素材在站点装配阶段加入。新贡献者和 AI 从 [AGENTS](AGENTS.md) 与[当前状态](docs/STATUS.md)继续。

## 来源与许可证

这是非官方项目。DELTARUNE 游戏文本及素材属于各自权利人，中文文本来自好人汉化组。JetBrains Mono NL 附带 SIL OFL；详见[第三方说明](THIRD_PARTY.md)。

项目原创源码及文档采用 [MIT License](LICENSE)。游戏文本、中文译文、GIF、其他游戏素材及第三方字体不在这份 MIT 授权范围内，各自来源与许可见[第三方说明](THIRD_PARTY.md)。源码仓库的首次发布范围见[文件清单](docs/FIRST_COMMIT.md)，网站部署另行安排。
