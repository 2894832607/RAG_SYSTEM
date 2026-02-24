package com.example.poetryvisualization.dto;

import jakarta.validation.constraints.NotBlank;

public class PoemTaskRequest {

  @NotBlank(message = "诗句不能为空")
  private String poemText;

  public String getPoemText() {
    return poemText;
  }

  public void setPoemText(String poemText) {
    this.poemText = poemText;
  }
}
