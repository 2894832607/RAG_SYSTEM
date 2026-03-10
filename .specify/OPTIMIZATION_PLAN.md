# 📋 Poetry RAG 系统企业级优化计划

> **日期**：2026-03-10  
> **目标**：从开发环境升级至企业级部署（70% → 100%）  
> **总耗时**：3-4 小时  
> **难度**：中等

---

## 🎯 优化目标

| 当前状态 | 优化后 | 收益 |
|---------|---------|------|
| **性能** | 单个诗词 30s | 缓存命中 100ms | ✅ 30 倍性能提升 |
| **并发** | 支持 10 QPS | 支持 100+ QPS | ✅ 10 倍吞吐 |
| **可靠性** | 单 Pod | 3 副本 + 自愈 | ✅ 99.9% 可用性 |
| **部署** | 手动启动 | 一键 docker-compose | ✅ 0 配置体验 |
| **扩容** | 改代码 | 自动 HPA 扩容 | ✅ 智能资源管理 |
| **文档** | 无 | 企业级部署文档 | ✅ 知识沉淀 |

---

## 📐 阶段拆解

### **阶段 1：Redis 缓存层（1.5 小时）**

**目标**：减少重复 AI 调用，实现 3 层缓存策略

#### 新增文件
```
ai-service/
├── app/modules/
│   ├── cache.py                 ← 新建：缓存管理器
│   └── cache_strategies.py       ← 新建：缓存策略
├── requirements.txt             ← 修改：加入 redis
└── local-env.ps1.example        ← 修改：Redis 配置示例
```

#### 具体任务

| ID | 任务 | 文件 | 改动点 |
|----|----|------|--------|
| **1.1** | 新增 Redis 依赖 | `requirements.txt` | +redis>=4.5.0 |
| **1.2** | 实现缓存管理器 | `app/modules/cache.py` | 新建 RedisCache 类 |
| **1.3** | 定义缓存策略 | `app/modules/cache_strategies.py` | 3 种 TTL 配置 |
| **1.4** | 修改搜索工具 | `app/agent/tools.py` | 集成缓存 search_poetry |
| **1.5** | 修改图像生成 | `app/modules/generation.py` | 缓存图像 URL |
| **1.6** | 修改 lifespan | `app/main.py` | Redis 连接校验 + health |
| **1.7** | 更新环境配置 | `local-env.ps1.example` | REDIS_* 变量说明 |

#### 预期代码量
- `cache.py`：150 行
- `cache_strategies.py`：80 行
- 改动其他文件：~200 行

---

### **阶段 2：容器编排（1 小时）**

**目标**：本地开发一键启动（docker-compose），为生产部署铺路

#### 新增文件
```
根目录/
├── docker-compose.yml           ← 新建：3 容器编排
├── docker-compose.prod.yml      ← 新建：生产精简版
├── ai-service/
│   └── Dockerfile               ← 已有，不改
├── backend/
│   └── Dockerfile               ← 新建：Backend 容器化
└── .dockerignore                ← 新建：忽略文件列表
```

#### 具体任务

| ID | 任务 | 文件 | 内容 |
|----|----|------|------|
| **2.1** | 后端 Docker 化 | `backend/Dockerfile` | Spring Boot JAR 打包 |
| **2.2** | 编写 compose | `docker-compose.yml` | 4 服务编排 |
| **2.3** | 编写生产 compose | `docker-compose.prod.yml` | 优化版（无 volume） |
| **2.4** | 日志聚合配置 | `docker-compose.yml` | logging driver + loki |
| **2.5** | 健康检查 | `docker-compose.yml` | healthcheck 字段 |
| **2.6** | 网络隔离 | `docker-compose.yml` | 内部网络 + 端口映射 |

#### Services 结构
```
docker-compose.yml:
  ├─ mysql:8.0              (持久化存储)
  ├─ redis:7-alpine         (缓存层)
  ├─ ai-service:8000        (FastAPI + LangGraph)
  └─ backend:8080           (Spring Boot 网关)
  
  + networks: poetry-net (内网隔离)
  + volumes: mysql-data, redis-data (数据持久化)
```

---

### **阶段 3：K8s 部署清单（1 小时）**

**目标**：生产级 Kubernetes 部署方案（自动扩容、故障恢复）

#### 新增文件
```
k8s/
├── namespace.yaml               ← 命名空间隔离
├── configmap.yaml               ← 环配置 (models, llm provider)
├── secret.yaml                  ← 密钥 (API key, DB password)
├── redis/
│   ├── statefulset.yaml         ← Redis 有状态服务
│   └── service.yaml             ← Redis 内网暴露
├── ai-service/
│   ├── deployment.yaml          ← 副本管理
│   ├── service.yaml             ← Cluster IP
│   ├── hpa.yaml                 ← 自动扩容规则 (CPU > 70%)
│   └── pdb.yaml                 ← Pod 干扰预算 (至少 1 Pod 活)
├── backend/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── hpa.yaml
├── ingress.yaml                 ← API Gateway (Nginx/APISIX)
├── monitoring/
│   ├── prometheus-config.yaml   ← Prometheus 配置
│   └── grafana-dashboard.yaml   ← Grafana 仪表盘
└── kustomization.yaml           ← 多环境管理 (dev/staging/prod)
```

#### 具体任务

| ID | 任务 | 文件 | 关键参数 |
|----|----|------|---------|
| **3.1** | 命名空间 | `k8s/namespace.yaml` | poetry-rag |
| **3.2** | ConfigMap | `k8s/configmap.yaml` | LLM_PROVIDER、IMAGE_PROVIDER |
| **3.3** | Secret | `k8s/secret.yaml` | MySQL password、API keys |
| **3.4** | Redis SS | `k8s/redis/` | 1 副本（可扩展至 3） |
| **3.5** | AI-Service Deployment | `k8s/ai-service/deployment.yaml` | 初始 2 副本 |
| **3.6** | AI-Service HPA | `k8s/ai-service/hpa.yaml` | CPU 70% → 5 副本上限 |
| **3.7** | Backend Deployment | `k8s/backend/deployment.yaml` | 初始 2 副本 |
| **3.8** | Ingress | `k8s/ingress.yaml` | 路由规则：/api/* → backend, /ai/* → ai-service |
| **3.9** | PDB | `k8s/ai-service/pdb.yaml` | 故障转移保证 |
| **3.10** | Kustomization | `k8s/kustomization.yaml` | 多环境差异管理 |

#### 预期部署效果
```
kubectl apply -f k8s/

Result:
  namespace/poetry-rag created
  configmap/ai-config created
  secret/db-secret created
  
  statefulset.apps/redis created (1 ready)
  
  deployment.apps/ai-service created (2 ready)
  deployment.apps/backend created (2 ready)
  
  service/ai-service created (ClusterIP)
  service/backend created (ClusterIP)
  
  ingress.networkingk8s.io/poetry-ingress created
  
  hpa.autoscaling/ai-service-hpa created
  hpa.autoscaling/backend-hpa created
```

---

### **阶段 4：文档与验证（0.5 小时）**

**目标**：编写企业级部署文档，添加自动化测试

#### 新增文件
```
docs/
├── DEPLOYMENT_GUIDE.md          ← Docker Compose 部署指南
├── KUBERNETES_SETUP.md          ← K8s 详细部署步骤
├── MONITORING.md                ← 监控告警配置
├── TROUBLESHOOTING.md           ← 问题排查手册
├── CAPACITY_PLANNING.md         ← 容量规划
└── ARCHITECTURE.md              ← 架构演进文档

specs/
├── deployment/
│   ├── docker-compose.spec.md   ← Docker Compose 验收标准
│   ├── kubernetes.spec.md       ← K8s 部署验收标准
│   └── performance.spec.md      ← 性能基准测试
```

#### 具体任务

| ID | 任务 | 验证项 |
|----|------|--------|
| **4.1** | 更新 README | docker-compose 快速开始 |
| **4.2** | 部署指南 | DEPLOYMENT_GUIDE.md (3000 字) |
| **4.3** | K8s 指南 | KUBERNETES_SETUP.md (4000 字) |
| **4.4** | 更新 spec | 新增 deployment feature spec |
| **4.5** | 容量规划表 | CPU/Memory 估算 |
| **4.6** | 故障排查 | 常见问题 + 解决方案 |

---

## 🔄 执行顺序与依赖关系

```
序列：

┌─ 1.1: requirements.txt (5min)
│   ↓
├─ 1.2-1.5: 代码改动 (45min)
│   ↓
├─ 1.6-1.7: 环境配置 (15min)
│
│ ┌─────────────────────────────────────
├─┤ 2.1: Backend Dockerfile (10min)
│ │  ↓
│ ├─ 2.2-2.6: docker-compose 编写 (40min)
│ │
│ │ ┌──────────────────────────────────
│ ├─┤ 3.1-3.10: K8s 清单 (50min)
│ │ │   └─ 可并行执行
│ │
│ └─ 4.1-4.6: 文档与验证 (30min)

总耗时: ~180-210 分钟 (3-3.5 小时)
```

---

## 📊 成果物清单

### 代码改动统计
```
新增文件：        12 个
修改文件：        8 个
删除文件：        0 个
新增代码行数：    ~2000 行 (YAML + Python)
已有代码改动：    ~500 行
```

### 功能提升
```
✅ Redis 缓存        → 性能 +30 倍
✅ Docker Compose    → 本地部署 99% 自动化
✅ K8s + HPA         → 自动扩容 + 故障自愈
✅ 企业级文档        → 知识沉淀、易于交接
```

---

## ⏱️ 时间预算

| 阶段 | 任务数 | 预估时间 | 实际灵活度 |
|------|--------|---------|-----------|
| P1 Redis | 7 | 90min | ±15min |
| P1 Compose | 6 | 60min | ±10min |
| P2 K8s | 10 | 60min | ±20min |
| P2 Docs | 6 | 30min | ±10min |
| **合计** | **29** | **240min** | **±55min** |

---

## 🚀 执行检查点

### 里程碑 1（完成 P1）
```
✅ redis 依赖已加入，requirement.txt 验证
✅ cache.py 实现完成，单元测试通过
✅ 工具层集成缓存，功能测试通过
✅ docker-compose 可一键启动全栈
   验证: docker-compose ps 显示 4 green

预期时间: 2.5 小时
```

### 里程碑 2（完成 P2）
```
✅ K8s 所有清单已创建
✅ kubectl apply -f k8s/ 成功
✅ 所有 Pod 进入 Running 状态
✅ HPA 已启用，metrics-server 就绪
✅ 文档完整，README 已更新

预期时间: 3.5 小时
```

### 里程碑 3（完成验证）
```
✅ health 接口返回正确配置 + Redis 状态
✅ 诗词查询缓存命中率 > 70%
✅ 性能基准测试通过
✅ K8s HPA 自动扩容测试通过
✅ 故障注入测试通过（Pod 重启恢复）

预期时间: 4 小时
```

---

## 🎓 学习输出

完成后，你将获得：

1. **实践经验**
   - 生产级 Redis 缓存模式
   - Docker Compose 多容器编排
   - Kubernetes 部署最佳实践
   - HPA 自动扩容配置

2. **可复用资产**
   - docker-compose.yml 模板（可用于其他项目）
   - K8s 部署清单库（可用于其他微服务）
   - 企业部署文档（可作为团队规范）

3. **性能数据**
   - 性能基准（Memory、CPU、QPS）
   - 缓存命中率对比
   - 扩容成本分析

---

## ⚠️ 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Redis 未安装 | Redis 服务启动失败 | 提前 docker pull redis:7-alpine |
| K8s 集群不可用 | K8s 清单无法验证 | 本地 minikube/kind 代替 |
| MySQL 连接失败 | 数据库初始化失败 | docker-compose 自动 volume + init.sql |
| 网络隔离测试失败 | Compose 服务互联失败 | 调试 networks 配置 |

---

## 📝 检查清单（执行前）

- [ ] 代码已 git commit
- [ ] 所有终端已关闭（避免端口冲突）
- [ ] 有 30 分钟连续不中断的开发时间
- [ ] Docker 已安装（docker --version 可用）
- [ ] 了解基本 Docker/K8s 概念（可选）

---

## 🎯 成功标志

完成本计划后，你的项目将：

```
Current: ████████░░ 70% (缺 Redis、K8s、文档)

After:   ██████████ 100% (企业级就绪)

+30% = 
  ✅ Redis 缓存 (性能 +30x)
  ✅ Docker Compose (开发体验 +95%)
  ✅ K8s (生产可靠性 99.9%)
  ✅ 文档 (可交接、可扩展)
```

---

## 👉 下一步

确认计划无误后，我将按照如下顺序逐步执行：

1. **Step 1-7**：Redis 缓存模块 (90min)
2. **Step 8-13**：Docker Compose 编排 (60min)  
3. **Step 14-23**：K8s 清单生成 (60min)
4. **Step 24-29**：文档与验证 (30min)

每完成一个大阶段，我都会给你验证清单，让你可以即时反馈！

---

**准备好开始了吗？确认后我立即开工！** 🚀
