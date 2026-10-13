# 从每日跟写到完整项目

已有LLMPort、delegate、Retry、Deadline、ResearchTask和Evidence继续保留。完整参考分支扩展了它们；学习时每次先做一个业务结果，再看成品如何处理复杂条件。

| 阶段 | 先亲手完成的结果 | 再参考 |
| --- | --- | --- |
| P1 | 人工资料→Claim→核对→报告 | application的claims/verification/reports |
| P2 | PDF按页定位，再检索正确原文 | parsers、ingestion、retrieval |
| P3 | 网页创建任务、看进度、接受知识 | API、Web、KnowledgeService |
| P4 | 强杀后恢复，取消后拒绝迟到 | Worker、fence、预算、LangGraph |
| P5 | 解释故障、量化误判和消耗 | OTel、evaluation、CI |

先读application/research.py，沿调用走进Extractor、Verifier和ReportBuilder。拿supported/contradicted两例讲清数据变化，再亲手核对页字符串切片。

每轮应有可运行结果、关键故障、一个小修改与架构解释。测试证明这些行为；不能用增加多少测试代替学习进度。
