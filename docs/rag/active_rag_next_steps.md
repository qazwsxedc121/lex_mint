# lex_mint Active RAG 下一步计划（2026-02-19）

## 1. 当前结论

主动式 RAG 的 P0 主链路已落地并可用：

1. 检索前 query planner（multi-query + fallback）
2. 结构化 source 注入（可配置开关）
3. 工具式 RAG（`search_knowledge` / `read_knowledge`，按 assistant 绑定 KB 动态注入）
4. 工具轮次上限后的最终收敛回答（避免半截输出）

---

## 2. 当前主要短板

1. 缺少质量门禁：评测指标阈值尚未固化，CI 无自动阻断
2. 工具轨迹仍可优化：存在重复 search、证据型问题 read 触发不稳定
3. 权限模型偏轻：KB 级 ACL 与跨会话访问边界未系统化
4. 数据源并轨不足：附件/网页与 KB 结果尚未完全统一到同一 source/citation 协议

---

## 3. 建议执行顺序

## Sprint 1（评测先行）

1. 固化基线阈值：Recall@K、MRR、citation hit rate
2. 建立真实问题回归集（不显式提示 function call）
3. 接入 CI：低于阈值直接阻断

## Sprint 2（工具质量）

1. 证据型请求增强 read 策略（原文/出处/逐字引用优先 read）
2. 重复 search 抑制（相似 query 限次）
3. 增加工具链路诊断字段（read 触发率、重复查询率、收敛轮次）

## Sprint 3（能力扩展）

1. 统一附件/网页/KB 的 source 协议与引用渲染
2. 设计并落地 KB ACL（owner/read/write 或 assistant scope）
3. 轻量 query intent routing（factual/analytical 分流策略）

---

## 4. 完成标准（下一阶段）

1. 真实问题回归集中，主动式链路稳定输出完整回答，无半截结束
2. 证据型问题中 `read_knowledge` 触发率达到预期阈值
3. 评测指标进入 CI，回归可自动发现质量退化
4. ACL 与统一 source 协议在至少一个端到端链路验证通过
