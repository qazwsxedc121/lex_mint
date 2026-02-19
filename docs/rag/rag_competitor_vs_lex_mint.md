# RAG 横向对比与当前策略（LibreChat / LobeHub / OpenWebUI / lex_mint）

> 更新日期：2026-02-19

## 1. 当前判断

lex_mint 已完成主动式 RAG 基础能力，不再处于“缺功能”阶段，当前重点应从“补功能”转为“提质量 + 做治理”。

---

## 2. 与三家方案的对齐情况

| 维度 | LibreChat | LobeHub | OpenWebUI | lex_mint 当前 |
|---|---|---|---|---|
| 工具式 RAG | file_search | search + read | 有工具与注入并轨 | 已有 search_knowledge + read_knowledge |
| 检索前查询规划 | 以工具触发为主 | 以工具触发为主 | retrieval query generation | 已有 query planner |
| 结构化 source 注入 | 有 | 有 | `<source>` + template | 已有 SourceContextService + 开关 |
| 混合检索能力 | 侧重向量 | 侧重向量 | 向量 + hybrid + rerank | 向量 + BM25 + hybrid + rerank |
| 权限治理 | 较完整 | 较完整 | access control 体系 | 仍偏轻量，ACL 待补 |

---

## 3. 现在真正的差距

1. **质量门禁不足**：缺统一阈值与 CI 自动阻断
2. **工具链路效率不足**：重复 search 与证据型问题 read 触发不稳定
3. **权限治理不足**：KB 访问边界与 ACL 还不完整
4. **多来源并轨不足**：附件/网页与 KB 的 source/citation 协议尚未完全统一

---

## 4. 下一步计划（建议）

### Sprint 1：评测与门禁

1. 固化 Recall@K / MRR / citation hit rate 阈值  
2. 建立真实问题回归集（禁止显式 function-call 提示）  
3. 接入 CI gate

### Sprint 2：主动式工具质量

1. 证据型请求优先 read  
2. 重复 search 抑制  
3. 增加工具轨迹诊断（read 触发率、重复率、收敛轮次）

### Sprint 3：治理与扩展

1. 统一附件/网页/KB 的 source 协议和引用渲染  
2. 设计并落地 KB ACL  
3. 轻量 query intent routing

---

## 5. 结论

当前 lex_mint 的方向已经正确：主动式主链路具备。下一阶段不要再做“竞品功能追平”，而要做“质量稳定化与治理能力建设”。
