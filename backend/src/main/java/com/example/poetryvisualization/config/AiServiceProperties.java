package com.example.poetryvisualization.config;

import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@ConfigurationProperties(prefix = "ai.service")
@Validated
public class AiServiceProperties {
  @NotBlank
  private String baseUrl;

  @NotBlank
  private String url;

  @NotBlank
  private String callbackUrl;

  @NotBlank
  private String callbackToken;

  public String getBaseUrl() {
    return baseUrl;
  }

  public void setBaseUrl(String baseUrl) {
    this.baseUrl = baseUrl;
  }

  public String getUrl() {
    return url;
  }

  public void setUrl(String url) {
    this.url = url;
  }

  public String getCallbackUrl() {
    return callbackUrl;
  }

  public void setCallbackUrl(String callbackUrl) {
    this.callbackUrl = callbackUrl;
  }

  public String getCallbackToken() {
    return callbackToken;
  }

  public void setCallbackToken(String callbackToken) {
    this.callbackToken = callbackToken;
  }
}
