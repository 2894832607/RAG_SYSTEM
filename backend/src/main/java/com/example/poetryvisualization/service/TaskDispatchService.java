package com.example.poetryvisualization.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.example.poetryvisualization.config.AiServiceProperties;
import com.example.poetryvisualization.dto.PoetryCallbackRequest;
import com.example.poetryvisualization.entity.GenerationTask;
import com.example.poetryvisualization.mapper.GenerationTaskMapper;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
public class TaskDispatchService {

  private static final Logger log = LoggerFactory.getLogger(TaskDispatchService.class);

  private final GenerationTaskMapper taskMapper;
  private final RestTemplate restTemplate;
  private final String aiServiceUrl;
  private final ObjectMapper objectMapper;

  public TaskDispatchService(GenerationTaskMapper taskMapper,
                             RestTemplateBuilder restTemplateBuilder,
                             AiServiceProperties aiServiceProperties,
                             ObjectMapper objectMapper) {
    this.taskMapper = taskMapper;
    this.restTemplate = restTemplateBuilder.build();
    this.aiServiceUrl = Objects.requireNonNull(aiServiceProperties.getUrl(), "ai.service.url must not be null");
    this.objectMapper = objectMapper;
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
      throw new IllegalArgumentException("Task not found: " + taskId);
    }
    return task;
  }

  /** 向 AI 微服务派发生成请求 */
  private void dispatchToAi(GenerationTask task) throws Exception {
    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_JSON);
    Map<String, String> payload = new HashMap<>();
    payload.put("taskId", task.getTaskId());
    payload.put("sourceText", task.getOriginalPoem());
    payload.put("callbackUrl", "http://127.0.0.1:8080/api/v1/poetry/callback");
    String jsonPayload = objectMapper.writeValueAsString(payload);
    HttpEntity<String> entity = new HttpEntity<>(jsonPayload, headers);
    restTemplate.postForEntity(aiServiceUrl, entity, String.class);
  }
}
