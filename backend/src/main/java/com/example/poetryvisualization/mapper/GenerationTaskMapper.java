package com.example.poetryvisualization.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.poetryvisualization.entity.GenerationTask;
import org.apache.ibatis.annotations.Mapper;

/**
 * 生图任务 Mapper — 继承 BaseMapper 即拥有全部 CRUD 能力
 */
@Mapper
public interface GenerationTaskMapper extends BaseMapper<GenerationTask> {
}
