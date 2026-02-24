package com.example.poetryvisualization.controller;

import com.example.poetryvisualization.dto.PoemTaskRequest;
import com.example.poetryvisualization.dto.PoetryCallbackRequest;
import com.example.poetryvisualization.model.TaskAggregate;
import com.example.poetryvisualization.service.TaskDispatchService;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/poetry")
@Validated
public class PoetryVisualizationController {
  private final TaskDispatchService dispatchService;

  public PoetryVisualizationController(TaskDispatchService dispatchService) {
    this.dispatchService = dispatchService;
  }

  @PostMapping("/visualize")
  public ResponseEntity<Map<String, Object>> submitPoem(@Valid @RequestBody PoemTaskRequest request) {
    TaskAggregate aggregate = dispatchService.createTask(request.getPoemText());
    return ResponseEntity.ok(Map.of(
      "code", 200,
      "message", "Task submitted successfully",
      "data", Map.of("taskId", aggregate.getTaskId())
    ));
  }

  @GetMapping("/task/{taskId}")
  public ResponseEntity<Map<String, Object>> getTask(@PathVariable String taskId) {
    TaskAggregate aggregate = dispatchService.findByTaskId(taskId);
    return ResponseEntity.ok(Map.of(
      "code", 200,
      "data", Map.of(
        "taskId", aggregate.getTaskId(),
        "originalPoem", aggregate.getOriginalPoem(),
        "retrievedText", aggregate.getRetrievedText(),
        "enhancedPrompt", aggregate.getEnhancedPrompt(),
        "resultImageUrl", aggregate.getResultImageUrl(),
        "taskStatus", aggregate.getTaskStatus().name()
      )
    ));
  }

  @PostMapping("/callback")
  public ResponseEntity<Map<String, Object>> handleCallback(@RequestBody PoetryCallbackRequest request) {
    dispatchService.updateFromCallback(request);
    return ResponseEntity.ok(Map.of("code", 200, "message", "callback processed"));
  }
}
