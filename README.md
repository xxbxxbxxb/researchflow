# ResearchFlow Agent

ResearchFlow 是一个可操作的单人科研工作台。它把研究任务、保存的原文、可定位证据、逐项主张判断、报告、经人工接受的项目知识和后续研究串成一条可追踪的链路。

完整参考实现位于 reference/mature-v1，适合运行、阅读与求职展示。每日跟写继续使用原分支，学习路线见 [阶段地图](docs/learning/phase-map.md)。

## 完整操作

上传文本、Markdown 或含文字的 PDF，也可以导入公开网页。创建研究问题后查看实时进度；报告逐项区分材料支持、材料反驳、材料不足和验证未完成。引用可以展开保存的原文，报告可以导出 Markdown。人工改判保留原因与旧版本，接受结论进入项目知识，后续研究先保存草稿，再主动启动。

运行使用原子业务提交凭据、租约和 LangGraph checkpoint。崩溃恢复沿用 run_id，已提交步骤不会重复生成报告；取消或旧 Worker 的迟到结果不能写回。受限 Agent 只可查找、获取、检索和检查资料，不能直接写知识、执行 Shell 或 SQL。

## 无 Key 的固定演示

需要 Python3.11/3.12 和 uv；这一路径不需要数据库。

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

非法引用案例应拒绝输出并返回非零退出码。固定演示标记 demo，只证明机制和业务流程，不代表真实模型质量。

## 完整工作台

需要 Docker Compose。复制 .env.example 为 .env，用 URL-safe 随机密码替换数据库密码。运行 `uv run researchflow hash-password`，输入至少12字符登录密码，将输出的 Argon2id 哈希填入环境文件；哈希含美元符号，请使用单引号包裹。

```bash
docker compose up --build -d
```

打开 http://localhost:8000，用刚才设置的密码登录。API 自动迁移，Worker 在 API 就绪后处理队列。默认 demo 不会请求真实模型。数据库与原文件保存在持久卷；停止容器后重新启动仍可查询。Windows、原生启动和备份见 [运行说明](docs/operations/quickstart.md)。

## 真实模型与检索

设置 RF_MODE=live 和 RF_LLM_BASE_URL、RF_LLM_API_KEY、RF_LLM_MODEL、RF_CONTEXT_WINDOW，重启服务后选择真实模型。Provider 使用 OpenAI-compatible chat/completions；重试、修复、验证与 Agent 规划共享预算。默认16次模型请求、20次工具、12个决策步、4个外部并发、300秒活跃时间，可以在运行输入或界面收紧。人工审阅等待不计活跃时间。

向量检索另设 RF_EMBEDDING_BASE_URL、RF_EMBEDDING_API_KEY、RF_EMBEDDING_MODEL、RF_EMBEDDING_DIMENSIONS。没有 embedding 时使用词法检索并显示实际模式。更换 embedding 模型/维度需要显式重建旧资料索引。研究中的 query embedding 计入同一预算。

勾选允许补充公开资料后，受限 Agent 可检索 arXiv 并经安全获取器保存来源。网络失败不伪造结果。预览由 RF_PREVIEW_ENABLED 控制，默认关闭，只用于活跃运行；预览尚未验证，停止它不会取消研究。

RF_PRICE_VERSION、RF_INPUT_PRICE_PER_MILLION、RF_OUTPUT_PRICE_PER_MILLION 同时提供版本与 USD/百万 token 单价。每个 Usage 保存价格版本，缺失 token 或价格时成本为 null。估算不等于供应商账单。

## 验证

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

数据库测试要求专用 PostgreSQL/pgvector 数据库，名称以 _test 结尾。没有环境时会明确 skipped/blocked，不计为通过。CI分别执行 Ubuntu/Windows Python3.11/3.12、真实数据库、迁移、进程故障、Chromium 与实际 Compose 重启。

SciFact 原始标签子集有开发/保留各12例，按主张与文档隔离。contract 永远 quality_measured=false。真实支持精确率0.90是目标，未测不能宣称达到。见 [评测](evaluation/README.md)、[验收边界](docs/operations/verification.md)、[恢复](docs/operations/recovery.md)。

## 代码阅读

| 位置（Python目录在 src/researchflow 下） | 责任 |
| --- | --- |
| domain | 主张、证据、运行、知识不变量 |
| application | 提取、核对、报告和人工审阅 |
| ports | 框架独立的边界契约 |
| infrastructure | 模型、文档、数据库、检索和 OTel |
| runtime | 预算、工具、Worker、租约、恢复与 LangGraph |
| api / web | 登录、项目操作、进度和证据检查 |
| evaluation | 原始标签、固定分母指标与误例 |

学习从 [证据与主张](docs/learning/evidence-claims.md) 开始，再看 [Provider与Runtime](docs/learning/provider-runtime.md) 和 [恢复与评测](docs/learning/recovery-evaluation.md)。
