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
    private String resultImageUrl;         // 向后兼容：第一张图片（主图）
    private String resultImageUrls;        // JSON 数组：所有生成的图片 URLs（新字段）
    private String resultVideoUrl;         // 视频生成结果 URL
    private String taskType;               // 任务类型：IMAGE / VIDEO
    private String poemExplanation;
    private LocalDateTime createdAt;
}
