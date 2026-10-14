# 从资料到可核对的结论

一份 PDF是原始来源；解析后的某一页字符串是保存的 canonical page；检索 Chunk负责找到可能相关的位置。Evidence在这份保存快照上绑定页码、字符起止和 quote_hash。它必须回到同一个字符串，不能靠后来重新解析的换行或网页的新内容猜位置。

Claim是一个原子事实判断。它提出哪些 Evidence可能支持自己，Verifier再检查 ID与项目归属、原文位置和实际支持关系。引用存在只是第一层；“样本12人”的原文不会因为附了一个合法ID就支持“样本999人”。模型的语义判断也会受到数值、单位和限定条件规则的保守检查。

supported表示当前材料支持，contradicted表示材料反驳，insufficient表示材料不足，inconclusive表示验证过程无法确定。报告只把 supported放入结论区，其他判断仍保留在发现与待解决问题中。一个完整的“材料不足”报告可以是成功执行，并不意味着完成了可信事实判断。

知识需要人工接受。接受记录保存人、时间、Verification、Report版本和原始 Evidence。人工改判建立新版本并写原因；新材料可以提出取代候选，用户确认后才取代旧知识。后续任务读取的知识是带来源的项目数据，仍要根据当前选中的 Evidence重新验证，不是不可质疑的系统指令。

检验代码时，先改变一个 offset，观察原文完整性检查失败；再保持合法 offset但把 Claim数字改错，观察支持判断受限。这两次实验把引用正确与语义受到支持分开。

最后的独立审查还揭示了更隐蔽的错误：原文写“仅在小鼠中，剂量5 mg/kg”，主张改成5 g/kg或删去小鼠条件，裸数字集合仍相同。因此verify-v2核对数值与单位的绑定，并对识别到的显式限制做负面检查。它只能指出冲突、不能凭相同词语证明蕴含；保守规则可以产生需要人工复核的inconclusive。

另一个容易遗漏的细节是知识的判断方向。“这个主张被反驳了”也是可以保存的审阅结果，不能只向下一次模型发送主张原句。collect提交凭据现在保存verification_status、原因、真正接受的Evidence IDs以及原文锚点。所有这些引用都必须属于本次冻结的资料范围；旧报告中的无关段落不能让一条知识获得使用资格。

## 最小实验与面试追问

先在安装后的Python中运行这个最小实验。它只演示负面核对，不调用模型：

```python
from researchflow.application.verification_rules import conservative_checks

source = 'The treatment improved survival by 20% only in mice at 5 mg/kg.'
claim = 'The treatment improved survival by 20% at 5 g/kg.'
issues = conservative_checks(claim, (source,))
assert 'unit_binding_mismatch' in issues
assert 'experimental_condition_missing' in issues
```

把claim改回source原句后，issues应该为空。但这只说明这两个负面检查未发现问题，不说明任意主张被证明。完整调用、原文锚点和报告结论排除行为见`tests/unit/test_claim_verification.py`。自己的小修改：增加“数字相同但分别绑定到剂量和时间”的案例，先让旧的裸数字策略失败，再解释为什么绑定关系不能用集合包含代替。

面试追问一：为什么不能直接把检索Chunk当Evidence？Chunk会随分块策略变化，也未必包含一个完整判断；Evidence必须绑定保存快照与准确quote/offset，作为可复核引用账本。追问二：人工改判后为什么不能更新原Verification行？覆盖会破坏报告当时的依据与审阅历史；新Verification和新Report版本保留旧记录，知识是否被取代仍需要显式接受。
