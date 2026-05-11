# Prompts 调优目录

此目录存放"诗境 Agent"所有节点的 Prompt，与代码解耦，无需修改 Python 文件即可调整 Agent 行为。

## 目录结构

```
prompts/
├── system/
│   └── main_agent.md              ← 云端路径全局人设与行为规则（GLM/Doubao 专用）
├── planner/
│   ├── local_tool_plan.md         ← 本地路径规划 prompt（含诗境身份 + JSON 工具调度，Ollama 专用）
│   └── intent_router.md           ← 意图分类（预留，暂未接入主流程）
├── chains/
│   └── visualize/
│       ├── 01_retrieve.md         ← RAG 检索结果整理
│       ├── 02_split_scenes.md     ← 场景拆分 + 提示词增强（一体化，所有生图路径通用）
│       ├── 03_storyboard.md       ← 分镜规划（/generate/storyboard 端点专用）
│       └── 04_video_super_prompt.md ← 视频超级提示词（generate_video 文生视频专用）
└── chat/
    ├── general.md                 ← 本地路径直接回答兜底（无工具结果时）
    ├── poetry_qa.md               ← 云端路径诗词问答专属追加段
    └── tool_result_answer.md      ← 本地路径工具结果总结兜底
```

## 如何调整

1. 直接编辑对应 `.md` 文件，保存后**重启 uvicorn** 即可生效（热加载版本见 TODO）
2. 文件内可使用 `{变量名}` 占位符，对应代码中的 `format_map()` 替换
3. 每个文件顶部有注释说明变量列表

## 优先级说明

- `system/main_agent.md`：定义 Agent 整体人设，对所有对话生效
- `planner/intent_router.md`：决定每条用户消息走哪条链路，调整此文件可以改变触发规则
- `chains/visualize/`：只在走可视化链路时生效，可分别单独优化单图、分镜和视频生成质量
- `chat/poetry_qa.md`：只在诗词问答时追加，用于引导回答结构
