# 验收证据

工程测试、固定演示、真实连接和真实质量分别报告。工具记录实际命令、返回码、时间和日志。JUnit failure/error是failed，skip是blocked，缺失场景是not_run；固定demo不代表模型质量。

RF_TEST_DATABASE_URL仅用于名称以_test结尾的专用数据库，测试会重置业务表。A01–A16覆盖原文定位、反驳、伪引用/项目边界、材料不足、原子回滚、重试、取消/迟到、进程恢复、ownership、SSE/UI状态、知识/取代/后续、恶意指令、非法来源、无Key和持久重启。映射见批准实施计划。

CI四个核心任务覆盖Ubuntu/Windows与Python3.11/3.12。PostgreSQL任务执行真实pgvector、迁移、Worker故障与Chromium；Compose任务从锁文件和固定镜像实际构建，并在数据库/API/Worker重启后读取同一Blob、报告、知识和checkpoint。

verify_release --existing-results只拼装当前CI已生成的报告，不能称为重跑。单个数据库任务拿不到另一个Compose任务的报告时A16会保留not_run；完整结论需同时核对两项证据。

真实支持精确率0.90是目标；SciFact子集评估给定abstract下的验证，不代表完整科研搜索或中文论文效果。保留集重复使用会削弱泛化估计，应在实验里说明。
