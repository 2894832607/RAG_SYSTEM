package com.example.poetryvisualization.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.poetryvisualization.config.AiServiceProperties;
import com.example.poetryvisualization.dto.PoetryCallbackRequest;
import com.example.poetryvisualization.entity.GenerationTask;
import com.example.poetryvisualization.mapper.GenerationTaskMapper;
import com.example.poetryvisualization.exception.ResourceNotFoundException;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.LocalDateTime;
import java.util.Objects;
import java.util.UUID;

@Service
public class TaskDispatchService {

  private static final Logger log = LoggerFactory.getLogger(TaskDispatchService.class);

  private final GenerationTaskMapper taskMapper;
  private final String aiServiceUrl;
  private final String callbackUrl;
  private final String callbackToken;

  public TaskDispatchService(GenerationTaskMapper taskMapper,
                             AiServiceProperties aiServiceProperties) {
    this.taskMapper = taskMapper;
    this.aiServiceUrl = Objects.requireNonNull(aiServiceProperties.getUrl(), "ai.service.url must not be null");
    this.callbackUrl = Objects.requireNonNull(aiServiceProperties.getCallbackUrl(), "ai.service.callback-url must not be null");
    this.callbackToken = Objects.requireNonNull(aiServiceProperties.getCallbackToken(), "ai.service.callback-token must not be null");
  }

  /** 创建任务 → 持久化到 MySQL → 异步派发到 AI 微服务 */
  public GenerationTask createTask(String poemText) {
    GenerationTask task = new GenerationTask();
    task.setTaskId(UUID.randomUUID().toString());
    task.setOriginalPoem(poemText);
    task.setTaskStatus(GenerationTask.STATUS_PENDING);
    task.setGmtCreate(LocalDateTime.now());
    task.setGmtModified(LocalDateTime.now());
    taskMapper.insert(task);
    // 异步派发（如果 AI 服务不可达，任务仍已落库，可后续重试）
    try {
      dispatchToAi(task);
    } catch (Exception e) {
      task.setTaskStatus(GenerationTask.STATUS_FAILED);
      task.setErrorMessage("AI dispatch failed: " + e.getMessage());
      task.setGmtModified(LocalDateTime.now());
      taskMapper.updateById(task);
      log.error("Failed to dispatch task {} to AI service", task.getTaskId(), e);
    }
    return task;
  }

  /** AI 微服务回调 → 更新任务状态 */
  public GenerationTask updateFromCallback(PoetryCallbackRequest request) {
    GenerationTask task = findByTaskId(request.getTaskId());
    if (request.getStatus() != null && request.getStatus() == GenerationTask.STATUS_COMPLETED) {
      if (request.getPayload() == null) {
        throw new IllegalArgumentException("Callback payload is required for completed task");
      }
      task.setTaskStatus(GenerationTask.STATUS_COMPLETED);
      task.setErrorMessage(null);
    } else {
      task.setTaskStatus(GenerationTask.STATUS_FAILED);
      task.setErrorMessage(request.getErrorMessage());
    }
    if (request.getPayload() != null) {
      task.setRetrievedText(request.getPayload().getRetrievedText());
      task.setEnhancedPrompt(request.getPayload().getEnhancedPrompt());
      task.setResultImageUrl(request.getPayload().getImageUrl());
    }
    task.setGmtModified(LocalDateTime.now());
    taskMapper.updateById(task);
    return task;
  }

  /** 根据 taskId 查询任务 */
  public GenerationTask findByTaskId(String taskId) {
    LambdaQueryWrapper<GenerationTask> wrapper = new LambdaQueryWrapper<>();
    wrapper.eq(GenerationTask::getTaskId, taskId);
    GenerationTask task = taskMapper.selectOne(wrapper);
    if (task == null) {
            throw new ResourceNotFoundException("Task not found: " + taskId);
        }
    return task;
  }

  /** 向 AI 微服务派发生成请求（使用 Java 内置 HttpClient，避免 RestTemplate 编码问题） */
  private void dispatchToAi(GenerationTask task) throws Exception {
    String json = String.format(
        "{\"taskId\":\"%s\",\"sourceText\":\"%s\",\"callbackUrl\":\"%s\",\"callbackToken\":\"%s\"}",
        escapeJson(task.getTaskId()),
        escapeJson(task.getOriginalPoem()),
        escapeJson(callbackUrl),
        escapeJson(callbackToken)
    );
    log.info("Dispatching task {} to AI: url={}, body={}", task.getTaskId(), aiServiceUrl, json);
    java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
        .version(java.net.http.HttpClient.Version.HTTP_1_1)
        .connectTimeout(java.time.Duration.ofSeconds(10))
        .build();
    java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
        .uri(java.net.URI.create(aiServiceUrl))
        .header("Content-Type", "application/json; charset=UTF-8")
        .POST(java.net.http.HttpRequest.BodyPublishers.ofString(json, java.nio.charset.StandardCharsets.UTF_8))
        .timeout(java.time.Duration.ofSeconds(15))
        .build();
    java.net.http.HttpResponse<String> response = client.send(
        request, java.net.http.HttpResponse.BodyHandlers.ofString(java.nio.charset.StandardCharsets.UTF_8));
    log.info("AI service responded: status={} body={}", response.statusCode(), response.body());
    if (response.statusCode() >= 400) {
        throw new RuntimeException(
            String.format("%d on POST to AI: %s", response.statusCode(), response.body()));
    }
  }

  private static String escapeJson(String value) {
    if (value == null) return "";
    return value.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
  }
}
