package com.poetry.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.poetry.constant.TaskStatus;
import com.poetry.dto.ApiResponse;
import com.poetry.entity.GenerationTask;
import com.poetry.mapper.GenerationTaskMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/poetry")
public class PoemController {

    @Autowired
    private GenerationTaskMapper taskMapper;

    @Value("${poetry.ai-service-url}")
    private String aiServiceUrl;

    @Value("${poetry.callback-url}")
    private String callbackUrl;

    @Value("${poetry.callback-token}")
    private String callbackToken;

    private RestTemplate restTemplate = new RestTemplate();

    @PostMapping("/visualize")
    public ApiResponse<Map<String, String>> submitTask(@RequestBody Map<String, String> request) {
        String poemText = request.get("poemText");
        
        GenerationTask task = new GenerationTask();
        task.setTaskId(UUID.randomUUID().toString());
        task.setOriginalPoem(poemText);
        task.setTaskStatus(TaskStatus.PENDING);
        task.setCreatedAt(LocalDateTime.now());
        // 简化实现：假设 userId 为 1
        task.setUserId(1L);
        taskMapper.insert(task);

        // 异步调用 AI Service
        try {
            Map<String, Object> aiRequest = new HashMap<>();
            aiRequest.put("taskId", task.getTaskId());
            aiRequest.put("poemText", poemText); // 对齐 specs/openapi/ai-service.yaml (应一致)
            aiRequest.put("callbackUrl", callbackUrl);
            aiRequest.put("callbackToken", callbackToken);

            restTemplate.postForEntity(aiServiceUrl + "/ai/api/v1/generate/async", aiRequest, String.class);
            task.setTaskStatus(TaskStatus.PROCESSING);
            taskMapper.updateById(task);
        } catch (Exception e) {
            // 正常应由异常处理器捕获
        }

        Map<String, String> data = new HashMap<>();
        data.put("taskId", task.getTaskId());
        return ApiResponse.success(data);
    }

    @PostMapping("/callback")
    public ApiResponse<String> handleCallback(@RequestBody Map<String, Object> callbackData) {
        String taskId = (String) callbackData.get("taskId");
        int statusInt = (int) callbackData.get("status");
        
        // 支持新旧两种格式：旧格式直接传 imageUrl，新格式在 payload 中
        String imageUrl = (String) callbackData.get("imageUrl");
        String videoUrl = (String) callbackData.get("videoUrl");
        String explanation = (String) callbackData.get("explanation");
        
        // 新格式：从 payload 中提取多张图片
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) callbackData.get("payload");
        if (payload != null) {
            // 优先使用 payload 中的值
            if (payload.get("imageUrl") != null) {
                imageUrl = (String) payload.get("imageUrl");
            }
            if (payload.get("videoUrl") != null) {
                videoUrl = (String) payload.get("videoUrl");
            }
            if (payload.get("explanation") != null) {
                explanation = (String) payload.get("explanation");
            }
            
            // 新字段：imageUrls（数组格式）
            Object imageUrlsObj = payload.get("imageUrls");
            if (imageUrlsObj != null) {
                try {
                    com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
                    // 如果是 List 就直接转 JSON，否则先序列化
                    String imageUrlsJson;
                    if (imageUrlsObj instanceof java.util.List) {
                        imageUrlsJson = mapper.writeValueAsString(imageUrlsObj);
                    } else {
                        imageUrlsJson = imageUrlsObj.toString();
                    }
                    
                    // 存储到 resultImageUrls 字段
                    GenerationTask task = taskMapper.selectById(taskId);
                    if (task != null) {
                        task.setResultImageUrls(imageUrlsJson);
                        
                        // 同时提取第一张作为主图（向后兼容）
                        if (imageUrl == null || imageUrl.isEmpty()) {
                            java.util.List<String> urls = mapper.readValue(imageUrlsJson, 
                                new com.fasterxml.jackson.core.type.TypeReference<java.util.List<String>>() {});
                            if (!urls.isEmpty()) {
                                task.setResultImageUrl(urls.get(0));
                            }
                        }
                        taskMapper.updateById(task);
                    }
                } catch (Exception e) {
                    // JSON处理失败，记录日志但不影响主流程
                }
            }
        }

        GenerationTask task = taskMapper.selectById(taskId);
        if (task != null) {
            task.setTaskStatus(statusInt == 1 ? TaskStatus.COMPLETED : TaskStatus.FAILED);
            
            // 处理单张图片（向后兼容）
            if (imageUrl != null && !imageUrl.isEmpty()) {
                task.setResultImageUrl(imageUrl);
                
                // 如果没有 imageUrls 字段，将单张图片转为数组存储
                if (task.getResultImageUrls() == null || task.getResultImageUrls().isEmpty()) {
                    try {
                        com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
                        java.util.List<String> urls = java.util.Arrays.asList(imageUrl);
                        task.setResultImageUrls(mapper.writeValueAsString(urls));
                    } catch (Exception e) {
                        // JSON处理失败，保持原样
                    }
                }
            }
            
            task.setResultVideoUrl(videoUrl);
            task.setPoemExplanation(explanation);
            taskMapper.updateById(task);
            return ApiResponse.success("Callback processed");
        }
        return ApiResponse.error(404, "Task not found");
    }

    @GetMapping("/history")
    public ApiResponse<List<GenerationTask>> getHistory() {
        // 简化实现：返回 userId=1 的所有任务
        List<GenerationTask> tasks = taskMapper.selectList(new LambdaQueryWrapper<GenerationTask>()
                .eq(GenerationTask::getUserId, 1L)
                .orderByDesc(GenerationTask::getCreatedAt));
        return ApiResponse.success(tasks);
    }

    @GetMapping("/task/{taskId}")
    public ApiResponse<GenerationTask> getTask(@PathVariable String taskId) {
        GenerationTask task = taskMapper.selectById(taskId);
        if (task != null) {
            return ApiResponse.success(task);
        }
        return ApiResponse.error(404, "Task not found");
    }
}
