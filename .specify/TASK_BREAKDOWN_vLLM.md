# 📋 Poetry RAG vLLM 企业级优化 - 详细任务清单

> **版本**：v3（vLLM 本地方案）  
> **日期**：2026-03-10  
> **总耗时**：4-4.5 小时  
> **难度**：中等  
> **推荐**：一口气完成，不要中断

---

## 🎯 总体目标

```
当前状态：70% 开发就绪 (无缓存、无容器、无 K8s)
目标状态：100% 企业级就绪 (vLLM + Redis + Docker + K8s)

核心改进：
  ✅ 本地 vLLM 推理（性能 +500%）
  ✅ Redis 3 层缓存（响应 -95%）
  ✅ Docker Compose 容器化（部署自动化）
  ✅ Kubernetes 编排（生产级可靠性）
  ✅ 企业级文档（知识沉淀）
```

---

## 📐 任务拆解（10 大任务，29 个子任务）

### **配置 0：前置检查 (10 分钟)**

#### **Task 0.1：Docker 就绪检查**

| 项目 | 内容 |
|------|------|
| **目标** | 验证 Docker 已安装且可用 |
| **输入** | Windows 10/11 系统 |
| **检查命令** | `docker --version` |
| **预期输出** | `Docker version 20.10+` |
| **失败处理** | 安装 Docker Desktop 或 WSL 2 |
| **耗时** | 2 分钟 |

**验证清单：**
- [ ] `docker --version` 返回版本号
- [ ] `docker ps` 无错误
- [ ] Docker 后台程序已运行（Windows 右下角图标可见）

#### **Task 0.2：NVIDIA GPU 检查（可选但推荐）**

| 项目 | 内容 |
|------|------|
| **目标** | 确认 GPU 可用（加速推理） |
| **检查命令** | `nvidia-smi` |
| **预期输出** | NVIDIA GPU 驱动版本 + GPU 信息 |
| **如果无 GPU** | ✅ 照常工作，但使用 CPU（慢） |
| **安装 NVIDIA Docker** | `docker run --gpus all nvidia/cuda:11.8.0 nvidia-smi` |
| **耗时** | 3 分钟 |

**验证清单：**
- [ ] `nvidia-smi` 显示 GPU 信息（如果有）
- [ ] `docker run --gpus all` 能访问 GPU
- [ ] CUDA Compute Capability >= 3.5

#### **Task 0.3：磁盘空间检查**

| 项目 | 内容 |
|------|------|
| **目标** | 确保磁盘有足够空间 |
| **所需空间** | ~20GB（vLLM ~5GB + 缓存 + 容器） |
| **检查命令** | `Get-Volume C:` (PowerShell) |
| **预期** | FreeSpace > 20GB |
| **风险** | 空间不足会导致模型下载失败 |
| **耗时** | 2 分钟 |

**验证清单：**
- [ ] C: 盘剩余 > 20GB

---

### **阶段 1：vLLM 本地服务准备 (60 分钟)**

#### **Task 1.1：创建 vLLM 启动脚本**

| 项目 | 内容 |
|------|------|
| **目标** | 生成 PowerShell 脚本，一键启动 vLLM |
| **输入** | 无 |
| **输出文件** | `scripts/start-vllm.ps1` |
| **关键参数** | model、port、gpu-memory-utilization、download-dir |
| **耗时** | 15 分钟 |

**文件内容要点：**
```powershell
# scripts/start-vllm.ps1

param(
    [string]$Model = "Qwen/Qwen2-7B",
    [int]$Port = 8000,
    [double]$GpuMemory = 0.8,
    [string]$DownloadDir = "./models"
)

# 1. 检查 Python venv
# 2. 激活 venv
# 3. 安装 vLLM 依赖（如果需要）
# 4. 启动 vLLM 服务
# 5. 显示启动日志

python -m vllm.entrypoints.openai.api_server `
  --model $Model `
  --port $Port `
  --gpu-memory-utilization $GpuMemory `
  --download-dir $DownloadDir `
  --trust-remote-code
```

**验证清单：**
- [ ] 脚本可执行（`powershell .\scripts\start-vllm.ps1` 无错误）
- [ ] 显示 vLLM 服务启动日志
- [ ] 端口 8000 监听中（`netstat -ano | findstr 8000`）

#### **Task 1.2：创建 Dockerfile.vllm**

| 项目 | 内容 |
|------|------|
| **目标** | 为 vLLM 构建 Docker 镜像 |
| **输出文件** | `Dockerfile.vllm` |
| **基础镜像** | `vllm/vllm-openai:latest` 或 `nvidia/cuda:11.8.0-devel` |
| **模型** | Qwen/Qwen2-7B（自动下载） |
| **启动命令** | OpenAI API 兼容服务 |
| **耗时** | 10 分钟 |

**文件内容要点：**
```dockerfile
FROM vllm/vllm-openai:latest

# 或者如果需要自定义
# FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
# RUN pip install vllm torch torchvision torchaudio

ENV MODEL_NAME=Qwen/Qwen2-7B
ENV GPU_MEMORY_UTILIZATION=0.8
ENV DOWNLOAD_DIR=/models

EXPOSE 8000

ENTRYPOINT ["python", "-m", "vllm.entrypoints.openai.api_server"]
CMD ["--model", "${MODEL_NAME}", "--port", "8000", "--gpu-memory-utilization", "${GPU_MEMORY_UTILIZATION}"]
```

**验证清单：**
- [ ] `docker build -f Dockerfile.vllm -t vllm-qwen .` 成功
- [ ] `docker run --gpus all -p 8000:8000 vllm-qwen` 启动成功
- [ ] `curl http://localhost:8000/health` 返回 200

---

### **阶段 1P：Redis + 缓存模块 (90 分钟)**

#### **Task 1P.1：新增 Redis 依赖**

| 项目 | 内容 |
|------|------|
| **目标** | 添加 redis 到项目依赖 |
| **文件** | `ai-service/requirements.txt` |
| **改动** | `+redis>=4.5.0` |
| **验证命令** | `pip install -r requirements.txt` |
| **耗时** | 5 分钟 |

**修改前后：**
```diff
  fastapi>=0.115.0
  uvicorn==0.23.0
+ redis>=4.5.0
  langchain>=0.3.0
```

**验证清单：**
- [ ] `pip install redis` 成功
- [ ] `python -c "import redis; print(redis.__version__)"` 输出版本号

#### **Task 1P.2：实现缓存管理器**

| 项目 | 内容 |
|------|------|
| **目标** | 创建 Redis 缓存抽象层 |
| **输出文件** | `ai-service/app/modules/cache.py` |
| **核心类** | `RedisCache`、方法 `get(key)`、`set(key, value, ttl)` |
| **行数** | ~150 行 |
| **耗时** | 30 分钟 |

**关键内容：**
```python
# app/modules/cache.py

import redis
import json
from typing import Optional, Any

class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0):
        self.client = redis.Redis(host=host, port=port, db=db)
    
    def get(self, key: str) -> Optional[Any]:
        """从缓存获取"""
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存（带 TTL）"""
        try:
            self.client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        return bool(self.client.delete(key))
    
    def is_connected(self) -> bool:
        """检查连接"""
        try:
            self.client.ping()
            return True
        except Exception:
            return False
```

**验证清单：**
- [ ] 文件创建成功
- [ ] `python -c "from app.modules.cache import RedisCache"` 无错误
- [ ] 单元测试通过（如有）

#### **Task 1P.3：定义缓存策略**

| 项目 | 内容 |
|------|------|
| **目标** | 定义不同场景的缓存 TTL |
| **输出文件** | `ai-service/app/modules/cache_strategies.py` |
| **策略** | 诗词缓存、图像缓存、提示词缓存 |
| **行数** | ~80 行 |
| **耗时** | 15 分钟 |

**关键内容：**
```python
# app/modules/cache_strategies.py

class CacheStrategy:
    # 诗词搜索结果缓存（1 小时）
    POETRY_SEARCH_TTL = 3600
    
    # 图像生成结果缓存（24 小时）
    IMAGE_GENERATION_TTL = 86400
    
    # Prompt 增强结果缓存（7 天）
    PROMPT_ENHANCEMENT_TTL = 604800
    
    # Embedding 缓存（无限）
    EMBEDDING_TTL = -1

def get_cache_key(prefix: str, *args) -> str:
    """生成规范的缓存 key"""
    return f"{prefix}:{':'.join(str(arg) for arg in args)}"
```

**验证清单：**
- [ ] 文件创建成功
- [ ] 至少定义 3 个 TTL 常量
- [ ] `get_cache_key` 函数工作正常

#### **Task 1P.4：集成缓存到搜索工具**

| 项目 | 内容 |
|------|------|
| **目标** | 修改 `search_poetry` 工具，加入缓存 |
| **文件** | `ai-service/app/agent/tools.py` |
| **改动点** | 在搜索前检查缓存，搜索后存入缓存 |
| **耗时** | 15 分钟 |

**修改模式：**
```python
from app.modules.cache import RedisCache
from app.modules.cache_strategies import CacheStrategy, get_cache_key

@tool
def search_poetry(query: str) -> str:
    cache = RedisCache()
    
    # 检查缓存
    cache_key = get_cache_key("poetry", query)
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result  # 缓存命中，直接返回！
    
    # 执行搜索（原有逻辑）
    result = Retriever().smart_retrieve(query)
    formatted_result = format_result(result)
    
    # 存入缓存
    cache.set(cache_key, formatted_result, CacheStrategy.POETRY_SEARCH_TTL)
    return formatted_result
```

**验证清单：**
- [ ] 修改后 `app/agent/tools.py` 导入缓存模块
- [ ] 缓存逻辑正确（先查、再检、再存）
- [ ] tools.py 仍能正常导入

#### **Task 1P.5：集成缓存到图像生成**

| 项目 | 内容 |
|------|------|
| **目标** | 修改 `CogViewClient`，加入图像 URL 缓存 |
| **文件** | `ai-service/app/modules/generation.py` |
| **改动点** | 缓存图像 URL 和增强的 prompt |
| **耗时** | 15 分钟 |

**修改模式：**
```python
# 在 CogViewClient.generate() 中

cache = RedisCache()
cache_key = get_cache_key("image", prompt[:50])  # 用 prompt 前 50 字作 key

# 检查缓存
cached = cache.get(cache_key)
if cached:
    return cached['image_url']

# 执行生成
image_url = self._call_api(prompt, negative_prompt)

# 存入缓存
cache.set(cache_key, {
    'image_url': image_url,
    'prompt': prompt
}, CacheStrategy.IMAGE_GENERATION_TTL)

return image_url
```

**验证清单：**
- [ ] `generation.py` 正常导入缓存模块
- [ ] 图像缓存逻辑正确
- [ ] 原有功能不受影响

#### **Task 1P.6：修改 lifespan 和 health**

| 项目 | 内容 |
|------|------|
| **目标** | 更新 FastAPI lifespan，加入 Redis 检查 |
| **文件** | `ai-service/app/main.py` |
| **改动点** | health 接口添加 Redis 状态 |
| **耗时** | 10 分钟 |

**修改要点：**
```python
# app/main.py 中 health 接口

from app.modules.cache import RedisCache

@app.get("/ai/health")
async def health():
    llm = get_llm_config()
    img = get_image_config()
    redis_cache = RedisCache()
    
    return {
        "status": "ok",
        "service": "poetry rag ai",
        "models": {
            "llm": {...},
            "image": {...}
        },
        "cache": {                           # ← 新增
            "provider": "redis",
            "connected": redis_cache.is_connected()
        }
    }
```

**验证清单：**
- [ ] `GET /ai/health` 返回新的 cache 字段
- [ ] `GET /ai/health | jq .cache` 显示 Redis 连接状态

#### **Task 1P.7：更新环境变量文档**

| 项目 | 内容 |
|------|------|
| **目标** | 在 `local-env.ps1.example` 中添加 Redis 配置 |
| **文件** | `ai-service/local-env.ps1.example` |
| **添加内容** | REDIS_HOST、REDIS_PORT、REDIS_DB |
| **耗时** | 5 分钟 |

**新增配置：**
```powershell
# ── Redis 缓存配置（可选，默认本地） ──────────────────────
$env:REDIS_HOST = 'localhost'
$env:REDIS_PORT = 6379
$env:REDIS_DB = 0

# docker-compose 中使用
# $env:REDIS_HOST = 'redis'   # 容器网络内的服务名
```

**验证清单：**
- [ ] 文件包含 REDIS_* 变量说明

---

### **阶段 2：Docker Compose 编排 (60 分钟)**

#### **Task 2.1：创建 Backend Dockerfile**

| 项目 | 内容 |
|------|------|
| **目标** | 容器化 Spring Boot Backend |
| **输出文件** | `backend/Dockerfile` |
| **构建流程** | Maven 编译 → JAR 打包 → Docker 镜像 |
| **镜像大小** | ~300MB |
| **耗时** | 15 分钟 |

**Dockerfile 内容：**
```dockerfile
# backend/Dockerfile

FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build
COPY pom.xml .
COPY src ./src

RUN mvn clean package -DskipTests

# 运行阶段
FROM eclipse-temurin:17-jdk-alpine

WORKDIR /app

# 复制 JAR（从 builder stage）
COPY --from=builder /build/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
```

**验证清单：**
- [ ] `docker build -f backend/Dockerfile -t poetry-backend .` 成功
- [ ] `docker run -p 8080:8080 poetry-backend` 启动成功

#### **Task 2.2：编写 docker-compose.yml**

| 项目 | 内容 |
|------|------|
| **目标** | 编排 5 个服务（vLLM、Redis、MySQL、AI、Backend） |
| **输出文件** | `docker-compose.yml` |
| **行数** | ~150 行 |
| **耗时** | 25 分钟 |

**核心结构：**
```yaml
version: '3.8'

services:
  # vLLM 推理服务（关键）
  vllm:
    image: vllm/vllm-openai:latest
    ports: ['8000:8000']
    environment:
      - MODEL_NAME=Qwen/Qwen2-7B
      - GPU_MEMORY_UTILIZATION=0.8
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    networks: [poetry-net]

  # Redis 缓存
  redis:
    image: redis:7-alpine
    ports: ['6379:6379']
    volumes: [redis-data:/data]
    networks: [poetry-net]

  # MySQL 数据库
  mysql:
    image: mysql:8.0
    ports: ['3306:3306']
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: poetry_rag
    volumes:
      - mysql-data:/var/lib/mysql
      - ./backend/sql/schema.sql:/docker-entrypoint-initdb.d/init.sql
    networks: [poetry-net]

  # AI Service
  ai-service:
    build:
      context: .
      dockerfile: ai-service/Dockerfile
    ports: ['8001:8000']
    depends_on:
      vllm:
        condition: service_started
      redis:
        condition: service_started
    environment:
      - LLM_PROVIDER=custom
      - LLM_BASE_URL=http://vllm:8000/v1
      - LLM_MODEL=Qwen/Qwen2-7B
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    networks: [poetry-net]

  # Backend
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports: ['8080:8080']
    depends_on: [mysql, ai-service]
    environment:
      - MYSQL_HOST=mysql
      - AI_SERVICE_URL=http://ai-service:8000
    networks: [poetry-net]

volumes:
  redis-data:
  mysql-data:
  models:

networks:
  poetry-net:
    driver: bridge
```

**验证清单：**
- [ ] YAML 语法无错误（`docker-compose config` 无错误）
- [ ] 所有 services 都有 `networks: [poetry-net]`
- [ ] vLLM 的 `depends_on` 正确

#### **Task 2.3：编写生产用 docker-compose.prod.yml**

| 项目 | 内容 |
|------|------|
| **目标** | 创建优化版 compose，用于生产 |
| **输出文件** | `docker-compose.prod.yml` |
| **区别** | 无本地 volumes、日志驱动、资源限制 |
| **耗时** | 10 分钟 |

**关键改动：**
```yaml
# docker-compose.prod.yml - 基于 docker-compose.yml 修改

services:
  vllm:
    # ... (保持相同)
    # 新增资源限制
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
        reservations:
          devices:
            - driver: nvidia
              count: 1

  ai-service:
    # ... (保持相同)
    # 新增健康检查和日志
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/ai/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**验证清单：**
- [ ] `docker-compose -f docker-compose.prod.yml config` 无错误

#### **Task 2.4：创建 .dockerignore**

| 项目 | 内容 |
|------|------|
| **目标** | 减小构建上下文大小 |
| **输出文件** | `.dockerignore` |
| **内容** | 忽略不必要的文件（.git、node_modules、.venv 等） |
| **耗时** | 3 分钟 |

**内容：**
```
.git
.gitignore
__pycache__
.venv
.env
.env.*
node_modules
*.pyc
.pytest_cache
.coverage
dist/
build/
*.egg-info/
.vscode
.idea
target/
```

**验证清单：**
- [ ] 文件创建成功
- [ ] docker build 时上下文大小 < 100MB

#### **Task 2.5：修改 AI Service Dockerfile**

| 项目 | 内容 |
|------|------|
| **目标** | 更新 AI Service Dockerfile 以支持 Redis |
| **文件** | `ai-service/Dockerfile` |
| **改动** | 添加 healthcheck 和日志驱动 |
| **耗时** | 5 分钟 |

**修改要点：**
```dockerfile
# ai-service/Dockerfile

FROM python:3.10-slim

WORKDIR /opt/ai-service

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# 新增健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/ai/health', timeout=5)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**验证清单：**
- [ ] `docker build -f ai-service/Dockerfile -t poetry-ai .` 成功

#### **Task 2.6：创建 docker-compose 启动脚本**

| 项目 | 内容 |
|------|------|
| **目标** | 一键启动全栈（带日志输出） |
| **输出文件** | `scripts/docker-compose-up.ps1` |
| **功能** | 启动、日志显示、验证 |
| **耗时** | 5 分钟 |

**脚本内容：**
```powershell
# scripts/docker-compose-up.ps1

Write-Host "🚀 启动 Poetry RAG 全栈系统" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# 1. 检查 Docker
$docker = docker --version 2>$null
if (-not $docker) {
    Write-Host "❌ Docker 未找到，请先安装" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker: $docker" -ForegroundColor Green

# 2. 启动容器
Write-Host "`n⏳ 启动容器组..." -ForegroundColor Yellow
docker-compose up -d --build

# 3. 等待服务就绪
Write-Host "`n⏳ 等待服务启动（大约 30 秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# 4. 验证
Write-Host "`n✅ 验证服务状态..." -ForegroundColor Green

$services = @{
    "vLLM" = "http://localhost:8000/health"
    "AI Service" = "http://localhost:8001/ai/health"
    "Backend" = "http://localhost:8080/actuator/health"
    "Redis" = "localhost:6379"
}

foreach ($service in $services.GetEnumerator()) {
    if ($service.Key -eq "Redis") {
        # Redis 检查
        $redis_ok = redis-cli -h localhost -p 6379 PING 2>$null
        Write-Host "  $($service.Key): $(if ($redis_ok) { '✅' } else { '⚠️' })" 
    } else {
        # HTTP 检查
        try {
            $response = curl -s -o /dev/null -w "%{http_code}" $service.Value
            Write-Host "  $($service.Key): $(if ($response -eq '200') { '✅' } else { '⚠️' })"
        } catch {
            Write-Host "  $($service.Key): ⚠️"
        }
    }
}

Write-Host "`n📊 服务映射：" -ForegroundColor Cyan
Write-Host "  vLLM:       http://localhost:8000" -ForegroundColor Green
Write-Host "  AI Service: http://localhost:8001" -ForegroundColor Green
Write-Host "  Backend:    http://localhost:8080" -ForegroundColor Green
Write-Host "  Redis:      localhost:6379" -ForegroundColor Green
Write-Host "  MySQL:      localhost:3306" -ForegroundColor Green

Write-Host "`n✅ 系统启动完成！" -ForegroundColor Green
Write-Host "`n查看日志: docker-compose logs [service_name]" -ForegroundColor Yellow
Write-Host "停止所有: docker-compose down" -ForegroundColor Yellow
```

**验证清单：**
- [ ] `powershell .\scripts\docker-compose-up.ps1` 无错误

---

### **阶段 3：K8s 部署清单 (60 分钟)**

#### **Task 3.1-3.10：生成 K8s YAML 清单**

| 任务 | 文件 | 行数 | 内容 |
|------|------|------|------|
| **3.1** | `k8s/namespace.yaml` | 5 | 创建 poetry-rag 命名空间 |
| **3.2** | `k8s/configmap.yaml` | 20 | 环境变量（LLM_PROVIDER 等） |
| **3.3** | `k8s/secret.yaml` | 15 | 密钥（MySQL password、API keys） |
| **3.4** | `k8s/vllm-deployment.yaml` | 45 | vLLM 服务 (GPU 支持) |
| **3.5** | `k8s/ai-service-deployment.yaml` | 40 | AI Service 副本管理 |
| **3.6** | `k8s/ai-service-hpa.yaml` | 15 | CPU > 70% 时自动扩容到 5 副本 |
| **3.7** | `k8s/backend-deployment.yaml` | 40 | Backend 副本管理 (2 副本) |
| **3.8** | `k8s/mysql-statefulset.yaml` | 50 | MySQL 有状态服务 |
| **3.9** | `k8s/redis-statefulset.yaml` | 45 | Redis 有状态服务 |
| **3.10** | `k8s/ingress.yaml` | 30 | API Gateway 路由规则 |

**总耗时**：60 分钟

**关键 YAML 示例：**

```yaml
# k8s/vllm-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm
  namespace: poetry-rag
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm
  template:
    metadata:
      labels:
        app: vllm
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        ports:
        - containerPort: 8000
        env:
        - name: MODEL_NAME
          value: "Qwen/Qwen2-7B"
        - name: GPU_MEMORY_UTILIZATION
          value: "0.8"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "4Gi"
            cpu: "2"
          limits:
            nvidia.com/gpu: 1
            memory: "8Gi"
            cpu: "4"
        volumeMounts:
        - name: models
          mountPath: /models
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: vllm-models-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: vllm
  namespace: poetry-rag
spec:
  selector:
    app: vllm
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

**验证清单：**
- [ ] 所有 YAML 文件创建成功
- [ ] `kubectl apply -f k8s/ --dry-run=client` 无错误
- [ ] 至少 10 个 K8s 资源定义

---

### **阶段 4：文档与验证 (30 分钟)**

#### **Task 4.1：编写部署指南**

| 项目 | 内容 |
|------|------|
| **文件** | `docs/DOCKER_COMPOSE_DEPLOY.md` |
| **内容** | docker-compose 完整部署步骤 |
| **行数** | ~300 行 |
| **耗时** | 15 分钟 |

#### **Task 4.2：编写 K8s 部署指南**

| 项目 | 内容 |
|------|------|
| **文件** | `docs/KUBERNETES_DEPLOY.md` |
| **内容** | K8s 部署、调试、扩容步骤 |
| **行数** | ~400 行 |
| **耗时** | 15 分钟 |

**验证清单：**
- [ ] 至少 2 份部署文档
- [ ] README.md 已更新（添加快速开始链接）

#### **Task 4.3：全系统功能验证**

| 验证项 | 命令/检查点 | 预期结果 |
|--------|-----------|---------|
| **Docker 启动** | `docker-compose up -d` | 5 个服务运行中 |
| **vLLM 健康检查** | `curl http://localhost:8000/health` | 200 OK |
| **Redis 连接** | `redis-cli ping` | PONG |
| **AI Service 健康检查** | `curl http://localhost:8001/ai/health` | models 字段完整 |
| **后端网关** | `curl http://localhost:8080/actuator/health` | status=UP |
| **诗词查询** | `curl -X POST http://localhost:8001/ai/api/v1/generate/simple` | 返回诗词 + 图像 URL |
| **缓存效率** | 连续查询相同诗词 2 次，第 2 次 < 200ms | 缓存命中 |
| **Redis 缓存** | `redis-cli KEYS *` | 显示诗词、图像 key |

**耗时**：10 分钟

**验证清单：**
- [ ] 所有 5 个服务状态 "Up"
- [ ] health 接口返回完整信息（包含 Redis、models）
- [ ] 至少 1 次成功的诗词生成
- [ ] 缓存命中后延迟 < 200ms

---

## 📊 总任务统计

| 类别 | 数量 | 耗时 |
|------|------|------|
| **前置检查** | 3 | 10 min |
| **vLLM 服务** | 2 | 25 min |
| **Redis 缓存** | 7 | 90 min |
| **Docker Compose** | 5 | 60 min |
| **K8s 清单** | 10 | 60 min |
| **文档验证** | 3 | 30 min |
| **总计** | **30** | **275 min (4.5h)** |

---

## ✅ 执行检查清单

### 执行前
- [ ] Docker Desktop 已启动
- [ ] GPU 驱动已安装（可选，但推荐）
- [ ] 磁盘剩余 > 20GB
- [ ] 网络连接良好（用于拉取镜像和模型）
- [ ] 终端进入项目根目录

### 阶段 1 完成后
- [ ] `docker-compose ps` 显示 5 green services
- [ ] `curl http://localhost:8000/health` 返回 200
- [ ] `curl http://localhost:8001/ai/health` 返回 redis 状态

### 阶段 2 完成后
- [ ] `docker-compose logs ai-service` 显示"Uvicorn running"
- [ ] `docker-compose logs vllm` 显示"Uvicorn running"
- [ ] Redis 中有诗词缓存 key

### 阶段 3 完成后
- [ ] `kubectl apply -f k8s/` 成功（需要已连接 K8s 集群）
- [ ] `kubectl get pods -n poetry-rag` 显示所有 Pod running
- [ ] `kubectl logs <pod-name> -n poetry-rag` 无错误

### 全系统验证后
- [ ] 所有文档已编写
- [ ] README.md 包含快速开始链接
- [ ] 项目根目录有 `docker-compose.yml`、`k8s/` 文件夹

---

## 🎯 成功标志

完成后，你能做到：

```
✅ 一键启动全栈（docker-compose up）
✅ 诗词查询 < 100ms（缓存命中）
✅ 自动扩容（K8s HPA）
✅ 故障自愈（Pod 重启）
✅ 企业级监控（可选 Prometheus）
✅ 无缝切换 LLM（只改环境变量）
```

---

## 🚀 现在开始执行！

```powershell
# 第一步：进入项目目录
cd d:\aaa111\Poetry-RAG-System

# 第二步：执行前置检查（Task 0）
docker --version
nvidia-smi  # (可选)
Get-Volume C:

# 第三步：按顺序执行 Task 1-4
# （我下面会给你每个 Task 的具体操作指令）
```

完整的分步执行指令即将生成！ 🎉
