# 上下文契约

上下文是同文件文本引用、局部选项和条件分支的静态结构。当前为测试版，不是完整执行图，也不提供运行时角色或样式归因。

## 输入与产物

输入为与语言表版本对应的 GML 根目录，含 `ch1..ch5/`，每章直接放 `.gml` 文件；使用者自行通过 UMT 反编译。构建与验证命令见[构建说明](../build/README.md)。

`local/context-all/` 包含：

| 文件 | 内容 |
|---|---|
| `contexts.json` | schema 2 目录与文本 manifest 摘要 |
| `index-chN.json` | 章节文件清单和 key 到文件的索引 |
| `files/<id>.json` | 每个源码文件的结构及消息引用，按需加载 |
| `evidence.json` | 源码及输出摘要、大小和统计 |

网站装配核验绑定和每个分包的摘要、大小、身份与索引覆盖；过期或损坏的包会报错。修改语言表或 GML 后应重新生成并验证，不手改结果。

## 用法与关系

- 同 key 的不同引用保留独立 `occurrence_id`、文件、行号和文本绑定。
- 身份中的 `data/exported/code/chN/...` 是逻辑命名空间，不是磁盘路径；移动输入目录不改变身份，变更反编译格式可能改变身份。
- 消息节点类型为 `message`；容器为 `sequence/block/blocks`；分支为 `choice/condition`，端点为 `end/join`。
- 无法确定的动态调用、消费关系、分支连接保留未知或独立块，不猜顺序、汇合或全局路线。
- 无源码引用的语言表项仍保留。没有引用不证明不可达；没有运行记录也不证明分支不存在。

局部排查可运行 `python -m tools.context.context_files --code "PATH_TO_GML" --file ch4/gml_Object_obj_ch4_DCC03_Step_0.gml --out build/context-file-check`，再运行 `python -m tools.context.verify_context_files --code "PATH_TO_GML" --out build/context-file-check`。替换 GML 路径和文件名；`--file` 相对于 GML 根目录。局部输出不替换现有全量包。
