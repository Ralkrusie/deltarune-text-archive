# DELTARUNE Text Archive · 真实台词示例

五章各选 8 条，共 40 条；直接摘自当前统一输入，保留原始 key、三语正文、三个中文版本及控制串，不编造人物、台词或缺失翻译。游戏版本 v0.0.253（2026-07-31），中文为好人汉化组 V261024。来源文件摘要及选取 key 见 [source.json](source.json)，不含本机绝对路径。

语言表收录不等于已经验证正常游玩可达性。文本及译文属于原作者／译者，不属于本项目原创示例；此目录只提供节选，不包含完整语言表。

需要 Python 3.10+，运行检查另需 Node.js 18+，无第三方 Python 包依赖。在项目根目录执行：

```sh
python tools/check_demo.py
python -m http.server 8801 --bind 127.0.0.1 --directory build/open-source-demo
```

打开 http://127.0.0.1:8801/ 。需使用 HTTP，不要双击 HTML。构建只读取 examples/input 和网页源码，不依赖完整游戏目录或旧项目，不覆盖正式 dist。

## 可查看的真实例子

- 第 1 章 `obj_alphysalley_event_slash_Step_0_gml_25_0`：Alphys 台词，检查中文人名译法和源码／简洁模式。
- 第 1 章 `obj_readable_room1_slash_Other_10_gml_17_0`：床下 CD 的调查文本，检查 `^1`、`&` 等原始控制串和换行。
- 第 2–5 章 `obj_treasure_room_slash_Other_10_gml_76_0`：宝箱文本，原文包含 `\cY`、`\cW` 和 `~1`／`~2`，动态参数仍显示占位，不伪造具体道具。
- 清空搜索：40 条记录、两页；章节分别保留，不因同 key 合并。

示例站复用当前网页，不加载游戏贴图、汉化字体、灵魂互动和上下文数据。JetBrains Mono NL 附有字体来源及 OFL，其他字符由系统字体补齐。示例不附源码位置映射；完整上下文需另外生成。

检查包括隔离构建、逐语言值对账、分页、检索与已有显示逻辑测试，不替代全量游戏数据和旧解析器验收。构建期间共享源码变化会明确报错；仅写 build/open-source-demo，目录中有意外文件时拒绝覆盖。
