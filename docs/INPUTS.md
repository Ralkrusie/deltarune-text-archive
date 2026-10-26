# 文本输入与输出契约 v1

## 输入

入口是一个目录，固定处理 ch1..ch5，每章必须有五个文件。当前不自动猜测章节、文件名或语言，不使用游戏路径配置或隐式旧项目路径。

| 文件 | 输出字段 | 含义 |
|---|---|---|
| lang_en.json | en | 英文 |
| lang_ja.json | ja | 日文 |
| lang_zh.json | zh_default | 默认中文 |
| lang_zh_names.json | zh_names | 中文 names 版本 |
| lang_zh_recruitable.json | zh_recruitable | 中文 recruitable 版本 |

文件内容为 JSON 对象，key 必须非空，值必须是字符串；缺失翻译应省略该 key。`null`、数字、布尔、嵌套对象、重复 JSON key、无效 UTF-8／JSON 均报错。空字符串是有效原文。JSON 文档的 `date` 字段仅为元数据，可省略；不能拿它当已确认的游戏／补丁发布版本。

UTF-8 BOM 可读。控制字符转义按 JSON 标准解码，原文不修剪空格、不统一换行、不替换字符、不去除控制串。不根据 key 前缀过滤台词。目录中的其他文件不作为语言输入。

25 份文件全部解析验证成功后才写结果；输入验证失败不会改写上一次输出。该保证不包括磁盘写入过程中断电或空间不足等 I/O 故障；manifest 最后写入，可据其摘要核对产物是否完整。复制准备工具要求目标目录不存在，避免覆盖已有快照。

## 输出

每章一个 `trilingual_chapterN.json`：

```json
{
  "schema": 1,
  "chapter": 1,
  "stats": {
    "total": 1,
    "complete": 0,
    "missing_by_language": {"en": 0, "ja": 1, "zh_default": 0, "zh_names": 0, "zh_recruitable": 0},
    "zh_differs": 0
  },
  "lines": [{
    "key": "synthetic_example",
    "en": "* Example./",
    "ja": null,
    "zh_default": "* 合成示例。/",
    "zh_names": "* 合成示例。/",
    "zh_recruitable": "* 合成示例。/",
    "missing": ["ja"],
    "status": "missing_ja",
    "zh_variant": "same"
  }]
}
```

- key 库存取五档语言并集，按 key 排序；缺失语言输出 null，空字符串仍为空字符串。
- 每章独立，不做跨章 key 合并、冗余隐藏或说话人推断。总数是章节/key 数，不是去重台词数，也不是 occurrence 数。
- `missing` 是缺失字段名数组；`status` 保留旧对齐格式便于对账，下游应读数组，不以 `_` 拆分语言字段。
- `zh_variant` 只比较已存在的中文值；不一致为 differs，否则 same。same 不代表三个版本齐全，完整性看 missing。
- 统计直接从结果字段计算。旧实现通过拆 status 统计缺失中文会拆坏 `zh_default` 等名称；这里按语言分别计数，不继承该聚合统计错误。正文及每行对齐语义保持。
- manifest 的输入摘要标识这批文本，记录输入 date 但不虚构上游版本号；正文没有反复复制摘要。发生补丁更新时重新导入并比较 key/字段。
- manifest 不包含构建时间或机器绝对路径，相同文件字节得到相同产物。单纯 JSON 缩进变化可能改变输入摘要，不代表正文变化。

当前输出是研究／构建用文本中间产物，不是最终网站分包格式。不包含代码位置、运行观察或人工结论；后续用章节/key 关联用法库存，不能把每条文本当成唯一一次出现。

可选复制工具的来源记录在项目 local/ 中，默认文件名为 <输出目录名>-provenance.json；输入根目录只需 ch1..ch5。该记录含本机路径，不属于共享输入或网站数据。
