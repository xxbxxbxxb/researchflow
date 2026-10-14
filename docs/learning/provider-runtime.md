# Provider 和 Runtime 为什么分开

Provider把一种真实服务的协议转换成统一消息、工具调用和 Usage。一次调用只发送一次 HTTP请求。认证错误、临时服务错误和不合法输出分别分类，调用者提供的 HTTPClient不会被适配器擅自关闭。

Runtime决定是否重试、还能花多少次请求、什么时候超时、取消怎样传递以及哪一次尝试应该记录。把这些策略放到这一层，JSON修复、验证、Agent规划和 embedding query才能共享同一个运行预算。否则多个SDK或装饰器同时重试，会把一个逻辑请求放大成许多收费请求。

429后Retry-After如果超出剩余 Deadline，运行结束；不能把服务端要求120秒悄悄缩成1秒，也不能等待到任务预算之外。一次未知的网络结果已经可能产生费用，所以预留的请求数不会退款。

试着阅读 `ModelRuntime._complete`：先检查上下文容量和活跃预算，再争取并发位置，每次实际发送前原子预留调用预算，调用结束后保存 Usage，finally释放位置。取消是控制信号，会继续向上抛，而不是归入可重试错误。

流式输出增加另一条边界。role或空帧还没有交付内容，可以重试；交付文本后发生故障，只能明确标记 incomplete。把另一份从头生成的内容追加进去，会污染用户已经看到的语义。预览和正式报告分开，验证与业务提交决定最终报告。

面试时可以解释：为什么单个模型接口不能负责任务预算？为什么重试后成本可能大于成功请求的 Usage？停止浏览器进度订阅与取消研究有什么区别？这三题都应该从实际请求和资源所有权说起。
## 最小预算实验与面试追问

先观察一次实际的预算预留，而不是只记住“最多16次请求”。下面是同一不可变预算值的两次消费；第二次必须在发送上游前失败：

```python
from researchflow.domain.usage import BudgetExceededError, RunBudget, RunLimits

budget = RunBudget(limits=RunLimits(max_model_calls=1))
budget = budget.reserve('model')
assert budget.model_calls_used == 1
try:
    budget.reserve('model')
except BudgetExceededError:
    print('第二次请求没有发送资格')
else:
    raise AssertionError('预算限制被绕过')
```

成品不能只把这个值放在内存里：两个并发调用、Worker重启和预览进程都要在同一个数据库事务中预留。查看`tests/integration/test_model_runtime.py`中429→503→成功和并发第17次请求被拒绝的实际契约。自己的小修改：将max_model_calls收紧为2，观察三次尝试的请求链不能发送到最终成功响应，并核对已记录的两个attempt没有消失。

面试追问一：模型超时为什么不退还已消耗调用？超时只说明客户端没有拿到完整结果，远端可能已计算并收费；退还会让重试突破真实请求上限。追问二：为什么不能在Provider、装饰器和框架各重试一次？多层重试会相乘放大请求，也不能统一解释deadline与费用；成品只有Runtime决定是否重试，Provider负责一次请求及错误分类。
