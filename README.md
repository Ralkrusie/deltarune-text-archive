# DELTARUNE Text Archive

DELTARUNE 台词库：检索、对照英文／日文／中文文本，查看原始字符串和局部对话上下文的非官方工具。

## 功能与状态

- 第 1–5 章三语检索；章节多选、大小写、整词、正则与高亮。
- 源码／简洁模式，中文人名三种译法与智能对照，横排／纵排，复制 key 或整条结果。
- 可选静态上下文：同文件文本、局部选择与条件分支。当前为测试版，分支判断可能有误。
- 可关闭的灵魂互动彩蛋。

“还原”模式目前只有占位展示；说话人、头像及文字运动等属性尚未接入。简洁文本和上下文都不能代替游戏实际表现，未找到源码引用也不代表文本不可达。网站尚未部署。

## 构建与开发

需要 Python 3.10+；自动检查另需 Node.js 18+。文本管线使用 Python 标准库，前端为原生 HTML/CSS/JavaScript，无 npm 依赖。游戏资源导出另需 UndertaleModCli 和字体转换依赖。

自备原版游戏、汉化版游戏与匹配版本的语言文件，按[构建说明](docs/build/README.md)准备输入并生成 `dist/`。第 2–5 章英文表需从游戏脚本提取，命令也在该说明中。上下文还需要对应版本的 GML。

常规检查：`python -m tools.check`。已有完整站点时运行 `python -m tools.check --full-site`，增加全量文本与搜索检查。

| 目录 | 职责 |
|---|---|
| `web/` | 网页及随仓库提供的字体、占位图 |
| `tools/text/` | 英文提取、统一语言导入 |
| `tools/assets/` | 游戏贴图、音效、字体导出与转换 |
| `tools/context/` | GML 解析、上下文生成与验证 |
| `tools/site/` | 网站数据、装配与本地服务 |
| `tests/` | 按功能分组的自动检查 |
| `config/` | 资源映射与上下文文件选择 |
| `docs/build/`、`docs/data/` | 构建方法、文本与上下文契约 |
| `input/`、`local/` | 自备输入、素材及本地记录，不提交 |
| `build/`、`dist/` | 中间数据与网站产物，不提交 |

贡献前阅读 [AGENTS.md](AGENTS.md)。数据处理规则见[文本契约](docs/data/TEXT.md)和[上下文契约](docs/data/CONTEXT.md)。

## 许可证

原创源码和文档采用 [MIT](LICENSE)。游戏文本、中文译文、游戏素材、占位 GIF 和第三方字体不在该授权范围内，来源见 [THIRD_PARTY.md](THIRD_PARTY.md)。
