package com.example.poetryvisualization.controller;

import com.example.poetryvisualization.dto.PoemTaskRequest;
import com.example.poetryvisualization.dto.PoetryCallbackRequest;
import com.example.poetryvisualization.entity.GenerationTask;
import com.example.poetryvisualization.service.TaskDispatchService;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/poetry")
@Validated
public class PoetryVisualizationController {

  private final TaskDispatchService dispatchService;

  public PoetryVisualizationController(TaskDispatchService dispatchService) {
    this.dispatchService = dispatchService;
  }

  /** 提交诗句 → 创建可视化任务 */
  @PostMapping("/visualize")
  public ResponseEntity<Map<String, Object>> submitPoem(@Valid @RequestBody PoemTaskRequest request) {
    GenerationTask task = dispatchService.createTask(request.getPoemText());
    return ResponseEntity.ok(Map.of(
      "code", 200,
      "message", "Task submitted successfully",
      "data", Map.of("taskId", task.getTaskId())
    ));
  }

  /** 前端轮询 → 查询任务状态 */
  @GetMapping("/task/{taskId}")
  public ResponseEntity<Map<String, Object>> getTask(@PathVariable String taskId) {
    GenerationTask task = dispatchService.findByTaskId(taskId);
    Map<String, Object> data = new HashMap<>();
    data.put("taskId",         task.getTaskId());
    data.put("originalPoem",   task.getOriginalPoem());
    data.put("retrievedText",  task.getRetrievedText()  != null ? task.getRetrievedText()  : "");
    data.put("enhancedPrompt", task.getEnhancedPrompt() != null ? task.getEnhancedPrompt() : "");
    data.put("resultImageUrl", task.getResultImageUrl() != null ? task.getResultImageUrl() : "");
    data.put("taskStatus",     task.getTaskStatus());
    data.put("errorMessage",   task.getErrorMessage()   != null ? task.getErrorMessage()   : "");
    return ResponseEntity.ok(Map.of("code", 200, "data", data));
  }

  /** AI 微服务回调 → 更新任务结果 */
  @PostMapping("/callback")
  public ResponseEntity<Map<String, Object>> handleCallback(@RequestBody PoetryCallbackRequest request) {
    dispatchService.updateFromCallback(request);
    return ResponseEntity.ok(Map.of("code", 200, "message", "callback processed"));
  }
}
