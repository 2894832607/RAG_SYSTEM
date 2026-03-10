package com.example.poetryvisualization.controller;

import com.example.poetryvisualization.dto.PoemTaskRequest;
import com.example.poetryvisualization.dto.PoetryCallbackRequest;
import com.example.poetryvisualization.entity.GenerationTask;
import com.example.poetryvisualization.config.AiServiceProperties;
import com.example.poetryvisualization.service.TaskDispatchService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.poetryvisualization.mapper.GenerationTaskMapper;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/poetry")
@Validated
public class PoetryVisualizationController {

  private final TaskDispatchService dispatchService;
  private final AiServiceProperties aiServiceProperties;
  private final GenerationTaskMapper taskMapper;

  public PoetryVisualizationController(TaskDispatchService dispatchService,
                                        AiServiceProperties aiServiceProperties,
                                        GenerationTaskMapper taskMapper) {
    this.dispatchService = dispatchService;
    this.aiServiceProperties = aiServiceProperties;
    this.taskMapper = taskMapper;
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
  public ResponseEntity<Map<String, Object>> handleCallback(
      @RequestHeader(value = "X-Callback-Token", required = false) String callbackToken,
      @Valid @RequestBody PoetryCallbackRequest request) {
    if (!aiServiceProperties.getCallbackToken().equals(callbackToken)) {
      throw new IllegalArgumentException("Invalid callback token");
    }
    dispatchService.updateFromCallback(request);
    return ResponseEntity.ok(Map.of("code", 200, "message", "callback processed"));
  }

  /**
   * SSE 代理 → 将 AI 服务的 GLM 思考流实时推送给前端。
   * 前端通过 fetch() 连接此端点（支持自定义 Authorization 头）。
   */
  @PostMapping(value = "/think-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
  @SuppressWarnings("null")
  public SseEmitter thinkStream(@RequestBody PoemTaskRequest request) {
    SseEmitter emitter = new SseEmitter(120_000L);

    // 派生 think-stream URL（将 async 替换为 think-stream）
    String asyncUrl = aiServiceProperties.getUrl();
    String thinkUrl = asyncUrl.replace("/generate/async", "/generate/think-stream");

    String json = "{\"sourceText\":\"" + escapeJson(request.getPoemText()) + "\"}";

    new Thread(() -> {
      try {
        HttpClient client = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

        HttpRequest httpRequest = HttpRequest.newBuilder()
            .uri(URI.create(thinkUrl))
            .header("Content-Type", "application/json; charset=UTF-8")
            .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
            .timeout(Duration.ofSeconds(120))
            .build();

        HttpResponse<InputStream> response = client.send(
            httpRequest, HttpResponse.BodyHandlers.ofInputStream());

        try (BufferedReader reader = new BufferedReader(
            new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
          String line;
          while ((line = reader.readLine()) != null) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) continue;
            if (trimmed.startsWith("data:")) {
              String data = trimmed.substring(5).trim();
              emitter.send(SseEmitter.event().data((Object) Objects.requireNonNullElse(data, ""), MediaType.TEXT_PLAIN));
              if ("[DONE]".equals(data)) break;
            }
          }
        }
        emitter.complete();
      } catch (Exception e) {
        emitter.completeWithError(e);
      }
    }).start();

    return emitter;
  }

  private static String escapeJson(String value) {
    if (value == null) return "";
    return value.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
  }

  /**
   * 查询当前用户的历史生成任务列表（倒序，仅返回当前用户数据）。
   * <p>
   * Spec: specs/openapi/backend.yaml §/api/v1/poetry/history
   * Spec: specs/features/poetry-visualization.spec.md §用户故事 5
   */
  @GetMapping("/history")
  public ResponseEntity<Map<String, Object>> listHistory(
      HttpServletRequest httpRequest,
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(defaultValue = "20") int pageSize) {
    Long userId = (Long) httpRequest.getAttribute("authenticatedUserId");

    LambdaQueryWrapper<GenerationTask> wrapper = new LambdaQueryWrapper<>();
    wrapper.eq(GenerationTask::getUserId, userId)
           .orderByDesc(GenerationTask::getGmtCreate);

    List<GenerationTask> rawList = taskMapper.selectList(wrapper);

    // 简单内存分页
    int total = rawList.size();
    int fromIdx = Math.min((page - 1) * pageSize, total);
    int toIdx   = Math.min(fromIdx + pageSize, total);
    List<Map<String, Object>> items = rawList.subList(fromIdx, toIdx).stream()
        .map(t -> {
          Map<String, Object> item = new HashMap<>();
          item.put("taskId",         t.getTaskId());
          item.put("originalPoem",   t.getOriginalPoem() != null   ? t.getOriginalPoem()   : "");
          item.put("resultImageUrl", t.getResultImageUrl() != null  ? t.getResultImageUrl() : "");
          item.put("taskStatus",     resolveStatusLabel(t.getTaskStatus()));
          item.put("createdAt",      t.getGmtCreate() != null       ? t.getGmtCreate().toString() : "");
          return item;
        })
        .collect(Collectors.toList());

    return ResponseEntity.ok(Map.of(
        "code", 200,
        "data", Map.of(
            "total", total,
            "page", page,
            "pageSize", pageSize,
            "items", items
        )
    ));
  }

  private static String resolveStatusLabel(Integer status) {
    if (status == null) return "PENDING";
    return switch (status) {
      case 1 -> "COMPLETED";
      case 2 -> "FAILED";
      default -> "PENDING";
    };
  }
}
