package com.poetry.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.poetry.constant.TaskStatus;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("sys_generation_task")
public class GenerationTask {
    @TableId(type = IdType.ASSIGN_UUID)
    private String taskId;
    private Long userId;
    private String originalPoem;
    private TaskStatus taskStatus;
    private String resultImageUrl;
    private String poemExplanation;
    private LocalDateTime createdAt;
}
