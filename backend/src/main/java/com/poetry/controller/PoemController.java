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
        String imageUrl = (String) callbackData.get("imageUrl");
        String explanation = (String) callbackData.get("explanation");

        GenerationTask task = taskMapper.selectById(taskId);
        if (task != null) {
            task.setTaskStatus(statusInt == 1 ? TaskStatus.COMPLETED : TaskStatus.FAILED);
            task.setResultImageUrl(imageUrl);
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
