# 运行工作台

## 首次配置

.env.example 提供字段名称，.env放在仓库根目录。Compose自动读取；原生启动需设置同样进程环境。数据库密码建议用 secrets.token_urlsafe(24)，避免连接 URL特殊字符。登录密码和数据库密码分开；researchflow hash-password 输出 Argon2id哈希，不保存明文。环境文件中用单引号包裹哈希，防止美元符号展开。

默认端口8000，模式demo。API/Worker共用数据库和 Blob卷。非loopback启动要求密码哈希，Compose只向本机loopback开放。自行使用反向代理时配置正确 Origin、HTTPS与Secure cookies。

## Windows原生运行

仓库可放 D:\\Projects\\researchflow-reference。Python3.11/3.12配合 uv sync --locked --extra dev --python 3.11，在本仓库建立独立环境。

只用Docker运行数据库时，准备好.env后执行 docker compose up -d db。在PowerShell设置 RF_DATABASE_URL、RF_PASSWORD_HASH、RF_MODE等环境变量，值使用单引号。先 uv run alembic upgrade head，一个终端 uv run researchflow serve，另一个终端 uv run researchflow worker --mode demo。

npm --prefix web ci 与 npm --prefix web run build 后，API同源提供完整界面；开发时 npm --prefix web run dev 使用相同API语义。Git attributes固定源码/JSONL的 LF换行与PDF二进制字节，CLI/PDF子进程协议避免中文被cp1252破坏。

## 实际模型

模型配置四项齐全才能live，context_window必须是实际模型容量。系统保守估算输入并预留输出。具备真实Provider的Worker仍可执行明确demo，demo不调用真实模型。

Embedding配置独立；缺失时使用词法模式。改变模型/维度要明确重建索引，原文与Evidence不因此改变。RF_OTLP_TRACES_ENDPOINT连接自己的Collector；无Collector也可查询持久事件、阶段间隔、尝试、Usage和故障。

RF_PRICE_VERSION与两项USD/百万token单价须同时配置，记录每次估算的版本。没有完整价格/token信息时成本未知。预览只做临时显示，分享研究预算，不会写入报告或知识。

## 停止和备份

docker compose down保留数据卷。备份同时保存PostgreSQL和source-blobs卷，以及私有配置。只复制一种无法完整恢复原始资料和业务关系。需要保留数据时不要使用down --volumes。

正常Worker停机标记interrupted，可在界面恢复；强杀进程后，新Worker在五秒租约过期后接管原run_id。远端模型可能继续处理，已预留请求数不会因为未知结果而退款。
