package com.example.poetryvisualization.dto;

public class PoetryCallbackRequest {
  private String taskId;
  private Integer status;
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

  public CallbackPayload getPayload() {
    return payload;
  }

  public void setPayload(CallbackPayload payload) {
    this.payload = payload;
  }

  public static class CallbackPayload {
    private String retrievedText;
    private String enhancedPrompt;
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
