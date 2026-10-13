# 恢复和故障边界

任务可有多次运行，每次固定输入清单。崩溃恢复沿用run_id，主动重新研究创建新run_id。认领、续租和每次提交检查数据库里的owner/epoch/lease/cancel。

业务输出和StepReceipt一起提交。业务提交后、checkpoint前崩溃时，重入节点先查凭据，返回已有结果。Checkpoint、pending writes和工具登记也在同一事务内fence，先检查后另开事务保存不能避免竞态。

五秒租约，每秒heartbeat。接管增加epoch，旧Worker的迟到结果不能写回。取消传播到协程、HTTP和PDF解析子进程；远端继续计算也无权提交。真实进程实验在evidence/report提交后杀死子进程，再恢复。

锁定的数据库活跃时钟避免Worker/预览重复计时，单次操作的Deadline用本地monotonic。崩溃片段保守计至旧租约结束；人工审阅等待不计活跃时间。

代码、关键依赖、模型或策略不兼容时创建新运行。保守指纹可能拒绝兼容的小修，这是保持来源可追踪的代价；旧报告、知识和原文仍能查看。

外部调用不是exactly-once。Provider成功与本地提交之间失败，恢复可能再次收费。提交凭据保护本地业务，不保证远端只调用一次。
