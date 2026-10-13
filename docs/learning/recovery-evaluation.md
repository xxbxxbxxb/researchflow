# 恢复与评测

LangGraph恢复工作流状态，StepReceipt保护业务提交。业务已经提交、checkpoint尚未保存的窗口，靠重入节点查凭据来恢复。

旧请求会在新Worker接管后返回，所以取消之外还要在同一事务检查owner、epoch、lease和cancel。模型调用可能重复收费，checkpoint不能保证远端exactly-once。

工程测试使用固定输出和故障点验证机制，质量评测用有来源的gold测真实判断。固定Provider预放答案，能测流程，不能测模型能力。

支持精确率=正确supported/全部supported，假支持不能从分母删除。没有supported预测时精确率未知；failed和inconclusive留在固定分母与误例中。

开发集改策略，冻结后检验保留集，记录数据、源码、Prompt和模型版本。简历应说明真实故障/误判、工程取舍和独立验证证据。

参考LangGraph状态、LiteLLM治理、Temporal副作用边界、Agents SDK授权、OTel父子Span、DSPy指标驱动思想；只实现当前项目需要的机制。
