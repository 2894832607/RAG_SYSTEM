package com.example.poetryvisualization.exception;

/**
 * 资源未找到异常 — 触发 GlobalExceptionHandler 返回 HTTP 404
 * <p>
 * Spec: specs/features/poetry-visualization/tasks.md T002
 */
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String message) {
        super(message);
    }
}
