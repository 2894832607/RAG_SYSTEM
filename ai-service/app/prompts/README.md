# Prompts 调优目录

此目录存放"诗境 Agent"所有节点的 Prompt，与代码解耦，无需修改 Python 文件即可调整 Agent 行为。

## 目录结构

```
prompts/
├── system/
│   └── main_agent.md          ← Agent 全局人设与行为规则（最重要）
├── planner/
│   └── intent_router.md       ← 意图分类指令（控制路由逻辑）
├── chains/
│   └── visualize/
│       ├── 01_retrieve.md     ← RAG 检索结果整理提示
│       ├── 02_enhance.md      ← SD 提示词增强指令
│       └── 03_generate.md     ← 图像生成前的确认提示（暂未启用）
└── chat/
    ├── poetry_qa.md           ← 诗词知识问答专属提示
    └── general.md             ← 通用对话兜底提示
```

## 如何调整

1. 直接编辑对应 `.md` 文件，保存后**重启 uvicorn** 即可生效（热加载版本见 TODO）
2. 文件内可使用 `{变量名}` 占位符，对应代码中的 `format_map()` 替换
3. 每个文件顶部有注释说明变量列表

## 优先级说明

- `system/main_agent.md`：定义 Agent 整体人设，对所有对话生效
- `planner/intent_router.md`：决定每条用户消息走哪条链路，调整此文件可以改变触发规则
- `chains/visualize/`：只在走可视化链路时生效，可单独优化图像生成质量
- `chat/poetry_qa.md`：只在诗词问答时追加，用于引导回答结构
