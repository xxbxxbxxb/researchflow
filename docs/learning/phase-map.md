# 从跟写到完整参考实现

你已经在每日跟写中接触模型适配、delegate、Retry、Deadline、ResearchTask 和 Evidence。这条分支保留旧 LLMPort 和用例，完整成品用新业务对象扩展它们。学习时每次先完成一个可观察的业务结果，再读成品在更复杂条件下如何处理它。

| 阶段 | 你应该先亲手完成的结果 | 再参考成品 |
| --- | --- | --- |
| P1 | 人工资料生成主张，逐项核对，再生成报告 | claims、verification、reports 与 CLI |
| P2 | 导入 PDF，按页定位，再检索正确原文 | parsers、ingestion、PostgresRetriever |
| P3 | 网页中创建任务，看进度，接受知识与后续草稿 | API、Web、KnowledgeService |
| P4 | 杀死进程后继续，取消后拒绝迟到输出 | Worker、fence、预算、LangGraph |
| P5 | 解释一次失败，量化误判与模型消耗 | OTel、evaluation、CI |

第一次阅读从 `application/research.py` 开始，沿调用进入 ClaimExtractor、ClaimVerifier、ReportBuilder。先拿固定 supported 与 contradicted 两个例子，把实际数据变化讲清楚。接着读取一页 PDF与 EvidenceAnchor，亲手检查字符串切片。

不要一次复制整套框架。先理解业务规则，再对照一次实际失败：例如引用 ID合法但数字不符、数据库已提交但进程被杀、模型输出已经交付一半后断线。完成之后再讲为什么成熟版本需要凭据、fence 或流式提交边界。

每轮验收应该有可运行行为、关键故障、你自己的一个小修改和一段架构解释。测试用来证明这些行为；不能把学习进度等同于增加了多少测试。
