# 文本契约

## 输入与导入

`input/ch1..ch5/` 每章五份 JSON，文件名及准备方法见[构建说明](../build/README.md)。JSON 顶层为 `key → 字符串`：

- UTF-8，可带 BOM；拒绝重复 key、空 key、非字符串值及无效 JSON。
- 缺失翻译省略 key；空字符串保留。可选 `date` 是元数据，不能当成已确认的发布版本。
- 逐字保留正文、空格、换行、控制串；不按 key 前缀筛选。
- 全部 25 份输入校验通过后才写结果。manifest 记录相对路径、摘要和大小，不写机器路径或时间戳。

输出为 `build/texts/trilingual_chapterN.json` 及 `manifest.json`。每章 `lines` 按 key 排序，取五份语言表的 key 并集；字段为 `key`、`en`、`ja`、`zh_default`、`zh_names`、`zh_recruitable`。

缺失字段输出 `null`，缺失语言列表在 `missing`；不要拆分 `status` 推断语言名。`zh_variant` 比较现存中文值，`same` 不代表译文齐全。章节/key 是文本记录，不是某次源码用法；不在导入阶段跨章合并、判断冗余或推断角色。

## 网站数据

`tools.site.build_site_data` 核验输入 manifest，生成按章分包的 `build/site-data/`：

```json
{"schema":1,"chapter":1,"languages":["en","ja","zh_default","zh_names","zh_recruitable"],"strings":["YES","はい","是"],"source_files":[],"rows":[["key",0,1,2,2,2,[]]]}
```

`strings` 是同章字符串字典，`rows` 为 key 和五个字符串索引；缺失为 `null`。`web/text.js` 的 `decodeRow` 还原命名字段。源码转义、简洁文本和搜索投影由前端计算，不重复存入包。

可选源码位置包含 `source_files` 字典及每行第七项 `[[fileIndex,line],...]`。来源映射存于 `local/source-links/chN.json`，包含 `schema:1`、`chapter`、`files`、`by_key` 和绑定当前文本 manifest 的 `text_manifest_sha256`。位置仅用于 Wiki 跳转，不表示运行覆盖或角色归因。

## 显示与搜索

`web/text.js` 的 `format(raw, chapter)` 返回 `raw/source/plain/state/issues/tokens`。`raw` 不变；源码模式仅将换行、Tab 等转成可见转义；简洁模式按各章常见 writer 语法生成阅读投影：

- 隐藏已知显示控制串；未知或不完整片段保留并记入 `issues`。
- `&`、`#`、实际换行按换行处理，`|` 为空格，Tab 为四空格；反引号转义下一字符。
- 隐藏尾部结束标记，保留内部 `/`、`%` 及数字后的末尾百分号。
- `~N`、艺术字、图标、行内头像显示占位，数字仅为槽位；不猜动态值或资源身份。
- `missing`、`empty`、`control-only`、`text` 分开显示；只含控制串的记录不删除。

简洁规则无法覆盖所有消费者，字面符号歧义需用源码模式核对。行内头像不等于 smallface 独立消息。所有返回值按普通文本插入页面，不能直接当 HTML。

搜索覆盖 key、全部语言及原串／源码／简洁投影；显示语言和中文译法不限制搜索。中文智能对照仅在原串相同时合组；同 key 的不同章节分别展示。

复制本条包含 key 和所选语言。源码复制使用可见转义，简洁复制折为单行；单语言可选中复制。简洁模式句首星号使用悬挂缩进，不新增空格，也不改原文、搜索或复制内容。
