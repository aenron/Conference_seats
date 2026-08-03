# Conference Seats

基于 FastAPI 与 MCP SSE 的会议排位工具服务，向智能体提供三个工具：

- `query_personnel_candidates`：按人员视图查询候选参会人员；
- `create_seating_plan`：生成、调整并校验三种会议排位方案；
- `render_seating_chart`：将方案导出为 SVG，并可选导出 PNG/PDF。

## 启动

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.mcp_sse_server
```

默认 MCP SSE 地址为 `http://127.0.0.1:8100/sse`。生成文件可通过工具返回的下载地址获取。
`cairosvg` 用于 PNG/PDF 导出；若运行环境缺少其系统图形依赖，工具仍会成功返回 SVG，并在 `warnings` 中说明附加格式未生成。

人员数据源支持与 `llm2word` 完全一致的分项配置：`PERSONNEL_DB_TYPE`、`PERSONNEL_DB_HOST`、`PERSONNEL_DB_PORT`、`PERSONNEL_DB_USER`、`PERSONNEL_DB_PASSWORD`、`PERSONNEL_DB_SERVICE_NAME`、`PERSONNEL_DB_SCHEMA` 与 `PERSONNEL_DB_VIEW`。也可用 `PERSONNEL_DATABASE_URL` 覆盖分项配置。

## Docker 部署

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写人员数据库连接，并将 MCP_DOWNLOAD_BASE_URL 改为外部可访问地址。
docker compose up --build -d
```

服务默认暴露 `8100` 端口。座位图文件保存在宿主机的 `generated_files`，容器重建后仍可下载。

若旧镜像启动后出现 `Permission denied: 'generated_files/plans'`，先执行一次：

```powershell
docker compose down
docker compose up --build -d
```

新镜像会以可写身份运行，兼容宿主机绑定的 `generated_files` 目录。

镜像内置并缓存 `Noto Sans CJK SC` 中文字体，PNG/PDF 导出前请使用 `docker compose up --build -d` 重建镜像；仅重启旧容器不会加入字体。

若 MCP 客户端通过局域网或公网地址访问，必须将该地址（含端口）同时加入 `.env` 的 `MCP_ALLOWED_HOSTS` 与 `MCP_ALLOWED_ORIGINS`，然后重建或重启容器。例如访问地址为 `http://168.8.6.168:8100/sse` 时，应允许 `168.8.6.168:8100` 和 `http://168.8.6.168:8100`。

## 排位类型

- `surrounding_table`：中央会议桌、四周围坐；
- `face_to_face`：上下两排相对而坐；
- `side_table_and_rows`：左侧纵向主桌、右侧多排座席。

`create_seating_plan` 的 `adjustments` 支持 `assign`、`swap`、`reserve` 与 `clear`。工具会返回 `warnings`，用于提示座位不足、人员未排入、重复安排或不存在的人员。

人员数据源配置与 `llm2word` 保持兼容；未配置数据库时，人员查询会返回明确的配置错误，但不影响根据手工名单排位和出图。
