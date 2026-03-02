package com.example.poetryvisualization.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户收藏实体 — 对应 sys_favorite 表
 */
@Data
@TableName("sys_favorite")
public class Favorite {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 用户ID */
    private Long userId;

    /** 收藏的任务ID */
    private String taskId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime gmtCreate;
}
