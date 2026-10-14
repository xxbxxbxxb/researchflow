# 验收证据与边界

工程测试、固定演示、真实连接和模型质量分别报告。验收工具记录实际命令、返回码、时间、版本和日志，不填写预设“通过多少项”。JUnit中的 failure/error 是 failed，skip 是 blocked，缺失场景是 not_run。固定演示始终标 demo；未配置真实 Key 的质量运行是 not_run。

`researchflow validate --scope engineering` 实际执行后端、lint、类型与前端检查。真实浏览器需要 `RF_TEST_DATABASE_URL`，数据库名必须以 `_test` 结尾，测试夹具会重置其中业务表。不要把生产数据库配置给测试。

A01–A16 的文件映射记录在批准的实施计划中。当前覆盖包括中文 PDF位置、反驳、跨项目/伪引用、材料不足、批量回滚、重试、取消/迟到、进程恢复、ownership fence、SSE/UI状态、知识/后续/取代、恶意资料指令、非法来源、无Key和持久服务重启。原文 quote、canonical page和 offsets 必须一起核对。

CI中，四个核心任务分别验证 Ubuntu/Windows 与 Python3.11/3.12；Linux PostgreSQL任务执行真实 pgvector、迁移、恢复和 Chromium；Compose任务从锁文件和固定镜像实际构建服务，并在重启数据库/API/Worker后查询同一原文件、报告、知识和 checkpoint。Artifacts 保留实际 XML/JSON与必要截图。

`--existing-results` 只拼装当前 CI已生成的报告，不能用于声称重新执行了检查。单个 PostgreSQL任务拿不到另一个 Compose任务的报告时，会明确留下 A16 not_run，完整结论应同时检查两个任务。最终 release记录会列明各 gate，不把缺少环境当作通过。

真实模型支持精确率0.90尚属目标。SciFact子集只评估给定 abstract下的主张验证；不能把它直接解释为完整科研搜索、中文论文或生产用户满意度。重复使用保留集会削弱泛化评估，必须在实验记录中说明。
