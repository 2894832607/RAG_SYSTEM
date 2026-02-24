package com.example.poetryvisualization.model;

import java.time.LocalDateTime;

public class TaskAggregate {
  private Long id;
  private String taskId;
  private Long userId;
  private String originalPoem;
  private String retrievedText;
  private String enhancedPrompt;
  private String resultImageUrl;
  private TaskStatus taskStatus;
  private String errorMessage;
  private LocalDateTime gmtCreate;
  private LocalDateTime gmtModified;

  public Long getId() {
    return id;
  }

  public void setId(Long id) {
    this.id = id;
  }

  public String getTaskId() {
    return taskId;
  }

  public void setTaskId(String taskId) {
    this.taskId = taskId;
  }

  public Long getUserId() {
    return userId;
  }

  public void setUserId(Long userId) {
    this.userId = userId;
  }

  public String getOriginalPoem() {
    return originalPoem;
  }

  public void setOriginalPoem(String originalPoem) {
    this.originalPoem = originalPoem;
  }

  public String getRetrievedText() {
    return retrievedText;
  }

  public void setRetrievedText(String retrievedText) {
    this.retrievedText = retrievedText;
  }

  public String getEnhancedPrompt() {
    return enhancedPrompt;
  }

  public void setEnhancedPrompt(String enhancedPrompt) {
    this.enhancedPrompt = enhancedPrompt;
  }

  public String getResultImageUrl() {
    return resultImageUrl;
  }

  public void setResultImageUrl(String resultImageUrl) {
    this.resultImageUrl = resultImageUrl;
  }

  public TaskStatus getTaskStatus() {
    return taskStatus;
  }

  public void setTaskStatus(TaskStatus taskStatus) {
    this.taskStatus = taskStatus;
  }

  public String getErrorMessage() {
    return errorMessage;
  }

  public void setErrorMessage(String errorMessage) {
    this.errorMessage = errorMessage;
  }

  public LocalDateTime getGmtCreate() {
    return gmtCreate;
  }

  public void setGmtCreate(LocalDateTime gmtCreate) {
    this.gmtCreate = gmtCreate;
  }

  public LocalDateTime getGmtModified() {
    return gmtModified;
  }

  public void setGmtModified(LocalDateTime gmtModified) {
    this.gmtModified = gmtModified;
  }
}
