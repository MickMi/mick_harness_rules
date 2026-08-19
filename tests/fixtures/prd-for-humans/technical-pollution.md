# 错误示例：账户页改版

## 实现方案

修改 `src/pages/Account.tsx`，新增 `UserProfileCard` 组件，通过 REST API 读取 `user_id` 字段并写入 PostgreSQL。

## AI 交付

System Prompt 必须执行 Reasoning Pipeline，并按 JSON Schema 输出 Data Contract。
