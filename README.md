# ResearchFlow Agent

ResearchFlow 是一个可操作的单人科研工作台。它把研究任务、保存的原文、可定位证据、逐项主张判断、报告、经人工接受的项目知识和后续研究串成一条可追踪的链路。

这份完整参考实现位于 `reference/mature-v1`，适合运行、阅读和求职展示。每日跟写继续使用原分支，学习路线见 [阶段地图](docs/learning/phase-map.md)。

## 可以完成的工作

上传文本、Markdown 或含文字的 PDF，也可以导入公开网页。在项目中创建问题，启动研究后查看实时进度；报告逐项区分材料支持、材料反驳、材料不足和验证未完成。每个引用可以展开保存的原文，报告可以导出 Markdown。你可以人工改判并保留原因，接受结论为项目知识，从未解决问题创建草稿，再主动启动后续任务。

运行过程使用数据库提交凭据、租约和 LangGraph checkpoint。进程重启继续原 run_id，已提交步骤不重复生成报告；旧 Worker、取消后的结果和 checkpoint 无权写入。白名单 Agent 可以查找、获取和检查资料，模型不能直接写知识、执行 Shell 或 SQL。

## 先运行固定演示

需要 Python3.11/3.12 和 uv。这个路径不用数据库，也不用模型 Key。

```bash
python -m pip install uv==0.12.23
git clone --branch reference/mature-v1 --single-branch https://github.com/xxbxxbxxb/researchflow.git researchflow-reference
cd researchflow-reference
uv sync --locked --extra dev --python 3.11
uv run researchflow demo --case supported
uv run researchflow demo --case contradicted
uv run researchflow demo --case insufficient
uv run researchflow demo --case invalid-citation --format json
```

最后一个例子应该拒绝非法引用并返回非零退出码。固定演示明确标记 demo；它证明业务流程与规则可运行，不代表真实模型的判断质量。

## 启动完整工作台

需要 Docker Compose。先复制 `.env.example` 为 `.env`，将数据库密码换成自己生成的 URL-safe 密码。运行 `uv run researchflow hash-password`，输入至少12个字符的登录密码，把输出中的 Argon2id 哈希填入 `.env`。哈希含 `$`，应写成 `RF_PASSWORD_HASH='完整哈希'`，保留单引号。环境文件不会进入 Git。

```bash
docker compose up --build -d
```

打开 http://localhost:8000，用刚才输入的密码登录。API 会自动迁移数据库，Worker 在 API 就绪后开始处理任务。默认固定演示不会访问真实模型。`docker compose down` 只停止容器；数据库和原文件保存在两个持久卷中，重新启动仍可查询。具体配置、Windows 原生运行与备份见 [运行说明](docs/operations/quickstart.md)。

## 切换真实模型与检索

设置 `RF_MODE=live`，以及 `RF_LLM_BASE_URL`、`RF_LLM_API_KEY`、`RF_LLM_MODEL`、`RF_CONTEXT_WINDOW`。重建服务后选择真实模型运行。模型适配器使用 OpenAI-compatible `/chat/completions`；所有尝试、修复和验证共享运行预算。默认16次模型请求、20次工具、12次 Agent 决策、4个外部并发、300秒活跃时间，可以通过运行输入收紧上限。

需要向量检索时，另设 `RF_EMBEDDING_BASE_URL`、`RF_EMBEDDING_API_KEY`、`RF_EMBEDDING_MODEL`、`RF_EMBEDDING_DIMENSIONS`。未配置时使用词法检索，报告会显示实际模式。改变 embedding 模型或维度需要显式重建索引，不能混用旧向量。索引上传是用户主动操作；研究中的 query embedding 计入同一运行预算。

在研究方式中勾选“允许检索并补充公开科研资料”后，受限 Agent 可以使用 arXiv 和安全网页获取器。联网失败会保留错误或材料不足，不伪造来源。临时生成预览默认关闭；开启 `RF_PREVIEW_ENABLED=true` 后它只在活跃运行中可用，显示“尚未验证”，停止预览不取消研究。

## 验证与质量

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src/researchflow
npm --prefix web ci
npm --prefix web run typecheck
npm --prefix web run build
uv run researchflow evaluate --split development --mode contract --output artifacts/eval-contract
uv run researchflow validate --scope engineering --output artifacts/verification
```

完整工程验收需要专用 PostgreSQL/pgvector 测试数据库与浏览器。没有数据库时，集成测试会明确 skipped，验收 manifest 标记 blocked；这些结果不会算成数据库通过。CI 分别执行 Ubuntu/Windows、Python3.11/3.12，真实 PostgreSQL、迁移、进程故障、Chromium 与 Compose 重启。

质量集来自 SciFact 原始标签，开发集与保留集各12例，按主张和文档隔离。contract 模式始终 `quality_measured=false`。配置真实模型后才能测量支持精确率；0.90 是目标，未测不能宣称达到。未知 token 和价格保持 null。见 [评测说明](evaluation/README.md)、[验收边界](docs/operations/verification.md) 和 [真实连接验证](docs/operations/live-validation.md)。

## 阅读代码

| 位置 | 从这里理解什么 |
| --- | --- |
| `domain/` | 主张、证据、运行与知识的业务不变量 |
| `application/` | 提取、核对、报告与人工审阅 |
| `ports/` | 与框架无关的模型、来源、存储契约 |
| `infrastructure/` | 真实模型、文档解析、数据库与 OTel |
| `runtime/` | 预算、工具、Worker、租约、恢复和 LangGraph |
| `api/` 与 `web/` | 登录、项目操作、进度和证据检查 |
| `src/researchflow/evaluation/` | 原始标签、固定分母指标与误例 |

上面的 Python 目录均位于 `src/researchflow/`。从 [证据与主张](docs/learning/evidence-claims.md) 开始读，再进入 [Provider 与 Runtime](docs/learning/provider-runtime.md) 和 [恢复与评测](docs/learning/recovery-evaluation.md)。
