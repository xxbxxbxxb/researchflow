# 恢复与评测各自保证什么

LangGraph恢复的是工作流状态，StepReceipt保护的是业务提交。二者分别持久化，恰好会有“业务提交成功，checkpoint尚未保存”的窗口。重入节点先查凭据，返回已有业务结果，才能让这一窗口可恢复。

Worker的旧请求可能在新Worker接管后返回。单靠取消旧协程不能保证远端停止，因此每次数据库写入还要检查owner、epoch、lease和cancel。检查与写入必须在同一个事务，先检查后另开事务会留下竞态。模型调用本身仍可能重复收费，不能用 checkpoint宣称外部 exactly-once。

工程测试使用可复现模型输出和故障点，验证原子性、权限、重试和恢复机制。质量评测使用有来源的 gold标签，测试真实模型能否判断证据关系。固定演示把答案预先放在provider里，能够验证流程，却无法测量模型能力。

支持精确率等于正确的 supported预测数除以全部 supported预测数；把反驳或不足误标支持必须进入分母。没有任何 supported预测时，精确率是未知，不是100%。失败和inconclusive也不能从总体完成率与错误分析中删除。

先使用开发集改策略，再冻结策略、检查保留集。每次修改都记录源码、Prompt、模型和数据哈希。真正值得写进简历的，是你发现了哪个误判或故障、采用什么取舍，以及独立数据或真实重启怎样证明了改进。

参考思想：LangGraph的状态与checkpoint，LiteLLM的调用治理，Temporal的恢复/副作用边界，OpenAI Agents SDK的工具授权，OpenTelemetry的父子Span，DSPy的指标驱动优化。本项目实现了适合单人规模的对应机制，没有因此要求部署所有平台。

## 故障实验与面试追问

给专用`_test`数据库配置`RF_TEST_DATABASE_URL`后，运行`tests/e2e/test_worker_restart.py`和`tests/integration/test_run_fencing.py`。前者实际在业务提交后终止子进程，后者使旧owner在新epoch接管后提交。无数据库时skip意味着实验没做，不能把它当成恢复成功。自己的小修改：将故障点从Evidence提交后改到Report提交后，核对run_id不变、epoch增加、报告只有一个版本，而且已消耗调用不清零。

一个最小指标实验可以检查“不作supported预测”的边界，完整样例在`tests/unit/test_evaluation_metrics.py`。这里先用自然语言手算：4条原本应该被支持的主张全部预测成inconclusive时，总分母仍是4，完成率与准确率不能删去这4条；supported precision没有可计算的预测分母，应为null而非100%。再用评测输出核对这三个字段，才能理解固定分母为什么重要。

面试追问一：checkpoint为什么不足以保证报告只生成一次？它与业务提交存在持久化窗口，重入必须用原子业务StepReceipt识别已经提交的结果。追问二：Worker被取消为什么还需要epoch/fence？取消不保证外部请求停止，远端响应仍可能迟到；新owner接管后旧响应没有数据库写入权。
