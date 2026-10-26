# 上下文生成与验证

上下文由本项目内的静态解析工具生成，不需要安装旧项目。它组织同文件的文本引用、可识别的选项和局部条件关系，不是完整游戏执行图，也不包含运行时说话人归因。

## 输入与命令

Python 3.10+，仅标准库。先按 [README](../README.md) 导入语言表，再准备与文本版本相符的反编译 GML 根目录：包含 `ch1` 至 `ch5`，每章直接放 `.gml` 文件。工具不负责反编译游戏。

```sh
python tools/build_context_all.py --code /path/to/code --texts build/texts --out local/context-all
python tools/verify_context_all.py --code /path/to/code --texts build/texts --out local/context-all --report build/context-verification.json
python tools/build_site.py
```

`--code` 必填；不指定时直接报错，不回退读取旧项目。`--texts` 默认 `build/texts`，`--out` 默认 `local/context-all`。Windows 路径含空格时需加引号。仅做验证性构建时使用独立输出目录，避免覆盖正在使用的上下文包。

局部文件分析：

```sh
python tools/context_files.py --code /path/to/code --file ch4/gml_Object_obj_ch4_DCC03_Step_0.gml --out build/context-file-check
python tools/verify_context_files.py --code /path/to/code --out build/context-file-check
```

正式网站优先消费 `local/context-all`，没有全量包时兼容 `local/context-files` 试点包。局部研究不会替换已存在的全量包。更换语言表或源码快照后，应重新生成和验证上下文。

## 身份与证据

`tools/context_parser/` 包含必要的语法、调用位置和 occurrence 身份函数；迁移来源摘要与保留符号见 [SOURCES.json](../tools/context_parser/SOURCES.json)。这些来源记录用于追溯，不是运行时依赖。

occurrence 身份中的 `data/exported/code/chN/...` 是稳定的逻辑命名空间，不要求机器上存在这个路径。移动实际源码目录不会改变身份；更换反编译输出格式可能改变行号、偏移与身份，需要重新核对。

验证器检查源码摘要、调用位置、原文差异、缺失 key 和 occurrence 身份。可用 `--prior /path/to/contexts.json` 对比历史试点；不传则不读取历史包。全量验证器的历史对比针对原两个局部回归文件，不是任意旧包合并接口。

## 能力边界

- 同 key 的不同源码引用保留为不同 occurrence，不合并不同用法。
- 无源码引用的文本保留并提示；这不证明它是冗余文本或游戏不可达。
- 无法确定的动态关系、消息消费和分支连接保留未知或独立块，不补猜测的顺序和汇合。
- 当前上下文不替代运行时属性采集、人工归因，也不负责全局路径求解。
- 旧 C1/C2 研究命令不属于公开管线；当前使用上面的全量与局部入口。

独立化回归曾验证五章输出与迁移前一致（不比较耗时），并在没有相邻旧项目的临时目录完成生成和测试。当前数据规模及本轮验证结果以状态记录和实际构建报告为准，不在此维护历史计数。
