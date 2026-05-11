package com.example.poetryvisualization.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.poetryvisualization.config.AiServiceProperties;
import com.example.poetryvisualization.entity.ChatMessage;
import com.example.poetryvisualization.entity.GenerationTask;
import com.example.poetryvisualization.mapper.ChatMessageMapper;
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
import java.util.*;
import java.util.stream.Collectors;

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
    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(5);

    // 共享 HttpClient，避免每次请求都创建新实例（连接握手开销）
    private static final java.net.http.HttpClient HTTP_CLIENT = java.net.http.HttpClient.newBuilder()
            .version(java.net.http.HttpClient.Version.HTTP_1_1)
            .connectTimeout(CONNECT_TIMEOUT)
            .build();

    private final AiServiceProperties aiServiceProperties;
    private final GenerationTaskMapper taskMapper;
    private final ChatMessageMapper chatMessageMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public AiProxyController(AiServiceProperties aiServiceProperties,
                             GenerationTaskMapper taskMapper,
                             ChatMessageMapper chatMessageMapper) {
        this.aiServiceProperties = aiServiceProperties;
        this.taskMapper = taskMapper;
        this.chatMessageMapper = chatMessageMapper;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/v1/poetry/chat/session — 创建会话（本地生成 UUID，无需代理）
    // Spec: AI Service create_session 仅返回 uuid4，无需网络往返
    // ──────────────────────────────────────────────────────────────────────────
    @PostMapping("/chat/session")
    public ResponseEntity<Map<String, Object>> createSession() {
        return ResponseEntity.ok(Map.of("code", 200,
                "data", Map.of("session_id", UUID.randomUUID().toString())));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/v1/poetry/chat — 对话 SSE 代理（完成后持久化聊天记录）
    // ──────────────────────────────────────────────────────────────────────────
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@RequestBody String body, HttpServletRequest httpRequest) {
        Long userId = (Long) httpRequest.getAttribute("authenticatedUserId");
        String aiUrl = aiServiceProperties.getBaseUrl() + "/ai/api/v1/chat";

        // 从请求体中提取 message 和 session_id 用于持久化
        String userMessage = "";
        String sessionId = "";
        try {
            JsonNode bodyNode = objectMapper.readTree(body);
            userMessage = bodyNode.path("message").asText("");
            sessionId = bodyNode.path("session_id").asText("");
        } catch (Exception ignored) {}

        return proxyChatSse(aiUrl, body, userId, userMessage, sessionId);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/v1/poetry/chat/messages — 查询当前用户的对话历史
    // ──────────────────────────────────────────────────────────────────────────
    @GetMapping("/chat/messages")
    public ResponseEntity<Map<String, Object>> listChatMessages(
            HttpServletRequest httpRequest,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize) {

        Long userId = (Long) httpRequest.getAttribute("authenticatedUserId");

        LambdaQueryWrapper<ChatMessage> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ChatMessage::getUserId, userId)
               .orderByDesc(ChatMessage::getGmtCreate);

        List<ChatMessage> allMessages = chatMessageMapper.selectList(wrapper);

        int total = allMessages.size();
        int fromIdx = Math.min((page - 1) * pageSize, total);
        int toIdx = Math.min(fromIdx + pageSize, total);

        List<Map<String, Object>> items = allMessages.subList(fromIdx, toIdx).stream()
                .map(m -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", m.getId());
                    item.put("sessionId", m.getSessionId() != null ? m.getSessionId() : "");
                    item.put("userMessage", m.getUserMessage() != null ? m.getUserMessage() : "");
                    item.put("aiReply", m.getAiReply() != null ? m.getAiReply() : "");
                    item.put("createdAt", m.getGmtCreate() != null ? m.getGmtCreate().toString() : "");
                    return item;
                })
                .collect(Collectors.toList());

        return ResponseEntity.ok(Map.of(
                "code", 200,
                "data", Map.of(
                        "total", total,
                        "page", page,
                        "pageSize", pageSize,
                        "items", items
                )
        ));
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

        Thread worker = new Thread(() -> {
            // 用于分镜完成时写历史
            String firstImageUrl = null;

            try {
            // 在真正连 AI 之前立刻回首包，避免首访时前端无事件导致“连接中”长时间停留
            emitter.send(SseEmitter.event().data(
                "{\"type\":\"thinking\",\"content\":\"后端代理已接收请求，正在连接模型服务...\"}",
                MediaType.TEXT_PLAIN));

                HttpClient client = HTTP_CLIENT;

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
                // T026: AI Service 不可达时 5s 内（connectTimeout=5s）快速返回友好错误
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
        }, "sse-proxy-worker");
        worker.setDaemon(true);
        worker.start();

        return emitter;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 对话专用 SSE 代理（收集 AI 回复 token 并持久化）
    // ──────────────────────────────────────────────────────────────────────────
    private SseEmitter proxyChatSse(String targetUrl, String requestBody,
                                    Long userId, String userMessage, String sessionId) {
        SseEmitter emitter = new SseEmitter(180_000L);

        Thread worker = new Thread(() -> {
            StringBuilder aiReplyBuilder = new StringBuilder();
            try {
                emitter.send(SseEmitter.event().data(
                    "{\"type\":\"thinking\",\"content\":\"后端代理已接收请求，正在连接模型服务...\"}",
                    MediaType.TEXT_PLAIN));

                HttpClient client = HTTP_CLIENT;

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
                        if (!trimmed.startsWith("data:")) continue;
                        String data = trimmed.substring(5).trim();

                        emitter.send(SseEmitter.event().data(data, MediaType.TEXT_PLAIN));

                        // 收集 token 类型的文本用于持久化
                        if (data.startsWith("{")) {
                            try {
                                JsonNode node = objectMapper.readTree(data);
                                String type = node.path("type").asText();
                                if ("token".equals(type)) {
                                    String content = node.path("content").asText("");
                                    aiReplyBuilder.append(content);
                                }
                            } catch (Exception ignored) {}
                        }

                        if ("[DONE]".equals(data)) break;
                    }
                }

                // SSE 完成后持久化对话记录
                saveChatMessage(userId, sessionId, userMessage, aiReplyBuilder.toString());

                emitter.complete();

            } catch (java.net.ConnectException | java.net.http.HttpConnectTimeoutException e) {
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
        }, "sse-chat-worker");
        worker.setDaemon(true);
        worker.start();

        return emitter;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 持久化一轮对话到 sys_chat_message
    // ──────────────────────────────────────────────────────────────────────────
    private void saveChatMessage(Long userId, String sessionId, String userMessage, String aiReply) {
        try {
            ChatMessage msg = new ChatMessage();
            msg.setUserId(userId);
            msg.setSessionId(sessionId != null ? sessionId : "");
            msg.setUserMessage(userMessage != null ? userMessage : "");
            msg.setAiReply(aiReply != null ? aiReply : "");
            msg.setGmtCreate(LocalDateTime.now());
            chatMessageMapper.insert(msg);
            log.info("Chat message saved: userId={}, sessionId={}", userId, sessionId);
        } catch (Exception e) {
            log.error("Failed to save chat message: userId={}", userId, e);
        }
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
