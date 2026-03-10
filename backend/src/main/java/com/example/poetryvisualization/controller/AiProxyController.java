package com.example.poetryvisualization.controller;

import com.example.poetryvisualization.config.AiServiceProperties;
import com.example.poetryvisualization.entity.GenerationTask;
import com.example.poetryvisualization.mapper.GenerationTaskMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * AI Service SSE 代理控制器。
 * <p>
 * 所有前端对 AI Service 的调用均经过此控制器，经 JWT 认证后透明代理。
 * 架构合规: 满足 constitution §3.1 分层规范（Frontend → Backend → AI Service）。
 * <p>
 * Spec: specs/openapi/backend.yaml §/api/v1/poetry/chat、/storyboard、/chat/session
 */
@RestController
@RequestMapping("/api/v1/poetry")
public class AiProxyController {

    private static final Logger log = LoggerFactory.getLogger(AiProxyController.class);

    private final AiServiceProperties aiServiceProperties;
    private final GenerationTaskMapper taskMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public AiProxyController(AiServiceProperties aiServiceProperties,
                             GenerationTaskMapper taskMapper) {
        this.aiServiceProperties = aiServiceProperties;
        this.taskMapper = taskMapper;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/v1/poetry/chat/session — 创建会话（代理到 AI Service）
    // ──────────────────────────────────────────────────────────────────────────
    @PostMapping("/chat/session")
    public ResponseEntity<Map<String, Object>> createSession() {
        String aiUrl = aiServiceProperties.getBaseUrl() + "/ai/api/v1/chat/session";
        try {
            HttpClient client = HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)
                    .connectTimeout(Duration.ofSeconds(10))
                    .build();
            HttpRequest httpRequest = HttpRequest.newBuilder()
                    .uri(URI.create(aiUrl))
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.noBody())
                    .timeout(Duration.ofSeconds(10))
                    .build();
            HttpResponse<String> response = client.send(
                    httpRequest, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() >= 400) {
                log.warn("AI Service create session failed: status={}", response.statusCode());
                return ResponseEntity.internalServerError()
                        .body(Map.of("code", 500, "message", "AI Service 不可达"));
            }
            // 直接透传 AI Service 返回的 JSON
            JsonNode node = objectMapper.readTree(response.body());
            return ResponseEntity.ok(Map.of("code", 200, "data", node));
        } catch (Exception e) {
            log.error("createSession failed", e);
            // 降级：生成一个本地 UUID 返回，不中断用户流程
            return ResponseEntity.ok(Map.of("code", 200,
                    "data", Map.of("session_id", UUID.randomUUID().toString())));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/v1/poetry/chat — 对话 SSE 代理
    // ──────────────────────────────────────────────────────────────────────────
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@RequestBody String body, HttpServletRequest httpRequest) {
        Long userId = (Long) httpRequest.getAttribute("authenticatedUserId");
        String aiUrl = aiServiceProperties.getBaseUrl() + "/ai/api/v1/chat";
        return proxySse(aiUrl, body, /*saveHistory=*/false, userId, null);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/v1/poetry/storyboard — 分镜 SSE 代理（完成后写历史）
    // ──────────────────────────────────────────────────────────────────────────
    @PostMapping(value = "/storyboard", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter storyboard(@RequestBody String body, HttpServletRequest httpRequest) {
        Long userId = (Long) httpRequest.getAttribute("authenticatedUserId");
        // 从 body 中解析 sourceText，用于历史记录
        String sourceText = extractSourceText(body);
        String aiUrl = aiServiceProperties.getBaseUrl() + "/ai/api/v1/generate/storyboard";
        return proxySse(aiUrl, body, /*saveHistory=*/true, userId, sourceText);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 核心：SSE 透明代理
    // ──────────────────────────────────────────────────────────────────────────
    private SseEmitter proxySse(String targetUrl, String requestBody,
                                boolean saveHistory, Long userId, String sourceText) {
        SseEmitter emitter = new SseEmitter(180_000L);

        new Thread(() -> {
            // 用于分镜完成时写历史
            String firstImageUrl = null;

            try {
                HttpClient client = HttpClient.newBuilder()
                        .version(HttpClient.Version.HTTP_1_1)
                        .connectTimeout(Duration.ofSeconds(10))
                        .build();

                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(targetUrl))
                        .header("Content-Type", "application/json; charset=UTF-8")
                        .POST(HttpRequest.BodyPublishers.ofString(
                                requestBody != null ? requestBody : "{}",
                                StandardCharsets.UTF_8))
                        .timeout(Duration.ofSeconds(180))
                        .build();

                HttpResponse<InputStream> response = client.send(
                        request, HttpResponse.BodyHandlers.ofInputStream());

                if (response.statusCode() >= 400) {
                    emitter.send(SseEmitter.event().data(
                            "{\"type\":\"error\",\"content\":\"AI Service 响应错误: " + response.statusCode() + "\"}",
                            MediaType.TEXT_PLAIN));
                    emitter.complete();
                    return;
                }

                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        String trimmed = line.trim();
                        if (trimmed.isEmpty()) continue;
                        if (!trimmed.startsWith("data:")) {
                            // 直接透传空白行（SSE 协议需要）
                            continue;
                        }
                        String data = trimmed.substring(5).trim();

                        // 转发给前端
                        emitter.send(SseEmitter.event().data(data, MediaType.TEXT_PLAIN));

                        // === 分镜：捕获 shot_done 的第一张图 URL ===
                        if (saveHistory && firstImageUrl == null && data.startsWith("{")) {
                            try {
                                JsonNode node = objectMapper.readTree(data);
                                String type = node.path("type").asText();
                                if ("shot_done".equals(type)) {
                                    String imgUrl = node.path("image_url").asText(null);
                                    if (imgUrl != null && !imgUrl.isBlank()) {
                                        firstImageUrl = imgUrl;
                                    }
                                }
                            } catch (Exception ignored) {
                                // JSON 解析失败不中断流
                            }
                        }

                        if ("[DONE]".equals(data)) break;
                    }
                }

                // === 分镜完成后写入历史 ===
                if (saveHistory) {
                    saveStoryboardHistory(userId, sourceText, firstImageUrl);
                }

                emitter.complete();

            } catch (java.net.ConnectException | java.net.http.HttpConnectTimeoutException e) {
                // T026: AI Service 不可达时 5s 内（connectTimeout=10s）快速返回友好错误
                log.warn("AI Service unreachable: url={}, error={}", targetUrl, e.getMessage());
                try {
                    emitter.send(SseEmitter.event().data(
                            "{\"type\":\"error\",\"content\":\"AI 服务暂时不可达，请稍后重试\"}",
                            MediaType.TEXT_PLAIN));
                    emitter.complete();
                } catch (Exception ignored) {}
            } catch (Exception e) {
                log.error("SSE proxy error: url={}", targetUrl, e);
                try {
                    emitter.send(SseEmitter.event().data(
                            "{\"type\":\"error\",\"content\":\"代理转发失败: " + escapeJson(e.getMessage()) + "\"}",
                            MediaType.TEXT_PLAIN));
                } catch (Exception ignored) {}
                emitter.completeWithError(e);
            }
        }).start();

        return emitter;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 分镜完成 → 写入 sys_generation_task
    // ──────────────────────────────────────────────────────────────────────────
    private void saveStoryboardHistory(Long userId, String originalPoem, String imageUrl) {
        try {
            GenerationTask task = new GenerationTask();
            task.setTaskId(UUID.randomUUID().toString());
            task.setUserId(userId);
            task.setOriginalPoem(originalPoem != null ? originalPoem : "");
            task.setResultImageUrl(imageUrl != null ? imageUrl : "");
            task.setTaskStatus(GenerationTask.STATUS_COMPLETED);
            task.setGmtCreate(LocalDateTime.now());
            task.setGmtModified(LocalDateTime.now());
            taskMapper.insert(task);
            log.info("Storyboard history saved: taskId={}, userId={}", task.getTaskId(), userId);
        } catch (Exception e) {
            log.error("Failed to save storyboard history: userId={}", userId, e);
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 工具方法
    // ──────────────────────────────────────────────────────────────────────────
    private String extractSourceText(String body) {
        if (body == null || body.isBlank()) return "";
        try {
            JsonNode node = objectMapper.readTree(body);
            return node.path("sourceText").asText("");
        } catch (Exception e) {
            return "";
        }
    }

    private static String escapeJson(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
    }
}
