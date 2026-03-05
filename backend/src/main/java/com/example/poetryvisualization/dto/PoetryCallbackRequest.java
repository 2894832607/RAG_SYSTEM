package com.example.poetryvisualization.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public class PoetryCallbackRequest {
  @NotBlank(message = "taskId 不能为空")
  private String taskId;

  @NotNull(message = "status 不能为空")
  private Integer status;
  private String errorMessage;

  @Valid
  private CallbackPayload payload;

  public String getTaskId() {
    return taskId;
  }

  public void setTaskId(String taskId) {
    this.taskId = taskId;
  }

  public Integer getStatus() {
    return status;
  }

  public void setStatus(Integer status) {
    this.status = status;
  }

  public String getErrorMessage() {
    return errorMessage;
  }

  public void setErrorMessage(String errorMessage) {
    this.errorMessage = errorMessage;
  }

  public CallbackPayload getPayload() {
    return payload;
  }

  public void setPayload(CallbackPayload payload) {
    this.payload = payload;
  }

  public static class CallbackPayload {
    @NotBlank(message = "retrievedText 不能为空")
    private String retrievedText;

    @NotBlank(message = "enhancedPrompt 不能为空")
    private String enhancedPrompt;

    @NotBlank(message = "imageUrl 不能为空")
    private String imageUrl;

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

    public String getImageUrl() {
      return imageUrl;
    }

    public void setImageUrl(String imageUrl) {
      this.imageUrl = imageUrl;
    }
  }
}
