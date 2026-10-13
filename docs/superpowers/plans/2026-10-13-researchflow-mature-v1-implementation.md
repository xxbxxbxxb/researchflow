# ResearchFlow Mature V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可实际使用的单人科研工作台，完成研究任务、可定位证据、主张验证、报告、项目知识和后续任务的闭环，并验证重启恢复、取消、预算与质量边界。

**Architecture:** 在原有 Python 模块化单体上兼容扩展。领域实体及业务事务保持框架独立，API/Worker/Web 组成可操作产品；先运行固定阶段与 Minimal ReAct，再用带所有权校验的 LangGraph Checkpointer 驱动同一流程。

**Tech Stack:** Python 3.11/3.12、HTTPX、FastAPI/Pydantic 2、SQLAlchemy 2/Alembic、PostgreSQL/pgvector、LangGraph、React/TypeScript/Vite、OpenTelemetry、pytest/Ruff/mypy/Playwright。

**Spec:** `docs/superpowers/specs/2026-10-13-researchflow-mature-v1-design.md`（用户于 2026-10-13 批准）

## Global Constraints

- 代码基线固定为 `268160c88d9ab67fb314eb3b01f87fcfffe9e743`，完整成品位于 `reference/mature-v1`；不改每日跟写分支、不合并 Agent Reliability Lab。
- Python 3.11 兼容；CI 至少运行 Python 3.11/3.12；保留 `LLMPort.generate(LLMRequest) -> LLMResponse` 及旧教学用例。
- Domain 不导入 FastAPI、HTTPX、SQLAlchemy 或 LangGraph；Application 只依赖 Domain 与 Ports。
- 问题最大 5,000 字符；上传默认最大 20 MiB，PDF 默认最大 200 页；检索默认取 8 个候选。
- 每运行最多 12 个 Agent 决策步、20 次工具调用、16 次实际上游模型请求（包含 Retry、修复与验证调用）、4 个并发外部操作。
- 活跃运行 Deadline 300 秒，单次逻辑模型操作最多 60 秒；预算跨恢复保留，人工审阅等待不计活跃时间。
- Claim 验证状态只有 supported、contradicted、insufficient、inconclusive；引用有效不等于语义受到支持。
- Evidence 同 ID 同内容幂等，同 ID 不同内容冲突，批量提交原子；业务结果与步骤成功凭据同一事务。
- 输入/源码/Prompt/策略版本不兼容时创建新运行；崩溃恢复保持同一 run_id 并增加所有权代次。
- 取消或所有权过期后不得提交业务结果或 checkpoint；不吞 CancelledError；外部模型调用不承诺 exactly-once。
- UTC 保存时间，单调时钟计单进程耗时；项目查询强制 project_id；API Key 不进入 repr/日志/Trace/前端。
- Web 中文、代码与接口英文；刷新保持滚动、筛选、展开状态和编辑输入；断开进度订阅不自动取消研究。
- 工程测试、固定演示、真实模型效果与真实连接冒烟分别报告；没有凭据或环境时标记 not_run/blocked。
- 质量集至少 24 个独立案例，开发集 12、保留集 12；真实模型 Claim 支持精确率目标至少 0.90，展示分母、误例与混淆矩阵。
- 不新增多租户、支付、OCR、任意 Shell、自动邮件、公开发布、微服务、Redis、ES、Temporal 服务或付费云资源。
- 每项任务先写关键失败行为测试并实际看见失败，再实现与验证。低影响文档/样式修改不写镜像实现的测试。
- 计划获批后连续完成 P1–P5；阶段验收是技术检查，不再次请求用户批准常规可逆开发操作。

## Review Focus

1. 中文 PDF 的物理页、Unicode 规范化和 quote 偏移必须对应同一保存快照，不能因解析/换行变化引用错位（Task 2、7）。
2. Worker 在提交后、checkpoint 前崩溃，或者租约过期后迟到，不能产生重复报告或覆盖新结果（Task 9、14、16）。
3. 恶意 URL 的重定向、DNS 重绑定、IPv4-mapped IPv6、压缩超限必须在实际网络连接与写文件之前阻断（Task 7）。
4. 刷新、SSE 重连、多个页面重复启动和 Cookie/CSRF 异常不能重复提交任务或丢失 UI 状态（Task 10、12）。
5. 实验条件/单位丢失、模型拒答/空输出/工具参数损坏、Usage 缺失及真假演示模式不能悄悄转换为 verified（Task 3、4、13、17、18）。

---

## 执行前提与分支处理

本轮事实：GitHub 登录为 `xxbxxbxxb`；GitHub App 安装列表与已安装账号列表为空；插件本身已安装；创建远端分支返回 403 `Resource not accessible by integration`。当前主机有 Git/Node/npm/uv，但没有 gh、Docker、psql、Python 3.11 可执行文件；Python 3.12 尚未安装本项目的 HTTPX/pytest。

用户完成 GitHub 应用及仓库授权后，先读最新默认分支与目标参考分支。目标分支不存在则从固定基线创建；已存在则读取其 head，比较现有改动后继续，不能强制覆盖。只有参考分支的快进写入允许自动执行，任何合并回每日跟写分支都不属于本计划。

若授权尚未修复：在隔离目录使用已下载的基线源码快照进行实现，建立本地 Git 分支并保存 provenance；不能声称这种本地初始提交继承了远端完整历史。交付完整 Git 项目/变更包，之后从原基线应用到远端参考分支。权限问题不阻止本地规划与实现。

实施时使用 using-git-worktrees 建立隔离工作区。只有实施获批后才安装项目依赖或搭建运行服务。依赖下载失败时使用允许的包源或已配置缓存，不绕过网络策略；PostgreSQL/Compose 本地不可用时在已授权 GitHub 分支的 CI 中运行真实数据库与 Compose 验收。无法实际执行的项目必须报告 blocked，不能以 SQLite/Mock 替代声称 PostgreSQL 已验收。

## 文件与接口地图

| 路径 | 责任 |
| --- | --- |
| `src/researchflow/domain/research.py` | 保留已有 ResearchTask/Evidence 类型 |
| `src/researchflow/domain/{sources,claims,reports,projects,knowledge,runs}.py` | 新的不可变实体及业务不变量 |
| `src/researchflow/ports/{model,sources,repositories,retrieval,runtime,telemetry}.py` | 框架独立契约 |
| `src/researchflow/application/{evidence,claims,verification,reports,ingestion,retrieval,projects,knowledge,research}.py` | 按业务责任组织的服务 |
| `src/researchflow/infrastructure/llm/` | 保留旧适配器；新增 Chat/Tools/Usage/Embedding/Streaming |
| `src/researchflow/infrastructure/storage/` | SQLAlchemy、迁移映射、Repository、内容寻址文件存储 |
| `src/researchflow/infrastructure/sources/` | PDF/Text/HTML、安全 HTTP 获取、arXiv |
| `src/researchflow/runtime/` | 固定阶段、Worker、预算、工具、ReAct、LangGraph、Checkpointer |
| `src/researchflow/api/` | 路由、单用户认证、SSE、异常映射 |
| `src/researchflow/{composition,cli}.py` | 客户端及资源生命周期、CLI |
| `migrations/` | 版本化 PostgreSQL/pgvector 迁移 |
| `web/src/` | 项目、资料、任务、报告、知识和运行界面 |
| `tests/{unit,contract,integration,e2e}/` | 分层行为验证；保留原 tests 文件 |
| `evaluation/` | 标签集、评测驱动、指标与误例 |
| `examples/` | 已标注的固定演示资料与结果 |
| `docs/{adr,learning,operations}/` | 关键取舍、跟写路径、运行恢复手册 |

### 共享类型

所有类型在负责它的 Task 中定义，后续不能自行重命名。集合采用不可变 tuple，JSON 边界的可变数据由 Pydantic 验证后转换。

- Task 2 定义 `SnapshotPage(number: int, text: str)`、`SourceSnapshot(snapshot_id, project_id, source_uri, content_hash, pages, parser_version, fetched_at)`、`EvidenceAnchor(snapshot_id, page, start, end, normalization_version)` 和 `AnchoredEvidence(evidence: Evidence, project_id, anchor, quote_hash, extractor_version)`。偏移均为已保存 NFC/统一换行页面字符串的零起点字符偏移，end 排他。
- Task 3 定义 `Claim(claim_id, task_id, project_id, text, proposed_evidence_ids, qualifiers)`；每次提取最多 12 条，单条 text 最大 2,000 字符。
- Task 4 定义 `Verification(verification_id, claim_id, status, accepted_evidence_ids, rationale, checks, verifier_version, model_metadata, verified_at)`；人工改判创建新 Verification 并保存 supersedes_id 和 actor。
- Task 5 定义 `ResearchResult(project_id, task_id, run_id, report: ReportVersion, claims, verifications, evidences, unresolved_questions)`。
- Task 3 在 `domain/projects.py` 定义 `Project(project_id, name, background)`、`TaskRecord(task_id, project_id, question, source_ids, parent_task_id)`，Task 6 增加持久化；已有 ResearchTask 保持教学接口。
- Task 9 定义 `RunHandle(run_id, project_id, task_id, epoch, owner_id)` 与 `StepReceipt(run_id, step_key, output, committed_at)`；epoch 属于所有权，不从旧 checkpoint 状态读取。
- Task 13 定义 `RunLimits(max_steps=12, max_tool_calls=20, max_model_calls=16, max_concurrency=4, active_timeout_seconds=300, operation_timeout_seconds=60)`、`RunBudget` 与 `ModelUsage`。

配套边界类型：Task 2在`domain/errors.py`定义EvidenceConflict/ProjectBoundaryError；Task 3在ports/model定义ChatRequest/ChatResponse，在domain/tool_calls定义ToolCall，在domain/usage定义ModelUsage，qualifiers为不可变tuple；Task 5在domain/reports定义ReportInputs（project_id/task_id/run_id/claims/verifications/evidences/unresolved_questions）；Task 7在ports/sources定义SourceInput/FetchedSource/ParsedDocument/SourceCandidate/PreparedSource/SourceAccessDeniedError；Task 9在domain/runs定义RunState/RunRecord/RunOutcome/StepOutput/LeaseState/ReviewDecision，在ports/runtime定义RunOwnershipLostError/RunCancelledError/InputVersionMismatchError；Task10在domain/access定义Principal，在settings.py定义Settings；Task13在runtime/budget定义BudgetSnapshot/BudgetExceededError；Task15在domain/tool_calls定义ToolResult/CollectionResult并在runtime/tools定义ToolAuthorizationError；Task17在ports/model定义ModelDelta并在runtime/streaming定义StreamInterruptedError；Task18在ports/telemetry定义Scalar/SpanHandle/RuntimeFailure；Task19在evaluation/dataset定义EvalCase/Prediction/EvaluationReport/Metrics。第三方RunnableConfig/CheckpointTuple仅在Runtime适配器使用，不泄露到Domain。

工具调用统一使用domain/tool_calls的ToolCall，ports/model引用同一类型，不能创建第二套同名但字段不同的ToolCall。ModelUsage统一定义在domain/usage.py，Task13增加持久化而不重定义。BudgetSnapshot包含model_calls_used/tool_calls_used/steps_used/active_elapsed_seconds；ModelUsage的未知token或estimated_cost为None，不能用0代替未知。FollowUpDraft包含draft_id/project_id/parent_task_id/question/claim_ids/started_run_id（默认None）；KnowledgeEntry包含knowledge_id/project_id/verification_id/report_id/accepted_by/accepted_at/status/supersedes_id。

ReportVersion包含report_id/project_id/task_id/run_id/version/markdown/conclusion_claim_ids/finding_claim_ids/source_evidence_ids/execution_mode/created_at。conclusion_claim_ids只来自supported，finding_claim_ids保留其它判断，API报告查询返回完整ResearchResult bundle以便展开证据。Task6的Repository另提供`get_result(project_id: str, report_id: str) -> ResearchResult`和`get_evidence(project_id: str, evidence_id: str) -> AnchoredEvidence | None`，Task2的内存Ledger提供`get(project_id: str, evidence_id: str) -> AnchoredEvidence | None`。

数据库表名固定为projects/research_tasks/source_snapshots/snapshot_pages/chunks/evidences/claims/claim_evidence_links/verifications/report_versions/workflow_runs/step_receipts/run_events；后续迁移增加knowledge_entries/follow_up_drafts/tool_receipts/run_budgets/model_usage/graph_checkpoints/graph_writes。每张项目资料表保存project_id并采用组合外键/唯一约束，不能只在API过滤。

测试夹具在对应Task的测试文件或`tests/conftest.py`中先构建，只依赖此前Task已实现的实体/契约；断言代码中的existing/new/conflicting等名称对应本步骤已描述的固定样例。Task1的fixed_utc为2015-10-21T07:27:58Z。所有展示的测试代码是待实现计划，未在本轮运行，不是测试结果。

模型输入额外采用保守的16,000字符材料预算（非token保证），生成前按实际Provider配置的context_window与tokenizer/估算器预留4,096输出token；不能确定上下文容量时配置必须给出容量或拒绝live运行。报告与知识中保留源内容不受模型截断影响，model inputs记录实际选入的Evidence IDs。字符预算属于实现默认限制，可配置，但不得伪称token使用的精确值。

## P1：可运行的证据业务闭环

### Task 1:兼容保留旧 LLM 调用并修复已观察到的运行边界

**Files:** Modify `pyproject.toml`、`src/researchflow/infrastructure/llm/{retry_llm,openai_compatible,errors}.py`；Create `src/researchflow/infrastructure/llm/retry_after.py`、`tests/contract/test_provider_hardening.py`、`uv.lock`、`docs/operations/baseline.md`。

**Interfaces:** Consumes existing LLMPort、LLMRequest、LLMResponse；Produces `parse_retry_after(value: str | None, now: datetime) -> float | None`，保持 RetryLLM/OpenAICompatibleLLM 现有构造参数及行为。

- [ ] **Step 1 — 固定隔离源码与依赖：** 记录基线 SHA；增加 dev 中 pytest-asyncio、Ruff、mypy；用 uv 在 Python 3.11/3.12 目标下解析并锁定依赖。实际安装后运行旧 `python -m pytest -q`，记录真实基线；失败先定位，不删除测试。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
with pytest.raises(ValueError):
    RetryLLM(delegate=provider, base_delay_seconds=float("inf"))
assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT", now=fixed_utc) == 2.0
assert "secret-test-key" not in repr(config)
```

- [ ] **Step 2 — 写失败测试：** `test_retry_rejects_nonfinite_delay` 参数 nan/inf/-inf 均 raise ValueError；`test_retry_after_http_date` 用固定 UTC 时间得到 2.0；`test_retry_after_rejects_infinity` 返回 None；`test_config_repr_redacts_key` 断言 `'secret-test-key' not in repr(config)`；外部取消不进入第二次调用。
- [ ] **Step 3 — 看见失败：** `python -m pytest tests/contract/test_provider_hardening.py -q`；预期新用例在旧实现失败，不接受 fixture/import 错误代替业务失败。
- [ ] **Step 4 — 最小修复：** 有限非负延迟校验、RFC HTTP-date 解析、注入时间、api_key 字段 repr=False；保持现有失败分类和借用 HTTP Client 的所有权规则。
- [ ] **Step 5 — 验证并提交：** 新契约、全套旧测试与 `python -m researchflow.demo` 实际通过；`git add` 上述文件并提交 `fix: harden provider configuration and retry boundaries`。

### Task 2:带原文锚点的不可变 Evidence 与原子 Ledger

**Files:** Create `domain/{sources,errors}.py`、`ports/repositories.py`、`application/evidence.py`、`infrastructure/storage/memory_evidence.py`、`tests/unit/test_evidence_ledger.py`；所有 Python 路径均相对 `src/researchflow/`，测试路径相对仓库根目录。

**Interfaces:** Consumes old Evidence；Produces共享 SourceSnapshot/AnchoredEvidence 类型，`EvidenceLedger.add_batch(project_id: str, items: tuple[AnchoredEvidence, ...]) -> tuple[AnchoredEvidence, ...]`，`validate_anchor(item: AnchoredEvidence, snapshot: SourceSnapshot) -> None`。

- [ ] **Step 1 — 写失败测试：** 同 ID 同内容重复返回同一个逻辑记录；同 ID 不同 quote 抛 EvidenceConflict；第二条冲突后第一条新增也不存在；跨项目快照抛 ProjectBoundaryError；中文 CRLF/NFC 固定样例的 `page.text[start:end] == evidence.text`，修改一个偏移必须失败。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
ledger.add_batch(project_id, (existing,))
with pytest.raises(EvidenceConflict):
    ledger.add_batch(project_id, (new_evidence, conflicting_existing))
assert ledger.get(project_id, new_evidence.evidence.evidence_id) is None
assert snapshot.pages[0].text[good.anchor.start:good.anchor.end] == good.evidence.text
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/unit/test_evidence_ledger.py -q`，确认缺失的是目标行为。
- [ ] **Step 3 — 实现实体与 Ledger：** quote_hash 与保存页面校验；稳定 ID 来自项目、快照、页、偏移、quote_hash、extractor_version；批处理先完整预检再应用，不修改 caller 的对象。手动资料生成标为 manual 的快照，保留原 source/locator 作为来源注释。
- [ ] **Step 4 — 验证：** 单元测试和旧 Prepare/Answer 测试；手动材料不能被标成已抓取的真实网页。
- [ ] **Step 5 — 提交：** `feat: add immutable anchored evidence and atomic ledger`，只 stage 本任务文件。

### Task 3:结构化 Claim 提取与一次修复的明确边界

**Files:** Create `domain/{claims,projects,usage,tool_calls}.py`、`ports/model.py`、`application/claims.py`、`infrastructure/llm/chat_model.py`、`tests/contract/test_claim_extraction.py`、`tests/contract/test_chat_model.py`。

**Interfaces:** Consumes AnchoredEvidence；Produces Claim，`ChatModelPort.complete(request: ChatRequest) -> ChatResponse`，`ClaimExtractor.extract(task: TaskRecord, evidences: tuple[AnchoredEvidence, ...]) -> tuple[Claim, ...]`。ChatRequest 包含 messages、可选 tools/response_schema；ChatResponse 包含 text、tool_calls、model、request_id、usage；旧 LLMPort 不变。

- [ ] **Step 1 — 写失败测试：** 固定返回两个原子 Claim、去重相同 Claim；超过 12 条/2,000 字符、非法 JSON、未知引用或跨任务 ID 被拒绝；一次坏 JSON→修复后成功耗两次调用，两次坏 JSON 不进行第三次；空输出/拒答产生明确错误，不转为 supported。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
claims = await extractor.extract(task, evidences)
assert len(claims) == 2
assert all(set(c.proposed_evidence_ids) <= allowed_ids for c in claims)
with pytest.raises(ValueError):
    await unknown_citation_extractor.extract(task, evidences)
assert malformed_provider.calls == 2
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/contract/test_claim_extraction.py tests/contract/test_chat_model.py -q`。
- [ ] **Step 3 — 实现：** Provider 使用独立 system/user 消息，资料作为数据；Infrastructure用Pydantic校验Provider响应边界，Application只用标准库JSON及领域dataclass校验Claim payload，不能引入Pydantic/HTTPX。一个显式修复入口，修复调用经过同一个 ChatModelPort；保存模型/Prompt版本。TaskRecord 在 Task 6 才落库，先定义于 `domain/projects.py` 供内存用例使用。
- [ ] **Step 4 — 验证：** MockTransport 检查实际请求体、tools、模型拒答/缺失 Usage；`generate` 仍通过旧测试。
- [ ] **Step 5 — 提交：** `feat: extract typed atomic claims from evidence`。

### Task 4:引用、锚点和语义关系分层验证

**Files:** Create `application/verification.py`、`application/verification_rules.py`、`tests/unit/test_claim_verification.py`；Extend `domain/claims.py`。

**Interfaces:** Consumes Claim、AnchoredEvidence、SourceSnapshot、ChatModelPort；Produces Verification，`ClaimVerifier.verify(claims: tuple[Claim, ...], evidences: tuple[AnchoredEvidence, ...], snapshots: tuple[SourceSnapshot, ...]) -> tuple[Verification, ...]`。

- [ ] **Step 1 — 写失败测试：** 样本 12 却声明 999 不可 supported；“只在中文”被改成“所有语言”不可 supported；同一主张同时有支持和反驳保留冲突；无证据为 insufficient，Provider 失败为 inconclusive；伪引用/损坏 quote/跨项目引用在语义调用之前阻断。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
results = await verifier.verify((claim_999,), (evidence_12,), (snapshot_12,))
assert results[0].status != "supported"
empty = await verifier.verify((claim_999,), (), ())
assert empty[0].status == "insufficient"
assert identity_error_model_calls == 0
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/unit/test_claim_verification.py -q`，明确复现旧 Answer 只能检查别名的差距。
- [ ] **Step 3 — 实现：** 先校验身份和原文，再以最多 4 个 Claim 一批调用语义验证器；返回必须绑定原 claim_id、允许的 evidence_id 和具体原文。数字/单位/限定条件规则仅做保守否决或不确定升级，不把词匹配作为支持证明；规则与模型矛盾时不可 supported。
- [ ] **Step 4 — 验证：** 四种状态及理由保留；任何没有完成的验证不计语义正确；单元/契约全量运行。
- [ ] **Step 5 — 提交：** `feat: verify claim support beyond citation membership`。

### Task 5:可追溯报告与完整 CLI 演示

**Files:** Create `domain/reports.py`、`application/reports.py`、`application/research.py`、`cli.py`、`examples/{supported,contradicted,insufficient,invalid-citation}.json`、`tests/unit/test_report_builder.py`、`tests/e2e/test_research_cli.py`；Modify `pyproject.toml` entry point。

**Interfaces:** Consumes ClaimExtractor、ClaimVerifier、EvidenceLedger；Produces ReportVersion、ResearchResult，`ResearchService.run_manual(task: TaskRecord, snapshots: tuple[SourceSnapshot, ...], evidences: tuple[AnchoredEvidence, ...], run_id: str) -> ResearchResult`，`ReportBuilder.build(result_inputs: ReportInputs) -> ReportVersion`。

- [ ] **Step 1 — 写失败测试：** 只有 supported Claim 进入有依据的回答；contradicted/insufficient/inconclusive 分区保留；每个结论能解析回 Claim/Verification/Evidence；没有证据也得到有效报告；未知引用不能生成成功报告。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
report = report_builder.build(mixed_report_inputs)
assert report.conclusion_claim_ids == (supported_claim.claim_id,)
assert contradicted_claim.claim_id in report.finding_claim_ids
assert set(report.source_evidence_ids) <= known_evidence_ids
assert insufficient_result.report.conclusion_claim_ids == ()
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/unit/test_report_builder.py tests/e2e/test_research_cli.py -q`。
- [ ] **Step 3 — 实现：** 报告正文由验证后的 Claim 确定性构建，禁止添加无 Claim 对应的新事实。CLI `researchflow demo --case supported --format json` 和 `researchflow research --input PATH --mode live|demo`；demo 必须输出 `execution_mode=demo`，live 未配置模型必须失败，不自动使用 Fake。
- [ ] **Step 4 — 验证 P1：** 四个固定案例实际执行，检查 JSON 与 Markdown 输出、退出码；保留原 Day1 Demo；记录基线到完整闭环的差异。
- [ ] **Step 5 — 提交：** `feat: deliver traceable research reports and end-to-end CLI`。

## P2：真实资料、检索与持久化

### Task 6:PostgreSQL 权威 Repository、快照存储与迁移

**Files:** Create `infrastructure/storage/{database,models,repositories,blob_store}.py`、`migrations/env.py`、`migrations/versions/0001_research_entities.py`、`alembic.ini`、`compose.yaml`、`tests/integration/test_research_repository.py`、`.env.example`。

**Interfaces:** Consumes Task 2–5 实体；Produces `ResearchRepository.create_project(project: Project) -> Project`、`save_task(task: TaskRecord) -> None`、`add_evidence_batch(project_id, items) -> tuple[AnchoredEvidence, ...]`、`save_result(result: ResearchResult) -> None`、`get_report(project_id, report_id) -> ReportVersion`；`BlobStore.put(data: bytes) -> str`、`get(content_hash: str) -> bytes`。

- [ ] **Step 1 — 写失败测试：** 实际 PostgreSQL 的唯一约束与整批冲突回滚；跨项目同 ID 不串数据；重新建立 Engine 后结果仍在；内容哈希存储重复不产生不同文件；DB失败不能暴露未提交快照。Session每异步任务独立，不能共享正在使用的 AsyncSession。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
with pytest.raises(EvidenceConflict):
    await repository.add_evidence_batch(project_a, (new_evidence, conflicting_existing))
assert await repository.get_evidence(project_a, new_evidence.evidence.evidence_id) is None
assert (await reopened_repository.get_report(project_a, report_id)).report_id == report_id
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/integration/test_research_repository.py -q` 必须连接真实临时数据库；无数据库就 blocked，不能 skip 后宣称通过。
- [ ] **Step 3 — 实现：** PostgreSQL 16/pgvector 镜像先核对可取得标签并在锁定清单记录摘要；采用 SQLAlchemy 2 AsyncSession + psycopg；资料先写临时文件并原子改名、事务内登记归属；未引用 Blob 可回收，不能作为可见 Document。迁移建立 Project/Task/Snapshot/Page/Chunk/Evidence/Claim/Link/Verification/Report 及版本/归属外键。
- [ ] **Step 4 — 验证：** `alembic upgrade head`、测试、`alembic downgrade base`、再次 upgrade，确认外键/索引和相同数据重启查询；必要时通过 CI 数据库服务执行。
- [ ] **Step 5 — 提交：** `feat: persist research artifacts with transactional repositories`。

### Task 7:可定位的文件解析、安全网页获取与 arXiv 搜索

**Files:** Create `ports/sources.py`、`application/ingestion.py`、`infrastructure/sources/{parsers,safe_http,arxiv}.py`、`tests/unit/test_document_parsing.py`、`tests/contract/test_safe_fetch.py`、`tests/contract/test_arxiv.py`；测试资料放 `tests/fixtures/sources/`。

**Interfaces:** Produces `DocumentParser.parse(data: bytes, mime_type: str) -> ParsedDocument`、`SourceFetcher.fetch(url: str) -> FetchedSource`、`SourceSearch.search(query: str, limit: int = 8) -> tuple[SourceCandidate, ...]`、`IngestSource.prepare(project_id: str, source: SourceInput) -> PreparedSource` 与 `IngestSource.execute(project_id: str, source: SourceInput) -> SourceSnapshot`。prepare只写内容寻址Blob，不登记可见业务实体；execute用于已授权的人工导入并事务登记。ParsedDocument 包含 normalized pages/parser_version；FetchedSource 包含原/最终 URL、bytes、media_type、时间。

- [ ] **Step 1 — 写失败测试：** UTF-8 中文 CRLF 与两页文字 PDF 页码/quote 正确；20 MiB+1 和201页拒绝；空/损坏/扫描 PDF 提供 parse_failed 或 unsupported_scan；文件名 `../../outside` 不写出 Blob目录；拒绝 localhost、私网、link-local、metadata、IPv4-mapped IPv6；public→private重定向、DNS目标变化、gzip解压超限均不发生被禁止访问。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
assert parser.parse(two_page_pdf, "application/pdf").pages[1].number == 2
with pytest.raises(SourceAccessDeniedError):
    await fetcher.fetch("http://127.0.0.1/private")
assert network_connect_spy.calls == 0
with pytest.raises(ValueError):
    parser.parse(b"x" * (20 * 1024 * 1024 + 1), "text/plain")
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/unit/test_document_parsing.py tests/contract/test_safe_fetch.py tests/contract/test_arxiv.py -q`。
- [ ] **Step 3 — 实现：** PDF采用pypdf，文本/Markdown采用UTF-8严格解码，HTML移除script/style并保存标题/块文本。安全获取器最多5次重定向、连接5秒、读取30秒、解压后20 MiB；transport使用核验后的IP建立连接，同时保留正确Host/SNI和TLS验证，禁止“预检一次后让HTTPX重新DNS”的实现。DNS/transport是可注入契约以便验证。arXiv使用官方API、Atom解析、合规请求间隔与固定返回schema；失败返回分类错误。
- [ ] **Step 4 — 验证：** 外部连接只在标识为live的冒烟中发生；用解析结果生成Evidence，再验证原文位置；快照保存原始文件与canonical extracted pages。
- [ ] **Step 5 — 提交：** `feat: ingest anchored documents and safely fetch research sources`。

### Task 8:按项目隔离的混合检索与 Embedding 版本

**Files:** Create `ports/retrieval.py`、`application/retrieval.py`、`infrastructure/llm/embeddings.py`、`infrastructure/storage/retrieval.py`、`migrations/versions/0002_retrieval_vectors.py`、`tests/integration/test_hybrid_retrieval.py`、`tests/contract/test_embedding_provider.py`。

**Interfaces:** Produces `EmbeddingPort.embed(texts: tuple[str, ...]) -> EmbeddingBatch`、`Retriever.search(project_id: str, query: str, source_ids: tuple[str, ...], top_k: int = 8) -> RetrievalResult`、`EvidenceSelector.select(candidates: RetrievalResult) -> tuple[AnchoredEvidence, ...]`。EmbeddingBatch 保存向量/模型/维度；RetrievalResult 保存候选、mode、embedding_version。

- [ ] **Step 1 — 写失败测试：** 中文和英文已标注段落排进top8；另一个项目的相同文字不返回；同页重叠Chunk去重；Embedding缺失时mode=lexical；向量维度/模型变更拒绝旧索引混用；无结果不会生成虚构Evidence。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
result = await retriever.search(project_a, "中文实验样本", source_ids, top_k=8)
assert len(result.candidates) <= 8
assert all(c.project_id == project_a for c in result.candidates)
assert lexical_only_result.mode == "lexical"
assert lexical_only_result.embedding_version is None
```

- [ ] **Step 2 — 看见失败：** 实际pgvector测试及Mock HTTP契约执行；仅固定向量fixture测试检索机制，不能宣称语义效果。
- [ ] **Step 3 — 实现：** 按页/段落切800字符、重叠100，长段保持原文offset；英文全文与中文Unicode字符trigram词法检索组合，向量cosine检索，RRF融合常数60；统一project/source过滤。将Embedding模型、维度和index_version作为索引命名空间，缺失不静默生成随机“语义向量”。
- [ ] **Step 4 — 验证 P2：** 实际导入PDF→检索→Evidence→Claim→报告，重新打开数据库与Blob目录后仍可定位；报告记录实际检索模式。
- [ ] **Step 5 — 提交：** `feat: add project-scoped hybrid retrieval and evidence selection`。

## P3：可操作的完整科研工作台

### Task 9:持久运行与步骤提交凭据，固定业务阶段 Worker

**Files:** Create `domain/runs.py`、`ports/runtime.py`、`runtime/{fixed_workflow,worker}.py`、`infrastructure/storage/run_repository.py`、`migrations/versions/0003_runs_steps_events.py`、`tests/integration/test_step_commit.py`、`tests/e2e/test_fixed_worker.py`。

**Interfaces:** Consumes ResearchRepository、ResearchService、IngestSource、Retriever；Produces RunHandle/StepReceipt，`RunRepository.enqueue(task_id: str, project_id: str, input_version: str) -> RunRecord`、`claim_next(owner_id: str) -> RunHandle | None`、`get_receipt(handle: RunHandle, step_key: str) -> StepReceipt | None`、`commit_step(handle: RunHandle, step_key: str, output: StepOutput) -> StepReceipt`、`finish(handle: RunHandle, state: RunState) -> RunRecord`；`FixedWorkflow.execute(handle: RunHandle) -> RunOutcome`、`Worker.run_once() -> bool`。

- [ ] **Step 1 — 写失败测试：** 两个Worker只能认领一个queued run；步骤提交与Evidence/Claim/Report保存同时成功或失败；同step_key重入返回receipt不重复写业务对象；report版本只能递增；未知project/epoch拒绝。run inputs保存source、model/prompt/parser/workflow版本。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
first, second = await asyncio.gather(repo_a.claim_next("w1"), repo_b.claim_next("w2"))
assert sum(x is not None for x in (first, second)) == 1
receipt_a = await repository.commit_step(handle, "report", report_output)
receipt_b = await repository.commit_step(handle, "report", report_output)
assert receipt_a == receipt_b
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/integration/test_step_commit.py tests/e2e/test_fixed_worker.py -q`（真实数据库）。
- [ ] **Step 3 — 实现：** Run表含owner/epoch/lease_until/cancel_requested/input_manifest，Step有唯一(run_id,step_key)，Event有稳定递增id。认领使用行锁与SKIP LOCKED，提交在事务里核验epoch/租约/cancel标志，并一起保存业务对象和receipt/event。运行节点使用固定键collect/retrieve/evidence/claims/verify/report。Report步骤提交时run仍running，driver结束或暂停完成后再finish，避免最后checkpoint写入被提前终态阻止。
- [ ] **Step 4 — 验证 P3 后端基础：** `researchflow worker --once` 对资料库中的task产生完整报告；空资料产出不足报告；以新的Engine查询同run得到相同receipt。一次新run和一次恢复不能混淆。
- [ ] **Step 5 — 提交：** `feat: run research stages with durable commit receipts`。

### Task 10:API、单用户访问控制、幂等启动与可重连 SSE

**Files:** Create `api/{app,schemas,auth,projects,sources,tasks,runs,reports,events}.py`、`composition.py`、`settings.py`、`domain/access.py`、`tests/contract/test_api_authorization.py`、`tests/integration/test_task_api.py`、`tests/integration/test_event_stream.py`、`migrations/versions/0004_sessions_idempotency.py`。

**Interfaces:** Produces `create_app(settings: Settings) -> FastAPI`、Composition生命周期。路由：POST/GET `/api/projects`，POST/GET `/api/projects/{project_id}/sources`，POST/GET `/api/projects/{project_id}/tasks`，POST `/api/tasks/{task_id}/runs`，GET `/api/runs/{run_id}`，POST cancel/resume/review，GET `/api/runs/{run_id}/events`，GET `/api/reports/{report_id}`、`/api/evidence/{evidence_id}` 与原始快照。所有归属通过登录身份和服务端查询校验。

- [ ] **Step 1 — 写失败测试：** 未登录写操作在repository调用前401；错误Origin/CSRF在副作用前403；相同Idempotency-Key和payload只建立一个run，换payload409；问题5000允许5001拒绝；Cookie HttpOnly/SameSite，登录失败限流；SSE携带Last-Event-ID只补缺失事件，断开不cancel run。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
response = await anonymous_client.post(f"/api/tasks/{task_id}/runs", json={})
assert response.status_code == 401
assert enqueue_spy.call_count == 0
assert first_start.json()["run_id"] == duplicate_start.json()["run_id"]
assert changed_payload_response.status_code == 409
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/contract/test_api_authorization.py tests/integration/test_task_api.py tests/integration/test_event_stream.py -q`。
- [ ] **Step 3 — 实现：** 单用户密码由环境提供Argon2id哈希，使用argon2-cffi校验并在线程中完成CPU工作；不透明随机session id由secrets生成，DB保存session摘要/过期时间，Cookie只存token。写操作校验Session+CSRF+Origin；登录每来源每分钟最多5次失败并持久记录，session默认8小时，登录并发最多2；默认不信任用户提交的X-Forwarded-For。文件入口使用bounded ASGI receive与逐块读取，file内容20 MiB上限，multipart请求容许额外64 KiB，不能先把无限body读入再检查。启动run用(project_id,key,payload_hash)数据库幂等表；error schema `{code,message,request_id,details}`不含secret。SSE事件含id/event/data，15秒heartbeat，页查询和订阅共用project权限，慢客户端不占无限队列；无事件保留裁剪的V1支持任意已有cursor重连。
- [ ] **Step 4 — 验证：** lifespan复用并关闭自有HTTP Client/Engine，不关闭借用资源；健康检查检查DB和迁移；访问live mode时无模型配置返回configuration_missing。文档给本地loopback和Compose方式。
- [ ] **Step 5 — 提交：** `feat: expose authenticated research APIs and resumable events`。

### Task 11:知识审阅、改判、版本取代与后续任务

**Files:** Create `domain/knowledge.py`、`application/knowledge.py`、`api/knowledge.py`、`migrations/versions/0005_project_knowledge.py`、`tests/integration/test_project_knowledge.py`；Extend `api/runs.py` 与 `ports/repositories.py`。

**Interfaces:** Produces `KnowledgeService.accept(project_id: str, verification_id: str, actor: str) -> KnowledgeEntry`、`override(project_id: str, verification_id: str, status: VerificationStatus, reason: str, actor: str) -> Verification`、`supersede(project_id: str, old_id: str, new_verification_id: str, actor: str) -> KnowledgeEntry`、`draft_follow_up(project_id: str, parent_task_id: str, question: str, claim_ids: tuple[str,...]) -> FollowUpDraft`；API POST accept/override/supersede/follow-ups，GET project knowledge。

- [ ] **Step 1 — 写失败测试：** 接受只针对当前supported Verification并记录人/时间/报告/证据；重复accept幂等；跨项目拒绝；override不删除原判断；新反驳资料只提出取代候选，用户确认后旧知识superseded；follow-up保留parent/claim关系但不自动启动模型调用。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
entry = await knowledge.accept(project_a, supported.verification_id, actor="owner")
again = await knowledge.accept(project_a, supported.verification_id, actor="owner")
assert entry.knowledge_id == again.knowledge_id
assert entry.verification_id == supported.verification_id
assert draft.parent_task_id == parent_task_id
assert model.calls == 0
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/integration/test_project_knowledge.py -q`。
- [ ] **Step 3 — 实现：** Knowledge保留出处版本，历史查询不因superseded丢失；检索知识时可查active和历史但明确状态，返回原Evidence可审计。人工改判必须非空reason，记录新Verification；report新版本引用新判断。run在awaiting_review时可用户完成审阅，固定driver直接finish succeeded，LangGraph driver后续使用持久review decision恢复。
- [ ] **Step 4 — 验证：** 同项目后续task读取知识及其原始证据；反驳旧知识不会悄悄修改历史报告；人工审阅期间无模型后台执行。
- [ ] **Step 5 — 提交：** `feat: preserve reviewed project knowledge and follow-up lineage`。

### Task 12:Web 完整操作路径与不会跳回页首的进度更新

**Files:** Create `web/package.json`、`web/package-lock.json`、`web/vite.config.ts`、`web/tsconfig.json`、`web/src/{main,App}.tsx`、`web/src/lib/{api,events,queryKeys}.ts`、`web/src/pages/{Login,Projects,Project,Task,Report,Run}.tsx`、`web/src/components/{SourceUpload,EvidenceDrawer,ClaimCard,RunProgress,KnowledgeReview}.tsx`、`web/src/styles.css`、`web/playwright.config.ts`、`web/e2e/research.spec.ts`、`web/e2e/state-preservation.spec.ts`。

**Interfaces:** Consumes实际API/OpenAPI；Produces项目/资料/任务/报告/知识/运行界面。API类型从已实现OpenAPI生成，不自行写另一套字段名。页面URL `/projects`、`/projects/:id`、`/tasks/:id`、`/reports/:id`、`/runs/:id`。

- [ ] **Step 1 — 写失败浏览器场景：** 登录→项目→上传PDF→创建/启动→看到进度→报告→查看原文→接受知识→建follow-up；非法引用报告不显示verified；SSE进来时滚动仍在原位置、EvidenceDrawer仍展开、未提交问题输入仍保留；刷新和双击启动仍只有一个run；浏览器back保留筛选。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```typescript
await expect(page.getByRole('button', { name: '查看原文' }).first()).toBeVisible();
await page.getByRole('button', { name: '查看原文' }).first().click();
await expect(page.getByTestId('evidence-drawer')).toBeVisible();
expect(Math.abs((await page.evaluate(() => window.scrollY)) - originalScrollY)).toBeLessThan(2);
await expect(page.getByLabel('研究问题')).toHaveValue(unsavedQuestion);
```

- [ ] **Step 2 — 看见失败：** `npm --prefix web run test:e2e` 对实际API/Worker/DB与固定demo provider运行；目标缺失行为失败，不能只截图静态页。
- [ ] **Step 3 — 实现：** React/TypeScript/Vite，Node至少22.12；TanStack Query管理数据，Router管理可打开链接，局部SSE更新对应query。视图采用固定key和局部更新，不触发整页reload；URL存筛选，组件保持输入/抽屉，导航恢复scroll。报告清楚呈现证据不足/冲突/验证受限和demo/live模式；登录session自动失效回登录，前端没有模型secret。
- [ ] **Step 4 — 验证 P3：** `npm --prefix web ci`、`npm --prefix web run typecheck`、`npm --prefix web run build`、浏览器E2E；视觉检查桌面/窄屏，逐项通过真实操作。Web build由API或独立静态服务同源提供，开发代理保持相同API语义。
- [ ] **Step 5 — 提交：** `feat: deliver an evidence-first research workspace`。

## P4：受限 Agent、统一预算与真正的恢复

### Task 13:跨重试/修复/验证共享的预算、Usage 与成本

**Files:** Create `runtime/{budget,model_runtime}.py`、`infrastructure/storage/budget_repository.py`、`migrations/versions/0006_run_budgets_usage.py`、`tests/unit/test_run_budget.py`、`tests/integration/test_model_runtime.py`；Extend `domain/usage.py`、`ports/model.py` 与 provider adapters。

**Interfaces:** Produces RunLimits/RunBudget/ModelUsage，`BudgetRepository.reserve(handle: RunHandle, resource: Literal['model','tool','step'], amount: int = 1) -> BudgetSnapshot`、`ModelRuntime.complete(handle: RunHandle, request: ChatRequest) -> ChatResponse`、`record_usage(handle, attempt_id: str, usage: ModelUsage) -> None`；所有模型入口经过ModelRuntime，Provider适配器只发一次请求。

- [ ] **Step 1 — 写失败测试：** 429→503→成功实际计3次upstream、最多3attempt默认；第17次模型请求在发送前阻断；JSON repair、验证与tool planning共用16上限；并发请求不能越限；Retry-After 120秒而operation余1秒立即deadline/budget失败，不提前忽视Retry-After；usage缺失为null，未设置价格成本null而非0；secret不进入记录。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
for _ in range(16):
    await runtime.complete(handle, request)
with pytest.raises(BudgetExceededError):
    await runtime.complete(handle, request)
assert provider.calls == 16
assert response_without_usage.usage is None
assert usage_without_price.estimated_cost is None
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/unit/test_run_budget.py tests/integration/test_model_runtime.py -q`。
- [ ] **Step 3 — 实现：** 每次发送前在DB事务预留预算且不因未知网络结果退款，最多4外部并发；operation timeout=min(60,run remaining)，重试只有一层，Full Jitter上限30秒且不得越Deadline。默认每批4Claim保证正常场景有验证预算，检索Agent进入前预留后续验证的最小额度；不足时受限结束。记录attempt/Usage与版本化可选price config，估算成本明确estimated。
- [ ] **Step 4 — 验证：** 固定时钟/随机/sleeper进行可复现contract，但至少一个实际asyncio cancellation/timeout场景验证资源；恢复读取已使用counter。
- [ ] **Step 5 — 提交：** `feat: enforce durable model budgets and attempt usage`。

### Task 14:租约、取消传播、过期结果隔离与进程重启恢复

**Files:** Create `runtime/{leases,cancellation,recovery}.py`、`tests/integration/test_run_fencing.py`、`tests/e2e/test_worker_restart.py`、`tests/e2e/test_cancel_late_result.py`；Extend Worker/RunRepository、run migration和API resume。

**Interfaces:** Produces `RunRepository.heartbeat(handle: RunHandle) -> LeaseState`、`request_cancel(project_id: str, run_id: str) -> RunRecord`、`recover_expired(owner_id: str) -> RunHandle | None`、`resume(project_id: str, run_id: str, expected_input_version: str) -> RunRecord`。RunHandle epoch每次重新认领递增；所有DB提交都消费此handle。

- [ ] **Step 1 — 写失败测试：** subprocess Worker在Evidence commit后被terminate，新进程跳过已提交step；在Report commit后driver完成前崩溃，不增加第二份Report；旧handle在new epoch后不能写Evidence/receipt/event；cancel后Provider迟到不能提交，外部Task取消不吞；恢复计数不归零；不同input version拒绝resume并要求new run。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
assert recovered_handle.run_id == old_handle.run_id
assert recovered_handle.epoch > old_handle.epoch
with pytest.raises(RunOwnershipLostError):
    await repository.commit_step(old_handle, "report", late_report_output)
assert recovered_budget.model_calls_used == before_crash_budget.model_calls_used
assert reports_after_restart == 1
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/integration/test_run_fencing.py tests/e2e/test_worker_restart.py tests/e2e/test_cancel_late_result.py -q`，故障点使用显式test hooks，不用难复现的random sleep。
- [ ] **Step 3 — 实现：** DB时钟租约5秒、heartbeat每1秒；提交时行锁核验owner/epoch/lease/cancel；后台cancel watcher传播到HTTP与子Task并清理自有资源。heartbeat保存active_elapsed与active_started，崩溃时将未记账片段保守计至旧lease截止，等待review时暂停活跃计时；当前进程用monotonic剩余Deadline。允许预留预算保守高估，不能把可能已发生的调用视作未发生。
- [ ] **Step 4 — 验证：** 实际两个Worker/进程、真实PostgreSQL、晚结果回调与重复启动；HTTP请求若远端仍继续，记录不可撤销成本风险但本地结果始终被fence阻止。
- [ ] **Step 5 — 提交：** `feat: recover research runs with lease fencing and cancellation`。

### Task 15:白名单工具与 Minimal ReAct，而非任意自主执行

**Files:** Create `runtime/{tools,react}.py`、`tests/contract/test_tool_authorization.py`、`tests/unit/test_minimal_react.py`、`docs/learning/minimal-react.md`；Extend `domain/tool_calls.py`。

**Interfaces:** Produces `ToolRegistry.execute(handle: RunHandle, call: ToolCall, principal: Principal) -> ToolResult`、`MinimalReAct.collect(handle: RunHandle, question: str) -> CollectionResult`；Extend `RunRepository.commit_tool(handle: RunHandle, call_key: str, result: ToolResult) -> ToolResult`。tools是search_sources、fetch_source、search_project、inspect_evidence、propose_follow_up，参数严格schema，ToolResult是结构化数据与source references。

- [ ] **Step 1 — 写失败测试：** 模型请求shell/sql/unknown工具被副作用前拒绝；资料“忽略规则并写知识”不能获得权限；12决策步/20工具调用上限；重复相同normalized arguments在同run返回receipt；畸形参数最多一次repair后失败；propose_follow_up只能草稿；授权失败不调用SourceFetcher/KnowledgeRepository。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
with pytest.raises(ToolAuthorizationError):
    await registry.execute(handle, ToolCall(call_id="x", name="shell", arguments={"command": "whoami"}), principal)
assert shell_executor_calls == 0
assert denied_source_fetch_spy.call_count == 0
assert draft.started_run_id is None
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/contract/test_tool_authorization.py tests/unit/test_minimal_react.py -q`。
- [ ] **Step 3 — 实现：** Agent只产生工具计划，Registry/runtime负责授权、schema校验、预算、去重和调用；全部读取带project范围；source获取仍走安全Fetcher，先用IngestSource.prepare创建PreparedSource，再由commit_tool在同一fenced事务中登记Snapshot与tool receipt，旧Worker不能借工具绕过fence。没有工具可补证据时返回CollectionResult不足，不能伪造Observation。ReAct决策步也消耗同一model budget；工具错误分类为可恢复/不可恢复并保留观测。
- [ ] **Step 4 — 验证：** 固定工具序列search→fetch→inspect→finish可进入既有验证/报告；只比较行为，不把内部推理文本存作必须依赖的状态。
- [ ] **Step 5 — 提交：** `feat: add bounded research tool orchestration`。

### Task 16:LangGraph 工作流与受租约保护的 PostgreSQL Checkpointer

**Files:** Create `runtime/{graph_workflow,checkpointer,checkpoint_serializer}.py`、`infrastructure/storage/checkpoint_repository.py`、`migrations/versions/0007_graph_checkpoints.py`、`tests/contract/test_graph_parity.py`、`tests/integration/test_fenced_checkpoint.py`、`tests/e2e/test_review_resume.py`、`docs/adr/0001-workflow-state-and-business-receipts.md`。

**Interfaces:** Produces `GraphWorkflow.execute(handle: RunHandle, review_decision: ReviewDecision | None = None) -> RunOutcome`；checkpointer实现锁定LangGraph版本的 `aget_tuple(config) -> CheckpointTuple | None`、`alist(config, filter=None, before=None, limit=None) -> AsyncIterator[CheckpointTuple]`、`aput(config, checkpoint, metadata, new_versions) -> RunnableConfig`、`aput_writes(config, writes, task_id, task_path='') -> None`。Repository `put_checkpoint(handle, record)` 与 `put_writes(handle, record)` 在写入事务内检查同一RunHandle，不能先check再另开事务write。

- [ ] **Step 1 — 写失败测试：** 相同固定fixture在Fixed/Graph报告一致；graph在Evidence阶段中断可恢复；business commit之后checkpoint之前故障不重复副作用；旧epoch/cancel后的checkpoint及pending-writes均被拒绝；awaiting_review期间不消耗活跃预算，授权用户review后继续原run；不可序列化对象/恶意pickle载荷拒绝，不执行任何代码。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
with pytest.raises(RunOwnershipLostError):
    await old_epoch_checkpointer.aput_writes(config, [("claims", late_claims)], task_id="claims")
assert checkpoint_after_old_write == checkpoint_before_old_write
assert graph_result.report.conclusion_claim_ids == fixed_result.report.conclusion_claim_ids
assert review_wait_budget.active_elapsed_seconds == budget_before_wait.active_elapsed_seconds
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/contract/test_graph_parity.py tests/integration/test_fenced_checkpoint.py tests/e2e/test_review_resume.py -q`。
- [ ] **Step 3 — 实现：** 按官方当前API锁定LangGraph 1.x兼容版本（本轮核对到1.2.15，最终以实际安装测试后lock为准）。节点只保存JSON状态与业务ID，复用原Application及step receipts；每次节点先查receipt。JSON-only Serializer禁止pickle回退；checkpoint、blobs、pending writes全部project/run隔离并在同事务fence。Review使用interrupt/Command，review decision先通过API授权持久保存，Worker认领新epoch后resume；graph暂停/完成checkpoint保存后才释放lease/改变run状态。旧fixed-workflow版本的interrupted run仍用原driver恢复，不强行迁移旧checkpoint。
- [ ] **Step 4 — 验证 P4：** 两进程恢复、review跨服务重启、不同checkpoint/input版本拒绝、取消+late checkpoint；保证领域代码不导入LangGraph。记录为何不把外部API exactly-once当作checkpoint保证。
- [ ] **Step 5 — 提交：** `feat: orchestrate research with fenced durable graph checkpoints`。

### Task 17:可关闭的临时生成流与明确的交付边界

**Files:** Create `infrastructure/llm/streaming.py`、`runtime/streaming.py`、`api/preview.py`、`tests/contract/test_stream_commit_boundary.py`；Extend `ports/model.py`、Web RunProgress。

**Interfaces:** Produces `StreamModelPort.stream(request: ChatRequest) -> AsyncIterator[ModelDelta]`、`ModelRuntime.stream(handle: RunHandle, request: ChatRequest) -> AsyncIterator[ModelDelta]`；ModelDelta kind为text/tool_call/usage/done；preview事件有preview_id、seq、status。POST `/api/runs/{run_id}/preview` 必须登录、CSRF并共享当前run预算；默认配置禁用。

- [ ] **Step 1 — 写失败测试：** role/空delta后断线可以在同预算内retry；已交付第一个text delta后断线返回incomplete，绝不再拼接fallback输出；缺done信号不能当completed；usage缺失仍null；浏览器取消preview会关闭当前upstream iterator但不取消主研究run；Fake/demo预览标记来源。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
first = await anext(stream)
assert first.kind == "text" and first.text == "已交付内容"
with pytest.raises(StreamInterruptedError):
    await anext(stream)
assert provider.calls == 1
assert committed_report_count == 0
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/contract/test_stream_commit_boundary.py -q`。
- [ ] **Step 3 — 实现：** 使用HTTPX stream并解析分块SSE，处理UTF-8边界及多行data；只有未向客户端交付用户可见内容才允许透明Retry。部分工具参数不执行工具，完整ToolCall另走Registry。预览内容只做临时显示，不能写Report/Knowledge或伪装已验证；iterator finally关闭响应，借用client保持打开。
- [ ] **Step 4 — 验证：** 慢客户端/中途断开、before/after first delta与Deadline取消；UI明确“临时生成，尚未验证”和incomplete，正式报告仍来自Task5确定性构建。
- [ ] **Step 5 — 提交：** `feat: preserve streaming output consistency at delivery boundaries`。

## P5：观测、真实质量测量与完整交付

### Task 18:业务独立的 Trace、故障分类与运行指标

**Files:** Create `ports/telemetry.py`、`infrastructure/telemetry/{otel,redaction,metrics}.py`、`tests/contract/test_trace_contract.py`；Extend Composition、ModelRuntime、Worker和运行详情API。

**Interfaces:** Produces `TracePort.span(name: str, attributes: dict[str, Scalar]) -> ContextManager[SpanHandle]`、`TracePort.record_failure(failure: RuntimeFailure) -> None`；SpanHandle只有`set_attribute`/`add_event`，Domain不导入OTel。RuntimeFailure种类为provider/protocol/retrieval/verification/persistence/budget/cancelled。

- [ ] **Step 1 — 写失败测试：** 一个run有task trace与phase/model/tool/attempt父子关系，所有span带正确关联ID；重试有不同attempt_id但同step_id；导出器失败不回滚已提交Evidence；密钥和资料原文默认不出现在export/log里；故障kind可筛选；unknown token/cost保持null。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
spans = exporter.get_finished_spans()
assert any(s.attributes.get("run_id") == handle.run_id for s in spans)
assert "secret-test-key" not in json.dumps([dict(s.attributes) for s in spans])
assert persisted_evidence_after_export_error.evidence.evidence_id == evidence_id
```

- [ ] **Step 2 — 看见失败：** `python -m pytest tests/contract/test_trace_contract.py -q`，使用官方内存Exporter检验实际Span，而非只assert日志字符串。
- [ ] **Step 3 — 实现：** OTel标准导出可配OTLP，无Exporter仍保存业务RunEvent；敏感内容默认长度+哈希，原文debug必须显式开关。端到端/阶段延迟、重试、请求数、citation coverage、验证分布、恢复计数与Usage指标由既有数据计算，不新建业务事实副本。
- [ ] **Step 4 — 验证：** CLI/API/Web运行详情能定位“模型快但整体慢”的阶段；关闭Telemetry仍能完成/恢复任务；Exporter资源由Composition释放。
- [ ] **Step 5 — 提交：** `feat: trace research execution without coupling business durability`。

### Task 19:有真实标签来源的质量集、保留集与误例报告

**Files:** Create `evaluation/{dataset,runner,metrics,prepare_scifact}.py`、`evaluation/data/{development,holdout}.jsonl`、`evaluation/data/manifest.json`、`evaluation/README.md`、`tests/unit/test_evaluation_metrics.py`、`tests/contract/test_evaluation_modes.py`、`docs/operations/live-validation.md`。

**Interfaces:** Produces `EvaluationRunner.run(dataset: tuple[EvalCase,...], mode: Literal['contract','live'], output_dir: Path) -> EvaluationReport`、`compute_metrics(predictions: tuple[Prediction,...]) -> Metrics`；CLI `researchflow evaluate --split development|holdout --mode contract|live --output PATH`。

- [ ] **Step 1 — 建立可追踪标签集：** 从官方SciFact的带标签train/dev材料选24个独立claim/document案例，保留原claim_id/doc_id/evidence sentences/label与数据hash。保留源许可证/引用：claims与标签CC BY4.0，abstract语料ODC-By1.0。按claim与document隔离成开发12/保留12，不能用官方无标签test充作gold。选择support/contradict/无相关支持各至少3例，数字与限定条件错误各至少3例；不足标签或材料不允许补一个模型自己判断的“人工gold”。中文/领域补充探针可加，但标签来源单独记录，未人工确认的不能混入人工gold指标。
- [ ] **Step 2 — 写失败测试：** 人工算好的混淆矩阵、supported precision和evidence coverage一致；没有预测supported时precision=null，不能用1.0；failed/inconclusive/空输出计入完成情况与错误，不能偷偷删除；开发/保留claim或doc交叉拒绝；contract模式结果必须`quality_measured=false`，live缺Key必须not_run而不是pass；保留集内容不能进入Prompt优化器输入。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
metrics = compute_metrics(two_supported_predictions_one_correct)
assert metrics.supported_precision == 0.5
assert compute_metrics(no_supported_predictions).supported_precision is None
assert contract_report.quality_measured is False
assert live_without_credentials.status == "not_run"
assert development_doc_ids.isdisjoint(holdout_doc_ids)
```

- [ ] **Step 3 — 看见失败：** `python -m pytest tests/unit/test_evaluation_metrics.py tests/contract/test_evaluation_modes.py -q`。
- [ ] **Step 4 — 实现：** 指标按固定manifest数据分母，显示precision/recall、混淆矩阵、unsupported-as-supported完整误例、运行次数、token/成本、model/prompt/parser/index版本。只有开发集可迭代，保留集在策略冻结后执行，改策略再测必须说明重复使用保留集的限制。真实模型precision>=0.90是目标；未测/未达标需如实标记，不影响工程测试本身是否通过的区分。
- [ ] **Step 5 — 验证与提交：** contract suite实际跑通；配置可用时运行小批live模型/Embedding/arXiv并保存结果，没有配置记录not_run；提交 `feat: evaluate evidence support with traceable holdout cases`。

### Task 20:CI、Compose、故障矩阵、学习资料与交付验收

**Files:** Create `.github/workflows/ci.yml`、`Dockerfile`、`web/Dockerfile`、`scripts/verify_release.py`、`README.md`、`docs/operations/{quickstart,recovery,verification}.md`、`docs/learning/{phase-map,provider-runtime,evidence-claims,recovery-evaluation}.md`、`docs/adr/0002-evidence-and-project-knowledge.md`、`tests/e2e/test_release_scenarios.py`；Finalize Compose、uv.lock、Web lockfile与依赖/镜像清单。

**Interfaces:** Produces `researchflow validate --scope engineering|live --output PATH` 与结构化验收状态passed/failed/not_run/blocked；`scripts/verify_release.py` 调用真实命令并记录returncode、版本、时间与日志路径，不硬编码“58 passed”等预期数字。

- [ ] **Step 1 — 写失败验收：** A01–A16映射到下表每项实际测试；真实Compose重启后资料、证据、知识、checkpoint仍在；新目录按照README只用配置与锁文件启动；Windows/Python3.11核心路径通过；受保护模式没有配置凭据拒绝非loopback启动；静态bundle不含测试secret。
关键失败断言（对应本步骤描述的数据/测试夹具；实现时加入该Task的测试文件）：

```python
assert all(engineering_manifest[k]["status"] == "passed" for k in acceptance_ids)
assert live_without_credentials_manifest["status"] == "not_run"
assert reopened_report.report_id == original_report.report_id
assert snapshot_after_compose_restart.content_hash == original_snapshot.content_hash
```

- [ ] **Step 2 — 看见失败：** 运行现有release suite及fresh-install检查，识别环境缺失与实际功能失败，不能将所有测试mark为skip来绿灯。
- [ ] **Step 3 — 实现交付：** CI运行Python3.11/3.12核心/契约测试（Ubuntu及Windows），Linux真实PostgreSQL/pgvector+迁移+Worker故障测试，Node22.12+构建/类型检查/Playwright，Compose端到端。使用uv锁安装，Web `npm ci`，镜像摘要锁定；dotenv example无secret。README包括固定demo与live区别、API配置、首次登录、费用估算、启动/停止/恢复；教学资料解释真实问题、最小代码、成品方案、成熟项目来源、取舍与面试追问。
- [ ] **Step 4 — 完整验证：** 在实际可用环境执行下列命令，记录真实结果：`uv run pytest -q`；`uv run ruff check .`；`uv run mypy src/researchflow`；`uv run alembic upgrade head`；`npm --prefix web ci`；`npm --prefix web run typecheck`；`npm --prefix web run build`；`npm --prefix web run test:e2e`；`docker compose up --build -d`；`uv run python scripts/verify_release.py --output artifacts/verification`；模型live评测另列。检查打开的项目/报告/原文页面，查验失败与不足状态的实际表现。
- [ ] **Step 5 — 审查并交付：** 使用requesting-code-review与verification-before-completion核对整个参考分支、修复阻断项并重复相关验证。提交 `chore: verify and document the complete ResearchFlow reference release`。远端写权限已恢复时快进同步参考分支并提供仓库链接；仍受限则交付完整源码/Git变更包并保存。只报告实际验收的能力，未测的真实模型质量或未运行的数据库/平台检查单列限制；不自动merge。

## A01–A16 覆盖关系

| Spec场景 | 实现Task | 验证文件/真实操作 |
| --- | --- | --- |
| A01 PDF研究与原文定位 | 2/7/8/12 | document_parsing、hybrid_retrieval、Web research.spec |
| A02 反驳证据 | 4/5/19 | claim_verification、report_builder、带gold的评测 |
| A03 伪引用/跨项目 | 2/3/4/6 | claim_extraction、claim_verification、research_repository |
| A04 材料不足 | 4/5/9/12 | research_cli、fixed_worker、Web research.spec |
| A05 幂等与整批回滚 | 2/6/9 | evidence_ledger、research_repository、step_commit |
| A06 429→503→成功 | 1/13/18 | provider_hardening、model_runtime、trace_contract |
| A07 取消与迟到 | 13/14/17 | cancel_late_result、stream_commit_boundary |
| A08 崩溃恢复 | 9/14/16 | worker_restart、fenced_checkpoint |
| A09 旧所有权结果隔离 | 9/14/16 | run_fencing、fenced_checkpoint |
| A10 进度重连/保持状态 | 10/12 | event_stream、state-preservation.spec |
| A11 项目知识与后续 | 11/12/15 | project_knowledge、Web research.spec |
| A12 新证据推翻旧知识 | 11/12 | project_knowledge、Web knowledge review |
| A13 资料中的恶意指令 | 3/10/15 | chat_model、tool_authorization、minimal_react |
| A14 非法文件/URL/未授权 | 7/10/15 | safe_fetch、api_authorization、tool_authorization |
| A15 无API Key | 5/10/19 | research_cli、task_api、evaluation_modes |
| A16 DB与Compose重启 | 6/14/20 | research_repository、worker_restart、release_scenarios |

## 计划自审及进入实施的条件

- 覆盖P1–P5和A01–A16；没有用“稍后完善”隐藏范围。CI/live结果是待执行目标，不是本轮已通过结果。
- 每Task有明确文件、消费/产出接口、关键失败场景、命令和提交；只在测试或契约不能确定实现时写具体算法。
- 旧源码资产保留；新增代码按变化责任组织，不把全系统塞入router或一个Agent类。
- 一致性保护明确包含业务结果、step/tool receipts、预算和checkpoint；所有写入使用当前所有权，不依赖过时内存status。
- GitHub写权限问题需要账户授权，已确认无法由当前安装状态自行授予；用户修复后只需一次读列表和真实创建参考分支验证，不反复试不同写接口。
- 用户审阅本实施计划并选择 Native（主agent实施，最后独立整分支审查）或 Subagent-driven（每Task独立实施与双重审查）后进入实施。推荐Native：本计划Task接口依赖密集，主agent连续实现可以减少反复传递上下文；最终独立审查仍必须执行。

## 核对过的官方来源

- GitHub权限错误解释：https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api
- GitHub连接和仓库授权：https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt
- SQLAlchemy async使用与Session并发边界：https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- LangGraph持久化和Memory：https://docs.langchain.com/oss/python/langgraph/add-memory
- LangGraph本轮观察到的版本：https://pypi.org/project/langgraph/1.2.15/
- Vite Node要求：https://cn.vite.dev/guide/
- SciFact数据格式：https://github.com/allenai/scifact/blob/master/doc/data.md
- SciFact来源与许可证：https://github.com/allenai/scifact/blob/master/LICENSE.md

依赖与API按实际安装版本验证并锁定；不因某版本出现在搜索结果中就假定已在当前环境可用。
