package com.poetry.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.poetry.entity.GenerationTask;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface GenerationTaskMapper extends BaseMapper<GenerationTask> {
}
