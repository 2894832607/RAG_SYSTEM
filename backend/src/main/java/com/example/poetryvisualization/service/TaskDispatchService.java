package com.example.poetryvisualization.service;

import com.example.poetryvisualization.dto.PoetryCallbackRequest;
import com.example.poetryvisualization.model.TaskAggregate;
import com.example.poetryvisualization.model.TaskStatus;
import com.example.poetryvisualization.repository.TaskRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@Service
public class TaskDispatchService {
  private final TaskRepository repository;
  private final RestTemplate restTemplate;
  private final String aiServiceUrl;

  public TaskDispatchService(TaskRepository repository,
                             RestTemplateBuilder restTemplateBuilder,
                             @Value("${ai.service.url}") String aiServiceUrl) {
    this.repository = repository;
    this.restTemplate = restTemplateBuilder.build();
    this.aiServiceUrl = aiServiceUrl;
  }

  public TaskAggregate createTask(String poemText) {
    TaskAggregate task = new TaskAggregate();
    task.setTaskId(UUID.randomUUID().toString());
    task.setOriginalPoem(poemText);
    task.setTaskStatus(TaskStatus.PENDING);
    task.setGmtCreate(LocalDateTime.now());
    task.setGmtModified(LocalDateTime.now());
    repository.save(task);
    dispatchToAi(task);
    return task;
  }

  public TaskAggregate updateFromCallback(PoetryCallbackRequest request) {
    TaskAggregate aggregate = repository.findByTaskId(request.getTaskId())
      .orElseThrow(() -> new IllegalArgumentException("Unknown task id: " + request.getTaskId()));
    if (request.getStatus() != null && request.getStatus() == TaskStatus.COMPLETED.getCode()) {
      aggregate.setTaskStatus(TaskStatus.COMPLETED);
    } else {
      aggregate.setTaskStatus(TaskStatus.FAILED);
    }
    if (request.getPayload() != null) {
      aggregate.setRetrievedText(request.getPayload().getRetrievedText());
      aggregate.setEnhancedPrompt(request.getPayload().getEnhancedPrompt());
      aggregate.setResultImageUrl(request.getPayload().getImageUrl());
    }
    aggregate.setGmtModified(LocalDateTime.now());
    repository.save(aggregate);
    return aggregate;
  }

  public TaskAggregate findByTaskId(String taskId) {
    return repository.findByTaskId(taskId)
      .orElseThrow(() -> new IllegalArgumentException("Task not found: " + taskId));
  }

  private void dispatchToAi(TaskAggregate task) {
    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_JSON);
    Map<String, String> payload = Map.of(
      "taskId", task.getTaskId(),
      "sourceText", task.getOriginalPoem(),
      "callbackUrl", "http://localhost:8080/api/v1/poetry/callback"
    );
    HttpEntity<Map<String, String>> entity = new HttpEntity<>(payload, headers);
    restTemplate.postForEntity(aiServiceUrl, entity, Void.class);
  }
}
