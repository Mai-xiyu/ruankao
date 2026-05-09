# 架构记忆

## 目标

系统定位为多科目软考题库，不再以网络工程师作为唯一业务中心。题库按 `高级 / 中级 / 初级` 三个级别组织，每个级别下有多个 `subjects`。

## 数据模型

- `subjects` 是前端科目展示和后端过滤的主入口。
- `exams.subject_id` 关联科目，`exam_name` 仅保留兼容和导入批次语义。
- `questions` 增加来源和质量字段：`source_provider`、`source_question_id`、`source_url`、`quality_status`、`requires_image`。
- `users` 和 `auth_sessions` 提供注册、登录和访客 session。
- `user_records`、`favorites` 同时支持 `user_id` 和 `guest_session_id`，记录按账号或访客隔离。

## 数据质量

前端题库页和刷题默认只使用：

```text
quality_status=ok
has_answer=true
```

清理接口会先备份，再隔离或删除无答案、缺选项、缺图、题干过短、未校对 AI 草稿等低质量题。

## try-learning

try-learning 首页是 SPA 外壳，v1 不绕过登录、付费、验证码或反爬限制。项目支持两种合规路径：

- 读取公开 JSON 响应并做质量门槛。
- 用浏览器监听公开流程中的 JSON/XHR 响应，保存原始响应后再结构化。

当前公开 JSON 没有答案字段，默认只生成草稿，不入库。

## AI

DeepSeek 是可选能力。未配置 API Key 时普通题库和用户系统仍可运行。AI 生成或结构化结果默认 `is_verified=false`，不能直接当作已校对真题。
