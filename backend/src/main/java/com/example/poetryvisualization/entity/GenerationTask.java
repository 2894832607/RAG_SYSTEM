package com.example.poetryvisualization.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 生图任务实体 — 对应 sys_generation_task 表
 * 状态机: PENDING(0) → COMPLETED(1) / FAILED(2)
 */
@Data
@TableName("sys_generation_task")
public class GenerationTask {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 分布式任务追踪ID(UUID) */
    private String taskId;

    /** 关联用户ID，未登录时为 null */
    private Long userId;

    /** 用户输入的原始古诗句 */
    private String originalPoem;

    /** RAG 检索到的现代文译文/知识 */
    private String retrievedText;

    /** 最终注入 SD 模型的正向提示词 */
    private String enhancedPrompt;

    /** 生成图像访问路径 */
    private String resultImageUrl;

    /** 任务状态: 0=排队/生成中, 1=成功, 2=失败 */
    private Integer taskStatus;

    /** 失败时的异常原因 */
    private String errorMessage;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime gmtCreate;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime gmtModified;

    // ---------- 状态常量 ----------
    public static final int STATUS_PENDING   = 0;
    public static final int STATUS_COMPLETED = 1;
    public static final int STATUS_FAILED    = 2;
}
