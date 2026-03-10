package com.poetry.constant;

/**
 * Spec: .specify/memory/constitution.md §3.3
 * 任务状态枚举，仅允许 PENDING | PROCESSING | COMPLETED | FAILED
 */
public enum TaskStatus {
    PENDING,
    PROCESSING,
    COMPLETED,
    FAILED
}
