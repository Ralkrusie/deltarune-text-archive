# 首次提交文件清单

更新：2026-10-26。目标仓库为 `Ralkrusie/deltarune-text-archive`。逐文件范围以 [config/first-commit-files.txt](../config/first-commit-files.txt) 为准；这是白名单，不是整个工作目录递归上传。本次按该清单创建首个源码提交；不部署网站。

## 纳入首次提交

| 内容 | 范围 |
|---|---|
| 入口 | README、AGENTS、LICENSE、THIRD_PARTY、.gitignore、preview.cmd |
| 网页 | web 源码、占位 GIF 及来源记录、JetBrains 字体和 OFL |
| 工具 | 当前文本导入、网站构建、预览、独立上下文解析、验证、素材导出 |
| 可选兼容工具 | prepare_inputs、prepare_source_links、verify_migration；不属于首次运行必需步骤 |
| 测试 | Python 与 JavaScript 检查；全量数据检查需自备完整输入 |
| 示例 | 40 条真实游戏／汉化节选、来源摘要及说明，按第三方内容单独标识 |
| 配置 | 上下文选择、站点资源映射、候选白名单 |
| 文档 | 当前状态、输入／显示契约、构建、资源、上下文、互动及本清单 |

公开的 `context_conditions.py` 只保留现用分析能力。历史 C1 入口已拆出，不进入候选；当前解析包自带所需实现，不在运行时导入旧项目。

## 留在本地

- 完整 `input/`、`local/`、`build/`、`dist/`，以及虚拟环境、机器路径、游戏包、GML、数据库、运行记录、存档。
- `legacy_context_conditions.py`、`prepare_context_pilot.py`、`verify_context_pilot.py`、`verify_context_conditions.py` 和旧试点配置。
- 旧步骤报告、研究日志、迁移计划、DEVELOPMENT_HISTORY 等历史材料；当前操作入口已从这些材料中独立。

占位 GIF 已明确纳入候选并附来源。其余游戏贴图、声音和中文 main 字体不在源码候选中，可用统一工具从自备游戏生成。提交导出脚本不等于提交这些文件。正式网站发布包是另一个范围，不能以源码清单代替。

## 如何复核

按白名单复制到不含 `local`、完整输入或相邻旧项目的新目录，运行：

```sh
python tools/check_demo.py
```

提供完整材料并构建站点后，再运行 `python tools/check_demo.py --full-site`。能力与材料对应关系见 [README](../README.md)，构建命令见 [BUILDING](BUILDING.md)。本轮文件摘要与检查日志存于本地 `build/release-audit.json`，不上传；后续修改需要重新检查，旧快照不是永久通过证明。

## 本次发布决定

- 原创源码及文档采用 [MIT License](../LICENSE)，版权署名为 Ralkrusie。
- 首次提交包含已确认的 40 条真实示例和占位 GIF，并保留第三方来源说明；这些内容不纳入 MIT 源码授权。
- 完整语言原料、游戏素材、研究记录和网站产物仍留本地。仓库公开不表示已经部署网站。
- 后续新增或修改文件需重新检查，首次检查结果不会自动覆盖后续提交。
