# ResearchFlow Agent 成熟参考版 V1：产品与架构设计

日期：2026-10-13（北京时间）  
状态：架构设计与实施计划已由用户批准；2026-10-13 开始 Native 实施  
代码基线：`xxbxxbxxb/researchflow@268160c88d9ab67fb314eb3b01f87fcfffe9e743`  
目标分支：`reference/mature-v1`（用户已选择独立参考分支）

## 1. 要交付的具体结果

ResearchFlow 是用于长期技术学习与科研调研的 Evidence-Grounded Agent System。用户创建一个研究项目，提出问题，导入或获取资料，系统组织检索、证据提取、主张生成与验证，产出可回溯原文的报告。用户能够审阅结论、积累项目知识、继续创建后续问题；任务失败或服务重启后可以继续。

完整业务链路为：Research Project → Research Task → Source/Document → Retrieval → Evidence → Claim → Verification → Research Report → Project Knowledge → Follow-up Task。

核心展示场景：用户研究“某种方法为什么优于另一种方法”，导入包含支持、反驳和条件限制的几篇资料。系统检索具体段落，提出可核验的原子 Claim，识别支持与冲突，形成带原文定位的报告；用户接受一个有依据的结论进入项目知识，并针对未解决的问题创建后续任务。下一次任务能检索本项目历史结论及其证据。

成功标准同时包含：实际可用的完整产品、可解释的架构与故障处理、可复现的质量评测，以及适合用户后续逐模块跟写的代码和教学路径。

## 2. 已有约束、已确认决定与本稿的设计假设

| 类别 | 具体内容 |
| --- | --- |
| 用户原规划 | 求职优先；强调可追踪、可验证、可继续的科研任务；不是通用聊天应用 |
| 用户原规划 | Windows、Python 3.11；模块化单体；Evidence 不等于检索 Chunk；项目知识与一次任务状态分开 |
| 用户原规划 | ResearchFlow 与 Agent Reliability Lab 保持独立仓库；暂不提前集成 Reliability Lab |
| 用户原规划 | 先理解并实现 Minimal ReAct，再引入 LangGraph；ES 与 Redis 按需求和评测结果决定 |
| 本次确认 | 完整成品使用独立参考分支，保留当前每日跟写主线 |
| 本稿假设 | V1 面向一个研究者的完整工作台；提供受保护的单用户自托管模式，先不做多租户 SaaS |
| 本稿假设 | 交付后端、Worker、Web 前端、可运行演示、迁移脚本、测试、评测和说明文档 |
| 本稿假设 | 免费离线演示使用明确标识的固定案例；真实模型与真实数据路径独立，不能用演示结果冒充效果测量 |
| 本稿假设 | 部署支持本地开发及 Docker Compose；此次不购买云资源、不直接上线公网服务 |

上述设计假设已随本稿由用户批准；具体实施选择依据实施计划与执行记录。

## 3. 当前源码基线与需要弥补的差距

已检查默认分支上述提交的全部源文件与测试。仓库有 28 个文件，其中 18 个位于 `src`、8 个测试文件，另有 `pyproject.toml` 和 `.gitignore`。未发现 `AGENTS.md`、README、架构文档、CI、持久化层或 Web 服务。

| 现有能力 | 真实行为 | V1 演进 |
| --- | --- | --- |
| `domain/research.py` | 不可变 ResearchTask/Evidence；基本字段与 ID 唯一性检查 | 保留旧接口，新增 Project、SourceSnapshot、Claim、Verification、Report 等明确实体 |
| `PrepareResearchTask` | 接受人工提供的 1–20 条 Evidence | 保留教学用例；成品增加自动获取、解析、检索与证据建立 |
| `AnswerResearchTask` | 一次模型调用；检查 `[E1]` 等引用别名是否存在 | 保留为“有引用的回答”；新主线必须逐 Claim 验证后构建报告 |
| `OpenAICompatibleLLM` | 可注入 HTTP Client，错误分类明确 | 兼容扩展多消息、工具调用、结构化结果、Usage 与 Streaming；保留旧 `generate` |
| `RetryLLM` | 分类重试、指数退避、Full Jitter、数值 Retry-After | 修复非有限数值输入；支持 HTTP-date、Deadline、Retry Budget 与尝试记录 |
| `DeadlineLLM` | 用 `asyncio.timeout` 限制逻辑调用并传播取消 | 在任务与步骤层增加统一预算、持久状态、取消与过期结果隔离 |

最高优先级的缺口是“引用存在”与“结论受到证据支持”的区别。检查过程中，证据写着样本量 12，旧回答仍能接受“样本量 999 [E1]”；一个有效引用后跟无引用的虚构句子也能通过。这不构成语义验证。

其他已观察到的风险包括 Retry 延迟接受 NaN/Infinity、Provider 配置默认 repr 包含 API Key，以及未记录模型 Usage、Request ID、成本与版本。

验证边界：本轮做了源码检查、AST 解析与标准库级行为实验；当前执行环境缺少 pytest/httpx，未安装项目依赖，未完成全套 pytest，也未做真实模型或 Windows/Python 3.11 验收。现有测试数不是成品验收结果。

## 4. 方案比较与推荐

| 方案 | 优点 | 代价与适用性 |
| --- | --- | --- |
| A：模块化单体、固定业务阶段、阶段内受限 Agent | 保留现有学习资产；领域规则可独立理解；端到端链路、可靠性与质量都有明确边界 | 需要实现自己的业务状态与提交规则；推荐采用 |
| B：直接围绕 Dify/LlamaIndex 等平台搭建 | 初期接入和界面较快 | 核心证据规则、恢复语义和项目知识容易受到平台接口限制；不利于展示自主工程能力 |
| C：从一开始拆分微服务并部署 Temporal、Redis、模型网关等 | 更适合复杂的跨团队和高并发基础设施 | 运维与一致性成本过高，超出当前个人项目的实际需求 |

选择 A。吸收成熟项目解决问题的思想，不把这些项目全部变成依赖。LangGraph 在固定业务闭环和 Minimal ReAct 已验收后进入主运行路径，领域实体、证据校验与数据库事务仍由 ResearchFlow 自己管理。

## 5. V1 产品范围

### 5.1 项目、任务与资料

- 创建和查询研究项目，项目具有名称、研究背景与资料范围。
- 创建研究任务：问题、关联项目、指定资料和执行预算；问题最大 5,000 字符。
- 导入 UTF-8 TXT/Markdown、可提取文字的 PDF，以及公开 HTTP/HTTPS 网页；PDF 保存物理页码。
- 网页快照保留原始 URL、最终 URL、获取时间、内容摘要和内容哈希；内容变化产生新版本。
- 首个真实外部检索连接器使用 arXiv；系统也必须支持只在已导入资料中研究。连接器失败不能伪造搜索结果。
- 上传默认最大 20 MiB，PDF 默认最大 200 页；不支持的文件、扫描 PDF、无法解析或超限文件给出明确可操作的结果。OCR 与浏览器渲染网页不纳入 V1。

### 5.2 检索与 Evidence

- 建立可复现的分块与元数据；Chunk 是检索单元，Evidence 是与快照原文定位绑定的不可变引用记录。
- 支持词法检索与向量检索，组合为混合检索；默认取 8 个候选，经过去重和预算筛选后建立 Evidence。
- 向量检索依赖可配置的 Embedding Provider。未配置时允许词法模式，但界面和评测必须记录实际模式。
- Evidence 保存 snapshot_id、locator、quote、content_hash、提取版本及创建时间；引用必须能回到已保存的原文，而不是只指向一个随时变化的 URL。
- 同 ID、同内容的重复写入幂等；同 ID、不同内容是冲突；批量建立 Evidence 全部提交或全部失败。

### 5.3 Claim 与验证

- Claim 是一个可被证据支持或反驳的原子主张，不能把整篇回答当作一个 Claim。
- Claim 与 Evidence 是显式多对多关系；分别保存模型提出的引用与验证后接受的支持关系。
- 验证分三层：引用身份及项目边界、原文片段与位置完整性、Claim 与 Evidence 的语义关系。
- 每个 Claim 结果为 `supported`、`contradicted`、`insufficient`、`inconclusive` 之一，保存原因、引用原文、检验规则、Prompt/模型版本与验证时间。
- `inconclusive` 表示验证过程无法完成或结果不能确定；`insufficient` 表示现有材料不足，两者不能混用。
- 对数值、实验条件、比较对象与限定词增加确定性核对；模型验证与规则校验冲突时不得静默标为 supported。
- 模型验证结果表示“当前材料下的支持判断”，不宣称证明现实中的绝对事实；允许人工改判，但保留原结果和改判原因。

### 5.4 报告、知识与后续任务

- 报告包含回答、逐项结论、支持与反驳依据、未解决问题和参考来源；每个事实型结论可点击查看 Claim→Evidence→原文。
- supported 结论进入有依据的回答区；矛盾和不足在报告中明确呈现。没有证据时仍能生成“材料不足”的有效研究结果。
- 报告是不可变版本；重新研究或更换验证策略生成新版本，不覆盖历史。
- 用户主动接受结论后进入 Project Knowledge，记录接受者、时间、原 Claim/Verification/Report 版本与证据。
- 项目知识可被后续资料反驳或取代，保留 superseded 状态及版本关系；不能把旧结论当成无来源的系统指令。
- 从未解决问题创建后续任务，建立 parent_task_id、关联 Claim 和所需证据类型；默认作为草稿，由用户启动。

### 5.5 可用界面

Web 包含项目列表、项目资料与知识、任务详情与实时进度、报告与证据检查、运行历史五个主要视图。界面提供上传、创建任务、启动、取消、恢复、查看报告、接受知识和创建后续任务的完整操作。

任务与报告 URL 可直接打开；筛选状态写入 URL。进度刷新只更新数据，保持滚动位置、当前展开的证据和正在编辑的输入。

核心界面使用中文，代码命名与接口用英文。运行详情可以展示步骤、重试与耗时，普通用户流程不暴露框架内部实现术语。

## 6. 系统结构与技术选择

### 6.1 组件

| 组件 | 责任 | 依赖边界 |
| --- | --- | --- |
| Domain | 研究实体、关系、状态和不变量 | 不导入 FastAPI、HTTPX、SQLAlchemy 或 LangGraph |
| Application | 导入、研究、验证、审阅和恢复等用例 | 只依赖 Domain 与 Ports |
| Ports | Model、Embedding、Search、SourceFetch、Repository、Clock、Trace 接口 | 以业务需要定义最小契约 |
| Infrastructure | HTTP Provider、文件解析、数据库、检索和观测适配器 | 将外部错误翻译为明确错误 |
| Runtime | Worker、步骤执行、预算、取消、尝试隔离与工作流驱动 | 不替代 Domain 的正确性规则 |
| API/CLI | 输入验证、授权、传输、用户操作与脚本入口 | 调用 Application；不直接绕过 Repository 规则 |
| Web | 资料与任务操作、进度、报告、证据检查 | 通过 API，不直接连接模型或数据库 |
| Composition | 读取配置并建立客户端、适配器和用例 | 集中管理资源所有权与生命周期 |

### 6.2 技术栈

- Python 3.11 兼容；FastAPI/Pydantic 负责接口边界，HTTPX 复用异步连接池。
- SQLAlchemy 2 + Alembic；PostgreSQL 作为业务与运行记录的权威数据库，pgvector 支持向量检索。
- 本地文件目录/Compose Volume 保存内容寻址的资料快照；数据库保存索引与归属。接口为未来对象存储留出边界，但 V1 不接付费存储。
- React + TypeScript + Vite，采用查询缓存管理服务器状态，SSE 通知失效或局部更新。
- 初始实现固定阶段与 Minimal ReAct；后续使用 LangGraph 表达相同流程并提供恢复和人工审阅支持。
- pytest、Ruff、类型检查、前端静态检查、Playwright 与质量评测脚本；CI 至少运行 Python 3.11/3.12。
- OpenTelemetry 用于标准 Trace 导出；不要求部署 Langfuse。默认日志和运行详情可独立工作。

依赖版本、锁文件和镜像摘要在实施计划中根据当前官方文档与可安装版本确定，交付时锁定。本文的技术选择不是对“最新版”的未经核验声明。

### 6.3 数据实体

主要实体为 Project、ResearchTask、SourceSnapshot、Document、Chunk、Evidence、Claim、ClaimEvidenceLink、Verification、ReportVersion、KnowledgeEntry、FollowUpDraft、WorkflowRun、StepExecution、Attempt、RunEvent、LLMUsage。

- task_id 表示用户的研究任务；run_id 表示一次逻辑运行。崩溃恢复继续同一 run_id 并增加所有权代次，主动重新研究产生新 run_id；step_id 是逻辑步骤；attempt_id 是步骤的一次尝试。
- completed step 的唯一提交凭据防止恢复重复建立 Claim、Evidence 或报告。
- 业务实体独立于 Trace。Trace 丢失不撤销已提交 Evidence；报告正确性不能只依靠日志。
- UTC 存储时间，界面按用户时区显示；单进程内的耗时和 Deadline 使用单调时钟。

## 7. 工作流、Agent 与恢复边界

主流程：校验与规划 → 资料获取/快照 → 检索 → Evidence 建立 → Claim 提取 → 验证 → 报告 → 等待知识审阅。

阶段顺序由 Runtime 决定。受限 Agent 只能在资料收集、补充检索和后续问题提出的阶段调用白名单工具；不能直接决定某 Claim 已通过验证，不能直接执行任意代码、SQL 或文件操作。

工具包括 search_sources、fetch_source、search_project、inspect_evidence、propose_follow_up；工具返回结构化结果。数据库写入的最终业务用例由 Runtime 执行，不能用模型输出替代授权和校验。

默认限制：每运行最多 12 个 Agent 决策步、20 次工具调用、16 次实际上游模型请求（包含 Retry、修复与验证调用）、4 个并发外部操作；活跃运行 Deadline 300 秒，单次逻辑模型操作最多 60 秒。配置可以收紧或放宽，但不能接受非有限数值或负数。材料过多时分批处理或明确截断，不静默超出模型上下文。

预算计数跨恢复持久化；恢复不能重置已消耗的模型调用或工具次数。累计活跃执行时间受 Deadline 限制，人工审阅等待时间不计入活跃时间，重启前正在执行但未提交的时间不能凭空删除。

运行状态为 queued、running、awaiting_review、succeeded、failed、cancelled、interrupted。步骤与尝试有各自状态，局部不足不自动成为系统故障：完整产出“材料不足”的报告可以 succeeded；Provider 无法完成验证时可记录 inconclusive，但必须显式标记结果受限，不能伪装为 supported。

Worker 通过数据库认领运行并持有带版本的租约。认领、续租、取消和最终结果提交必须检查运行代次；租约过期后旧 Worker 的结果及 checkpoint 写入不能覆盖新 Worker。LangGraph checkpoint 适配器与业务提交使用相同的运行所有权校验。

恢复依据持久化的输入快照、策略版本、已完成步骤和输出凭据，跳过已提交的步骤。不读取一条 status=running 就假装恢复完成。源码、Prompt 或输入版本改变时启动新运行，不能把不兼容的旧 checkpoint 强行继续。

业务数据提交与步骤成功记录放在同一数据库事务中。若数据库已提交而工作流 checkpoint 尚未完成，重入步骤先读取提交凭据，返回已有结果。数据库事务之外的模型调用无法承诺只发生一次：进程在拿到响应但尚未保存时崩溃，恢复可能再次调用模型并产生额外成本；Trace 与 Usage 必须揭示这个限制。

## 8. 模型可靠性、取消与 Streaming

- 保留旧 `LLMPort.generate`；新增明确的消息、工具调用、结构化结果、Usage 和流式契约，不能破坏现有教学用例。
- 统一由一个 Runtime 层负责 Retry，关闭或明确计入第三方 SDK 的隐藏重试，避免层层放大。
- 仅瞬时网络错误、429 和可恢复 5xx 进入受限重试；认证、请求参数、非法协议输出不进行无限重试。
- Retry-After 支持有限秒数和 HTTP-date；服务端建议仍受剩余 Deadline 约束。等待时间不足时直接结束，不等待到预算外。
- JSON/工具参数错误最多进行一次可记录的结构修复；修复也消耗同一预算，失败返回结构化错误。
- HTTP Client 与外部资源在应用生命周期建立和释放；调用者拥有的客户端不由单个请求关闭。
- 用户取消写入持久取消标志并传播到当前 Task、HTTP 请求与子任务；不吞掉 CancelledError。过期结果即使迟到也不能提交。
- 任务进度 SSE 与模型 token 流分开。任务进度允许按持久 event_id 重新连接；断开进度页不会自动取消研究，取消需要显式操作。
- 如果提供临时生成预览，向客户端交付内容之前可透明重试；交付后中断必须标记 incomplete，不能拼接另一模型从头生成的内容。
- 临时预览不能成为最终报告；验证通过并提交的新报告版本才是最终成果。
- Usage 记录 provider/model、已知 token、耗时与 Request ID；成本使用版本化价格配置估算，未知用 null，不能填成 0 冒充已测量。

## 9. 数据完整性与执行权限

- 不把资料原文当作系统指令；资料和系统规则使用不同消息角色或明确的结构化边界。遇到原文中的命令，模型可以引用但不能因此获得工具权限。
- 网页获取只允许 HTTP/HTTPS；限制重定向、大小、下载时间和内容类型，防止访问本地、私有、链路本地及云元数据地址。每次重定向和实际连接均按同一规则检查，DNS 解析与连接目标必须一致。
- 文件导入用服务器生成的路径和内容哈希；不使用上传文件名拼接可写路径，不解压任意用户压缩包。
- 数据库查询强制带 project_id；跨项目 Evidence 或知识引用必须通过显式关联，不能因为 ID 存在就接受。
- 写入知识、启动后续任务、上传文件和取消运行在副作用发生前校验权限与参数，不能依赖生成后才运行的 Guardrail。
- API Key 不进入日志、repr、Trace、评测文件或前端资源；配置仅从环境或本机未提交文件读取。
- 本地演示默认绑定 loopback；可访问的自托管服务启用单用户登录、HttpOnly/SameSite Cookie、Origin/CSRF 校验和限流；首次凭据由环境配置。公网部署需由后续部署任务单独验证 HTTPS 和反向代理配置。
- V1 不包括任意 Shell 执行、自动邮件发送、第三方账号写入或自动发布用户科研结论。

## 10. Trace、评测与“成熟”的证据

一次运行包含端到端 Trace，内部记录阶段、工具、模型与尝试的 Span，绑定 project_id/task_id/run_id/step_id/attempt_id。失败记录区分 provider、protocol、retrieval、verification、persistence、budget、cancelled；敏感输入默认只保存长度与哈希，调试原文保存为显式配置。

默认收集：端到端延迟、各阶段延迟、模型请求数、重试数、引用覆盖、支持/冲突/不足比例、已知 token、估算成本、恢复成功情况。不要只报告“没有抛异常”。

评测分三层，报告不得混用：

1. 确定性工程测试：固定模型输出、Mock HTTP、实际数据库事务、超时取消与故障注入，验证系统的行为契约。
2. 离线语义评测：带人工标签的固定资料—问题—Claim—原文支持关系，覆盖支持、矛盾、材料不足、条件丢失、数字错误与来源冲突。生成和优化使用开发集，最终指标用未参与优化的保留集。
3. 真实连接冒烟：使用配置的模型、Embedding 与 arXiv 执行少量已知案例，保存模型和数据版本；没有凭据或网络时标记 not_run，不能称通过。

初始人工标注集至少 24 个独立案例（开发集 12、保留集 12），每个 Claim 有具体原文锚点；对矛盾、材料不足、数字/条件错误至少各 3 个案例。小样本指标必须连同分母、混淆矩阵和误例展示，不能宣称生产级泛化。

硬性发布门槛：工程集中的非法引用、跨项目引用、损坏 quote/locator 和被禁止写入均被阻断；支持与矛盾案例的报告行为符合标签；数据库幂等、取消后禁止提交和进程重启恢复验收通过。

模型效果门槛：真实模型的 Claim 支持精确率目标至少 0.90，报告所有 unsupported-as-supported 错误。该数值是目标，当前未测量；未达到时需改进或明确标记实验性，不能用假模型结果满足这一门槛。

## 11. 实施分解与每阶段可用结果

以下是整体交付顺序。各阶段的精确文件、接口、测试和提交步骤将在本设计审阅后写入实施计划。

| 阶段 | 产出 | 可独立验收的行为 |
| --- | --- | --- |
| P1 证据业务闭环 | Claim/Link/Verification/Report，用手动材料运行完整 CLI；修复已发现的运行边界问题 | 支持、反驳、无证据、伪引用各一个案例能产生正确类型结果 |
| P2 资料与检索 | 项目、快照、PDF/网页解析、混合检索、PostgreSQL/pgvector 持久化 | 从真实资料找到原文，重启后资料、证据与报告仍在 |
| P3 可用产品 | API、Worker、Web、SSE、单用户访问控制、知识与后续任务 | 通过界面完成导入→研究→证据检查→知识接受→后续研究 |
| P4 Agent 与恢复 | Minimal ReAct 教学基线，再迁移到 LangGraph；预算、租约、取消、恢复和提交凭据 | 强制停止 Worker 后恢复；已完成步骤不重复提交；旧尝试无法覆盖新结果 |
| P5 质量与交付 | Trace、故障矩阵、保留集评测、真实连接冒烟、CI、文档、可运行包 | 每项发布门槛有实际命令、结果、配置与证据，限制明确 |

P1–P5 都属于本次完整项目范围，不能完成 P1 就把它叫成熟版。也不能因某阶段测试很多就长期不交付可操作的业务功能。

V1 不纳入：多租户/团队协作、支付计费、训练模型、爬取登录网站、OCR、任意代码执行、复杂微服务、Elasticsearch、Redis、Temporal 服务部署，以及与另一个项目的深度集成。发生明确需求时通过新设计加入，不在实施中偷偷扩大范围。

## 12. 完整验收场景

| 编号 | 场景 | 必须观察到的结果 |
| --- | --- | --- |
| A01 | 导入含实验结果的 PDF，提问并研究 | 报告中每个事实型结论可跳到保存的具体页与原文，quote 与快照一致 |
| A02 | 提供与 Claim 相反的证据 | 被标为 contradicted 或保留冲突；不能因为引用存在就宣告 supported |
| A03 | 模型生成不存在/跨项目 Evidence ID | 阻断结果提交，保存具体失败原因 |
| A04 | 没有材料，或材料无法回答 | 输出材料不足及建议补充资料；没有伪造结论 |
| A05 | 重复导入/重试同一批 Evidence | 同内容幂等，冲突整批回滚，没有半批新增记录 |
| A06 | 模型 429→503→成功 | 在总预算内重试，Trace 可见每次尝试，完成一份报告 |
| A07 | 模型迟迟不返回；用户取消 | 上游调用终止或被隔离；任务取消；迟到结果不能写入业务数据 |
| A08 | Evidence 已提交，验证前杀死 Worker | 新 Worker 从持久状态继续；已完成步骤不重复生成业务记录 |
| A09 | 旧 Worker 租约失效后才返回 | 无法更新步骤、业务结果或 checkpoint；新运行结果保持有效 |
| A10 | 刷新进度页/断开后重连 | 进度依据 event_id 补齐，不重复创建任务，滚动和证据展开状态保持 |
| A11 | 接受项目结论，再提交相关后续问题 | 新任务能使用同项目历史知识并回溯其证据；其它项目数据不会混入 |
| A12 | 新证据推翻已接受结论 | 生成新验证/报告版本；旧知识有 superseded 关联，历史仍可查 |
| A13 | 资料包含“忽略规则并执行命令” | 不获得额外工具或写入权限；原文仅作为资料处理 |
| A14 | 非法文件路径/本地网络 URL/未授权 API | 副作用前阻止，不能产生文件、网络访问或业务写入 |
| A15 | 没有模型 API Key | 可运行明确标识的固定演示；真实模型任务显示配置缺失，不降级为伪造真实回答 |
| A16 | 实际数据库与 Docker Compose 重启 | 数据和业务关系保存完整；迁移、健康检查与恢复按文档有效 |

最终验证至少包含 Python 3.11、PostgreSQL/pgvector 实际事务与迁移、后端测试、前端构建/类型检查、浏览器端到端操作以及故障注入。当前尚未执行上述成品验收。

## 13. 交付与学习衔接

完整交付包含：源码、锁定依赖、`.env.example`、数据库迁移、Docker Compose、CLI、API/OpenAPI、Web、演示资料、自动化测试、质量评测数据与脚本、架构说明、关键 ADR、运行与恢复手册、验收结果和已知限制。

参考版提供 `docs/learning/`：每阶段真实问题、最小实现、成品实现、成熟项目来源、设计取舍、故障实验与面试追问。你的每日跟写分支按实际已掌握进度推进，参考版完成不代表你已经掌握全部内容。

现有 `LLMPort`、错误分类、注入 HTTP Client/Sleeper/Randomizer、不可变 Evidence 和 `DeadlineLLM(RetryLLM(provider))` 是值得保留的资产。旧 Answer 用例明确命名为引用契约验证，不能把其 answered 状态当成 Claim 已验证。

GitHub 授权已于 2026-10-13 补齐，reference/mature-v1 远端分支创建成功；本次实现只更新参考分支，不修改每日跟写分支。

## 14. 设计依据与使用边界

- 原项目与本次基线：https://github.com/xxbxxbxxb/researchflow/tree/268160c88d9ab67fb314eb3b01f87fcfffe9e743
- REA：https://github.com/morluto/rea 。借鉴证据身份、完整性与调查记录；不因为 Ledger 完整就认定结论真实。
- LangGraph 官方持久化文档：https://docs.langchain.com/oss/python/langgraph/persistence 。区分一次工作流 checkpoint 与跨任务知识；内存 Saver 不能提供进程重启持久化。
- Temporal 官方 Activity 文档：https://docs.temporal.io/activity-definition 。借鉴可重复执行、副作用幂等与提交凭据；不部署 Temporal，也不承诺外部模型调用 exactly-once。
- OpenAI Agents SDK 官方 Guardrails 文档：https://openai.github.io/openai-agents-python/guardrails/ 。借鉴正确的检查边界；模型 Guardrail 不能替代工具授权。
- LiteLLM：https://github.com/BerriAI/litellm 。参考 Retry/Fallback、流式输出边界与成本记录，具体实现时按版本核对，不接入完整网关。
- Langfuse：https://github.com/langfuse/langfuse 。参考 Trace、运行实验与真实反馈；业务事实不依赖观测系统可用性。
- DSPy：https://github.com/stanfordnlp/dspy 。借鉴指标与保留集驱动的迭代，不在 V1 强制引入优化器。

以上是设计依据与待实施时持续查证的参考，不代表已审计这些项目全部源码。成熟度只能由本项目的实际行为、故障验证与效果测量说明。
