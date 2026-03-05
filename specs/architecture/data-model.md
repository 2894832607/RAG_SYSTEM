# 数据模型规范

> **Status**: Stable  
> **Version**: 1.0  
> **Last Updated**: 2026-03-05

---

## 1. MySQL 数据库：`poetry_rag`

### 1.1 `sys_generation_task`（任务主表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 自增主键 |
| `task_id` | VARCHAR(64) | NOT NULL, UNIQUE | 业务 UUID，对外暴露 |
| `original_poem` | TEXT | NOT NULL | 原始诗句 |
| `retrieved_text` | TEXT | NULL | RAG 检索到的诗文 |
| `enhanced_prompt` | TEXT | NULL | GLM 增强后的 Prompt |
| `result_image_url` | VARCHAR(512) | NULL | 生成图像 URL |
| `task_status` | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING' | 任务状态 |
| `error_message` | TEXT | NULL | 失败原因 |
| `create_time` | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| `update_time` | DATETIME | NOT NULL | 最后更新时间 |
| `user_id` | BIGINT | NULL, FK→sys_user.id | 所属用户（可选）|

**状态枚举**

```
PENDING     → 已提交，等待 AI 处理
PROCESSING  → AI 服务已接收，处理中
COMPLETED   → 成功，imageUrl 非空
FAILED      → 失败，errorMessage 非空
```

**索引**
- `UK_task_id` UNIQUE 索引 on `task_id`
- `IDX_status` on `task_status`（支持状态过滤查询）
- `IDX_user_id` on `user_id`（支持用户任务列表）

---

### 1.2 `sys_user`（用户表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT | |
| `username` | VARCHAR(64) | NOT NULL, UNIQUE | 登录名 |
| `password` | VARCHAR(255) | NOT NULL | BCrypt 哈希 |
| `create_time` | DATETIME | NOT NULL, DEFAULT NOW() | |

---

## 2. ChromaDB 向量库

| 项目 | 值 |
|------|-----|
| Collection | `poetry` |
| 本地路径 | `ai-service/data/chromadb/` |
| 数据集 | `gushiwen_cleaned.jsonl`（约 N 条诗文） |
| Embedding | GLM Embedding / SentenceTransformer |
| 距离函数 | cosine |

### 文档 Metadata Schema

```json
{
  "id": "唯一标识",
  "title": "诗名",
  "author": "作者",
  "dynasty": "朝代",
  "content": "正文"
}
```

---

## 3. Few-shot 示例（`data/fewshot_examples.json`）

```jsonc
[
  {
    "input": "床前明月光，疑是地上霜",
    "output": "A moonlit bedroom, soft silver light on the floor, ancient Chinese architecture, ink painting style..."
  }
  // ... 更多示例
]
```

---

## 4. 任务状态机

```
               ┌──────────┐
    提交        │  PENDING  │
   ──────────▶  └────┬─────┘
                     │ AI 服务接收
                     ▼
               ┌──────────────┐
               │  PROCESSING  │
               └──────┬───────┘
              成功 ▼         ▼ 失败
         ┌──────────┐   ┌──────────┐
         │COMPLETED │   │  FAILED  │
         └──────────┘   └──────────┘
```
