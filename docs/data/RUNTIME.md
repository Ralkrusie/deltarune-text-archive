# 运行观察与协作采集

## 当前边界

运行工具位于 `tools/runtime/`，使用显式输入，与网页构建独立，不写 `dist`。当前便携发布为 revision 31；安装、启动、导出、收包、GML 编译和带图审阅均可在新项目独立运行，不依赖旧仓库代码。原始 GML、HP 补丁配方和旧版增量包作为显式数据输入。

人工结论合并和网站属性展示尚未接入，当前不是五章采集器。审阅工作台见 [核对说明](../build/RUNTIME_REVIEW.md)。新解释层只认可有实际头像绘制佐证的头像身份信号；无头像气泡中的全局残留人物状态不再当作有效候选，仍保留原始诊断证据。

支持 Windows 英文原版匹配包的第二章。完整副本的其他章节保留存档隔离与既有测试修改，但不宣称已采集。参与者操作见 [试用说明](../build/RUNTIME_PARTICIPANTS.md)。

## 格式与接收规则

ZIP schema 1 根目录包含 `manifest.json` 和三种 JSONL：`capture_<run>_<segment>`、`interactions_<run>_<segment>`、`choices_<run>_<segment>`。接收后原始日志另存于证据目录的 `logs/`。原始行保持原字节；摘要绑定文件、来源库存、原版游戏包、采集器声明版本、模式和 run。每次章节启动有独立 segment，消息编号仅在 segment 内有意义。

只导出三流，不打包游戏、存档、机器路径、截图或整个来源库存；正文可能包含游戏内自选名称。没有联网上传。接收端显式提供可信来源库存，不能信任提交者自带的映射。

六个读取器在 `legacy/` 保持原解释，颜色／运动和 smallface 机制 JSON 随代码提供。消息、主动交互与选择关系分开保存：触发对象不是自动说话人，未知来源不按同文补配，观察不直接变成人工结论。

收包先检查 ZIP 白名单、大小、摘要、版本和三流绑定，再在临时三库中验证；通过后保存不可变原证据，单个 SQLite 事务更新 `library/index.sqlite`。同名 session 被改写会拒收。严格字节前缀追加（包括补完末行、晚到侧流）允许补全，旧包保留；较短旧包重交不会回退当前数据。非前缀或新旧混合三流需人工复核，不擅自拼接。

相同属性复用变体并保留各次观察，不同属性保留差分。不同来源库存／采集器／模式独立分区；`mechanism_selftest` 不算自然覆盖。采集器摘要只校验声明及三流一致，不构成签名认证。接收成功不等于语义已审核。

缺侧流、截断尾行、来源未知和观察不完整均明确报告；完整行损坏或不一致关系拒收。未走到的分支不因此不存在。

参与者默认布局为工具旁的 `capture/{game,saves,sessions,exports}`。`save_layout=local_appdata_v1` 通过子进程环境 `LOCALAPPDATA=<capture>/saves` 将游戏真实读写重定向到本地；不修改系统环境、原版存档或游戏字节。每个副本的锁位于自己的根目录。旧副本由 `tools.runtime.layout` 核验后同盘迁入，复制旧隔离存档但保留原件。

参与者采集结束后，ZIP 刷盘、回读摘要与逐文件原字节对账全部通过，先写恢复凭据，再删除当前 run 对应的两处 JSONL。变动中的文件、其他 run、存档不会删除。清理失败只报告并保留相应文件；再次恢复可从验证过的 ZIP 取回三流，相同内容复用原 ZIP。维护者的独立 `bundles export` 不删除输入；收包库原始证据仍永久保留。

## 命令

日常试玩与对外参与者统一使用发布 ZIP 内的 `DialogueCapture.exe`：解压、选择原版生成 `capture`、开始采集、退出后导出 ZIP。维护者不另建长期使用的开发试玩副本，也不直接改现用 `capture/game`。采集器更新先产出并验证新的分享包，再从同一分享包准备试玩副本；需要延续进度时关闭游戏，复制隔离存档。

以下为维护、收包及故障诊断命令，不是另一套日常试玩流程。在项目根目录执行，`PATH_TO_…` 均为显式输入：

```sh
python -m tools.runtime.kit build --original "PATH_TO_ORIGINAL_GAME" --capture "PATH_TO_VALIDATED_CAPTURE_BUILD" --out local/runtime-kit/r30
python -m tools.runtime.kit install --kit local/runtime-kit/r30 --game "PATH_TO_ORIGINAL_GAME" --out "PATH_TO_NEW_TOOL_HOME/capture"
python -m tools.runtime.launcher launch --capture "PATH_TO_DIALOGUE_CAPTURE/capture"
python -m tools.runtime.launcher recover --capture "PATH_TO_DIALOGUE_CAPTURE/capture"
python -m tools.runtime.layout --source "PATH_TO_OLD_CAPTURE" --tool-home "PATH_TO_DIALOGUE_CAPTURE" --legacy-saves "PATH_TO_OLD_ISOLATED_SAVES"
python -m tools.runtime.bundles export --session "PATH_TO_SESSION" --sources "PATH_TO_SOURCES_JSON" --out local/submission.zip
python -m tools.runtime.bundles receive --bundle local/submission.zip --sources local/runtime-inventories/sources.json --library local/runtime-library
```

kit 构建输入为已验证的完整采集构建目录，含 manifest、sources 和 game；输出使用 COPY／压缩字节增量。现有 r30 kit 已保存，可直接制作分享包、从原版安装，不依赖旧开发游戏副本。修改 GML 后需先完成新的编译与验收，不能把玩家安装副本冒充新的编译输入。安装前逐文件核验原版和补丁，输出必须是新目录且不能位于输入目录内。完整复制后再次核对摘要，成功才写 `capture.json`；失败保留 `INSTALL_INCOMPLETE`，不能当成可启动副本。

revision 30 便携化只对六个 `data.win` 中精确核验的 STRG 隔离路径字符串作等长匿名替换，保留索引和代码；有效路径取当机 `LOCALAPPDATA/profile`。安装摘要与原版来源摘要分别保存。原游戏和存档不修改。

维护者保存 `local/runtime-inventories/sources.json`；历史库存按原始 SHA 放在旁边的 `inventories/<sha>.json`。不能重格式化库存后仍沿用旧摘要。

制作无需 Python 的 Windows 工具需要 PyInstaller，它只是打包依赖：

```sh
python -m pip install --target local/runtime-build-deps pyinstaller
python -m tools.runtime.package_participant --kit local/runtime-kit/r30 --out "PATH_TO_NEW_RELEASE" --dependencies local/runtime-build-deps
```

发布物是输出目录中的 ZIP，必须保留整个解压目录。它包含两份机制 JSON、Python/Tk 运行库及项目运行工具源码，不含游戏、旧记录和存档。发布前应验证打包后的实际 EXE。

## 已核验与待验收

2026-10-27 本机：485 个原文件摘要、6 个增量补丁的流式重建和完整安装通过；安装后启动器正常退出，原版存档摘要保持。最终冻结 EXE 的受控第二章测试生成 14 页、4 次选择（3 次确认）、4 条 smallface，成功导出并被新接收器读入。该测试不增加自然覆盖。

历史真实 run `e3fc24015ab9493aa9d655300519db18`：416 页／331 消息变体、114 次交互、25 次选择、5 条 smallface 的事件、消息主体和关系与旧三库逐行相同；重复导入新增为 0，15 页未知来源仍未知。核验了 333 个实际源码文件，旧库存 10,315 个及当前库存 10,616 个 occurrence 均与新上下文精确匹配。

| 真实台词 | 迁移前 → 迁移后 |
|---|---|
| #159 `Don't bother. It tastes awful.` | Susie 主句＋Ralsei smallface 保持；交互对象仍另列为假人 |
| #196 `Mama mina! As long as ze purple girl is by your side!` | 人物未知保持；交互对象／贴图线索保留，不自动认作人物 |
| #203 `Hey, boss! I'll have a Dark Candy Starfait!` | 来源未知保持；旧咖啡馆默认贴图仍不能当作 NPC 身份 |
| #214 `They are free... for a price.` | Lancer 主句、Susie 与 Lancer 插话及选择关系保持 |

证据在 `local/runtime-migration/{verification,bundle-verification,frozen-mechanisms,frozen-receive}.json` 和 `local/runtime-kit/r30-verification.json`，不进入网站。

用户已在本机实际安装并游玩两段：47 页（43 个变体、1 次主动交互）与 29 页（29 个变体），来源全部对应，三流验证无警告；这两段未记录到选择题／smallface。两份原 ZIP 保持，升级本地布局时清理其对应的 12 个散装 JSONL，8 个旧隔离存档／设置文件按摘要复制。新版窗口自动识别本地副本已目检；另一台电脑安装与自然游玩尚未验收。

日常采集已统一为参与者流程；旧 `full_en_v1/game` 和 `local/runtime-playtest/game` 已退役清理，所在目录中的历史会话、数据库与报告保留。旧 AppData 采集目录经过存档对账和私有归档后清理，原版 `DELTARUNE` 存档保留。现用包与分享 ZIP 逐文件一致；核验、私有旧记录归档及可还原旧编译文件的增量在 `local/runtime-retirement/`，不随分享包分发。现有 r30 kit 与分享包保留，重新安装无需恢复旧开发副本。

最近自然试玩 `fa8dadbf517449daafedba99f4fa3b6e` 已收进 `local/runtime-library`：396 页／367 变体、51 次交互、5 次已确认选择、7 条完整 smallface；原始三流 1,514,504 字节、ZIP 81,981 字节，无截断／未关闭页／关联缺失，重复收包新增为 0。334 个实际来源 ID 涉及的 36 个源码文件摘要一致。396 页包含 339 个正文页、56 个纯控制页和 1 个三条 smallface 载体页；7 个未绑定页中只有 4 页是正文（战斗 ACT 局部变量、物品获得模板各 2 页）。其余 3 页为选择／结束控制页，不应作为未知角色台词计数。核验投影与逐页证据见 `local/runtime-playcheck-fa8d/{audit.json,review.html}`。

本次发现 6 个无头像正文页仍有全局头像候选：Tasque 气泡残留 Ralsei，拳击提示／回应残留 Queen。源码中 “Shut up!!” 与 “I said shut up!!” 的气泡锚点为 `su_actor`。旧读取器的 `face_code_evidence` 只是原始状态候选，不能直接用于已确认人物；revision 31 的审阅解释层已将这 6 页的无佐证候选降为待判断；旧变体与原始日志不改写。369 页使用快现，236 页采到头像，7 条插话均完整；本轮没有行内图片或文字运动样本，不能据此新增这些机制的自然验收结论。

数据保留：正文／来源、人物信号、贴图、字体／颜色／运动参数、插话与选择关系、交互对象快照属于核心证据。纯控制页用于连接来源与消息，不作为普通台词展示，尤其不能丢掉附属文本载体。耗时计数、绘制次数、瞬时相位／绝对坐标采样属于诊断，可在后续版本考虑缩减；本次不更改格式或删除旧记录。样式相位样本、smallface 绘制次数不参与变体签名，重复播放不会仅因这些诊断数值不同而新增变体。`capture_complete=false` 是现行格式固定的覆盖保留字段，并不表示运行失败；日志完整性须看独立的尾行／闭合／溢出检查。

`python -m tools.check` 已通过：108 项 Python 测试（其中运行时 44 项）及现有 JavaScript 检查。本次未修改网站产物，未重建或部署网站。本地布局版 ZIP 包含 1,024 个文件，约 26.9 MiB；另需约 849 MiB 的本地游戏副本空间。冻结 EXE 再次验证 14 页／4 次选择／4 条 smallface，原版存档摘要保持，本地两处 6 个 JSONL 在回读 ZIP 后清理，归档内原始三流完整。对应证据在 `local/runtime-layout-review/`。

## revision 31 编译与审阅契约

`tools.runtime.compile_kit` 接受 `--original`、`--code-root`、`--base-kit`、`--hp-patches`、`--cli`、`--out`，所有路径显式指定。只重编第二章，其他章节沿用已核验的隔离增量。编译输入摘要与来源新增记录在 `build.json`；旧 10,616 个 ID 不变，新增 48 个来源。重新编译不等于运行验收，必须验证实际分享包的 EXE 和游戏机制。

来源传播限定于同一块内、未重写的局部文本变量：支持本地化调用及完整三元分支，向 msgset/msgnext 传递独立来源标签；物品获得公共模板在返回时立即绑定本次调用。排除未加花括号的条件声明、嵌套函数、不明重写和任意文本拼接。模板的非标准自定义后缀保留来源未知。不会凭相同文本补配，也不会给历史缺失记录追填来源。

读取器为兼容历史包保持原始解释和变体签名。新消费者须通过 `tools.runtime.interpret.interpret` 得到版本为 `review-evidence-1` 的审阅投影，不能直接把 legacy identity 候选当已确认人物。实际头像只能支持候选；主动交互对象仍是独立线索。控制页默认隐藏，附属文本载体保留。

工作台只导出本次观察使用的素材帧，并核验原游戏与源码摘要。人工草稿绑定 session、partition、variant 和 occurrence，浏览器保存并可导出／导入 JSON；本版只编辑主消息，不自动回写归因库。插话、选择题、交互对象和源码证据可查看。旧采集、机制自测与自然游玩分开展示。

本机旧自然记录有 396 页，来源修复须在新的自然游玩继续验收；机制测试不能计为自然覆盖。浏览器自动操作因无法可靠识别当前 URL 而被工具中止，因此本版工作台仅完成生成、数据契约和脚本检查，尚未完成浏览器交互／视觉验收。

最终 r31 分享包已通过冻结 EXE 实测：来源夹具 8 页全部绑定（ACT 两种分支及 GlowWrist／FiberScarf 模板），源码断言标记通过；选择回归 14 页、4 次选择（3 次确认）、4 条 smallface，保留 1 个刻意构造的未知来源。原版存档摘要保持。工具检查通过 144 项 Python 测试及现有 JavaScript 检查；未重建网站。最终包 1,050 文件、28,240,209 字节，SHA-256 `ae546b212c3405c1bee96fca11ad2d96afc2165ceb62e2a2a968dae451ae02fe`。证据在 `local/runtime-validation/r31-final/`。

本地试用目录已由同一分享 ZIP 和冻结安装器升级到 r31，8 个存档／设置文件、3 个历史导出包逐文件一致。旧工具和元数据留在其 `_updates/previous-r30`，已移除可由旧 kit 重建的旧游戏副本。限时测试使用空白隔离进度，测试会话已另存开发证据，不混入玩家会话。新的 `local/runtime-review/r31-final/index.html` 包含 396 个旧自然页及 22 个机制页，共 105 张按需素材帧；自然覆盖数量不变。
