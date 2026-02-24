package com.example.poetryvisualization.model;

public enum TaskStatus {
  PENDING(0),
  COMPLETED(1),
  FAILED(2);

  private final int code;

  TaskStatus(int code) {
    this.code = code;
  }

  public int getCode() {
    return code;
  }
}
