# 采集后核对工作台

打开生成目录中的 `index.html`。先选择自然游玩批次，默认隐藏纯控制页；机制自测只用于检查程序，不能当成玩家覆盖。

左侧搜索文本、key 或角色，按“优先核对”“来源未绑定”“头像缺少佐证”“主动交互”“smallface”“选择题”等筛选。右侧查看原始文本与阅读投影、头像／贴图、字体／颜色／运动参数、源码及附近实际消息。阅读投影不代表完整游戏渲染，附近消息不代表完整分支树。

两条证据分别展示：消息自身的来源、人物信号和实际素材；主动交互对象、当时贴图与引出的消息。与汽车交互不等于汽车说话，全局头像状态也可能残留。来源未知和角色待判断是两回事。

人工审阅先选择用途，再选择主名称或自填角色，写依据并保存草稿。当前表单只针对主消息；smallface 单独展示证据。草稿保存在当前浏览器，完成后务必“导出草稿 JSON”；换浏览器或移动页面时可重新导入。导入验证观察与变体绑定，不能将另一版本的判断直接套用。本版不自动合并到正式归因库。

维护者生成命令（项目根目录；输入均显式指定）：

```sh
python -m tools.runtime.review --bundle PATH_TO_CAPTURE_ZIP --sources PATH_TO_SOURCES_JSON --library local/runtime-library --out PATH_TO_NEW_REVIEW --code-root PATH_TO_MATCHED_GML --game PATH_TO_ORIGINAL_CH2_DATA_WIN --cli PATH_TO_UMT_CLI --characters PATH_TO_CHARACTER_CATALOG
```

可多次传入 `--bundle`，每个 session 只选一份当前包。旧来源库存须放在 `sources.json` 旁的 `inventories/<sha>.json`。素材仅导出本次引用帧，原版包摘要必须匹配；不用重新导出全游戏贴图。输出含游戏文本与素材，作为本地开发审阅材料，不随参与者工具公开分发。

旧记录不会因更新编译器而获得当时没有采到的来源。对照修复时应同时看旧自然记录与新机制／自然记录，区分“错误候选已撤下”和“身份已经证实”。

需要直观预览时，可在此审核产物上另建[本地还原试验台](RESTORE_LOCAL.md)。它生成独立的 `index.html` 与带共用预览的 `review.html`，保持当前审核产物和默认生成器不变。首版布局／字体明确标为近似，不能代替游戏画面验收。
