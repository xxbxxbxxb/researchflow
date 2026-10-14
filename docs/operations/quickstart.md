# 运行工作台

## 配置与首次登录

`.env.example` 提供配置名称，`.env` 放在仓库根目录。Compose 自动读取它；原生启动应把同样变量设置到进程环境。数据库密码建议使用 `secrets.token_urlsafe(24)` 生成，避免连接 URL 中的特殊字符。登录密码与数据库密码分开；`researchflow hash-password` 只输出 Argon2id 哈希，不保存明文。Compose 中哈希请用单引号包裹，防止 `$` 被解释为环境变量。

默认端口8000，默认模式demo。API/Worker 共用数据库和 Blob卷。非 loopback 启动要求配置密码哈希；Compose 绑定本机 loopback。公开托管不属于这份运行默认；如果自行放到反向代理后面，应配置 HTTPS、正确 Origin 与 Secure cookies。

## Windows 原生方式

将仓库放在自己的工作盘，例如 `D:\Projects\researchflow-reference`。使用 Python3.11/3.12，不需要复用其他项目的 Conda环境。`uv sync --locked --extra dev --python 3.11` 会在本仓库建立隔离环境。

如果只让数据库运行在 Docker 中，必须先准备 `.env` 中的登录哈希和密码，再运行 `docker compose up -d db`。在 PowerShell 中设置进程环境，例如 `$env:RF_DATABASE_URL='postgresql+psycopg://researchflow:自己的URL-safe密码@127.0.0.1:5432/researchflow'`，`$env:RF_PASSWORD_HASH='完整Argon2id哈希'`，`$env:RF_MODE='demo'`。不要把自己的 Key 或哈希复制到公开代码。

运行 `uv run alembic upgrade head`。在一个终端执行 `uv run researchflow serve`，另一个终端执行 `uv run researchflow worker --mode demo`。先执行 `npm --prefix web ci` 和 `npm --prefix web run build`，API 就会同源提供完整界面；开发时可以单独运行 `npm --prefix web run dev`，其代理仍使用同样 API。

Git attributes 固定 JSONL 与源码的 LF 换行，并保留 PDF二进制字节。CLI JSON 和解析子进程使用可跨 Windows 控制台的协议编码，避免中文被 cp1252 破坏。

## 实际模型

模型配置四项必须齐全，context_window 是 Provider 所用模型的真实上下文容量，系统使用保守字节估算预留输出。配置不完整会拒绝 live。一个具备真实 Provider 的 Worker 仍可执行明确的 demo，demo 不会偷偷调用真实模型。

向量检索使用独立 embedding 配置。没有 embedding 时词法模式可正常运行。更换模型/维度后必须重建旧资料的索引；旧索引不会悄悄当作新模型向量。原文和证据不因重建索引而改变。

`RF_OTLP_TRACES_ENDPOINT` 可连接自己的 OTel collector；没有 collector 也可以查看持久运行事件、阶段间隔、尝试、Usage 和故障类别。临时预览由 `RF_PREVIEW_ENABLED` 开关控制，共享模型预算，不能形成正式结论。

## 停止、备份与恢复

`docker compose down` 停止服务，保留数据卷。备份时同时保存 PostgreSQL 数据和 source-blobs 原文件卷，并保管环境配置。只复制数据库无法恢复原始下载文件，只复制 Blob无法恢复证据与任务关系。不要在需要保留数据时使用 `down --volumes`。

Worker 正常停机会将活跃运行标为 interrupted；可以在界面恢复。进程被强制结束后，运行仍可能显示 running，新的 Worker 会在五秒租约过期后接管同一个 run_id。模型费用无法通过回滚数据库撤销；未知的已发请求不会退款或重置预算。

估算价格可通过 `RF_PRICE_VERSION`、`RF_INPUT_PRICE_PER_MILLION`、`RF_OUTPUT_PRICE_PER_MILLION` 同时设置，后两项单位是 USD/百万 token。每次 Usage保存价格版本；未提供完整价格或 token未知，成本为 null。它是配置价格下的估算，不是供应商账单。
