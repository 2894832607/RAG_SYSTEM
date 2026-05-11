-- 添加 resultImageUrls 字段支持多图显示
-- 执行时间：2026-03-29

-- 1. 添加新字段
ALTER TABLE sys_generation_task 
ADD COLUMN result_image_urls TEXT COMMENT '所有生成的图片 URLs（JSON 数组格式）';

-- 2. 将现有的 result_image_url 数据同步到 result_image_urls（单元素数组）
UPDATE sys_generation_task 
SET result_image_urls = CONCAT('["', result_image_url, '"]')
WHERE result_image_url IS NOT NULL 
  AND result_image_url != ''
  AND (result_image_urls IS NULL OR result_image_urls = '');

-- 验证
SELECT task_id, result_image_url, result_image_urls 
FROM sys_generation_task 
LIMIT 5;
