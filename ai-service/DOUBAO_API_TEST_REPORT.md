# 豆包 API 测试成功报告

## ✅ 测试结果

### 图像生成（Seedream 5.0 Lite）
- **状态**: ✅ 成功
- **模型**: `doubao-seedream-5-0-lite-260128`
- **API Endpoint**: `POST https://ark.cn-beijing.volces.com/api/v3/images/generations`
- **分辨率**: 1920x1920（≥3686400 像素）
- **生成时间**: ~20 秒
- **Token 消耗**: 14400 tokens

### 视频生成（Seedance 1.5 Pro）
- **状态**: ✅ 成功
- **模型**: `doubao-seedance-1-5-pro-251215`
- **API Endpoint**: `POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`
- **分辨率**: 720p, 16:9
- **时长**: 5 秒
- **帧率**: 24fps
- **生成时间**: ~78 秒（含音频）
- **Token 消耗**: 108900 tokens

---

## 📋 API 调用规范

### 图像生成（Seedream 5.0）

#### Request
```http
POST https://ark.cn-beijing.volces.com/api/v3/images/generations
Content-Type: application/json
Authorization: Bearer ARK_API_KEY

{
  "model": "doubao-seedream-5-0-lite-260128",
  "prompt": "一只可爱的小猫咪，坐在阳光明媚的窗台上，高清写实风格",
  "size": "1920x1920",
  "num_images": 1
}
```

#### Response
```json
{
  "model": "doubao-seedream-5-0-260128",
  "created": 1773692023,
  "data": [{
    "url": "https://...",
    "size": "1920x1920"
  }],
  "usage": {
    "generated_images": 1,
    "output_tokens": 14400,
    "total_tokens": 14400
  }
}
```

#### 关键参数
- **size**: 必须 ≥ 3686400 像素（如 1920x1920 = 3686400）
- **prompt**: 支持中英文
- **num_images**: 1-4

---

### 视频生成（Seedance 1.5 Pro）

#### Step 1: 创建任务
```http
POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
Content-Type: application/json
Authorization: Bearer ARK_API_KEY

{
  "model": "doubao-seedance-1-5-pro-251215",
  "content": [
    {
      "type": "text",
      "text": "无人机以极快速度穿越复杂山林，带来沉浸式飞行体验 --duration 5 --watermark true"
    }
  ]
}
```

#### Response
```json
{
  "id": "cgt-20260317041350-h6dvf",
  "model": "doubao-seedance-1-5-pro-251215",
  "status": "running"
}
```

#### Step 2: 轮询任务状态
```http
GET https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}
Authorization: Bearer ARK_API_KEY
```

#### Response (Success)
```json
{
  "id": "cgt-20260317041350-h6dvf",
  "model": "doubao-seedance-1-5-pro-251215",
  "status": "succeeded",
  "content": {
    "video_url": "https://..."
  },
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 5,
  "framespersecond": 24,
  "generate_audio": true
}
```

#### 关键参数
- **duration**: 5 秒（固定）
- **watermark**: true/false
- **camerafixed**: false（运镜）
- **轮询间隔**: 5 秒
- **超时时间**: 300 秒

---

## 🔧 环境配置

### .env.local 配置
```bash
# 豆包图像配置
IMAGE_PROVIDER=seedream
IMAGE_MODEL=doubao-seedream-5-0-lite-260128
IMAGE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
IMAGE_API_KEY=<YOUR_ARK_API_KEY>

# 豆包视频配置
VIDEO_PROVIDER=seedance
VIDEO_MODEL=doubao-seedance-1-5-pro-251215
VIDEO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VIDEO_API_KEY=<YOUR_ARK_API_KEY>
```

---

## 💡 最佳实践

### 图像生成
1. **尺寸要求**: 必须 ≥ 3686400 像素
   - ✅ 1920x1920 = 3686400
   - ✅ 2048x2048 = 4194304
   - ❌ 1024x1024 = 1048576（太小）

2. **Prompt 优化**:
   - 包含主体、场景、风格
   - 示例："一只可爱的小猫咪，坐在阳光明媚的窗台上，高清写实风格"

### 视频生成
1. **异步轮询**:
   ```python
   max_attempts = 60  # 5 分钟
   poll_interval = 5  # 5 秒
   ```

2. **Prompt 语法**:
   ```
   {描述} --duration 5 --watermark true --camerafixed false
   ```

3. **错误处理**:
   - 状态码检查（200/400/404/500）
   - 轮询超时处理
   - 失败重试机制

---

## 📊 成本对比

| 模型 | 价格 | 测试成本 |
|------|------|----------|
| Seedream 5.0 Lite | ¥0.012/张 | ¥0.012 |
| Seedance 1.5 Pro | ¥0.6/个 | ¥0.6 |

**总计测试成本**: ¥0.612

---

## 🎯 下一步

1. ✅ 图像生成 API 集成到 ai-service
2. ✅ 视频生成 API 集成到 ai-service
3. ⏳ 图生视频（Image-to-Video）测试
4. ⏳ 批量生成优化
5. ⏳ 错误重试机制完善

---

## 📝 测试脚本

- `test_doubao_seedream.py` - 图像生成测试
- `test_doubao_video_rest.py` - 视频生成测试
- `test_doubao_i2v.py` - 图生视频测试（待创建）

---

**测试日期**: 2026-03-17  
**测试人员**: AI Assistant  
**状态**: ✅ 全部通过
