# 端口配置指南

## 默认端口

项目默认使用以下端口：
- **后端 API**: 以根目录 `.env` 的 `API_PORT` 为准（见 `.env.example`）
- **前端**: 5173 (Vite 默认)

## 为什么推荐自定义端口？

默认端口容易与其他服务冲突，建议在 `.env` 中设置一个不易冲突的端口。

## 如何修改端口

### 方法一：修改 .env 文件（推荐）

1. **修改后端端口（单一真理来源）**

编辑项目根目录的 `.env` 文件：

```bash
API_PORT=9999  # 改为你想要的端口
```

2. **重启服务**

修改配置后需要重启前后端服务才能生效。
前端会从根目录 `.env` 读取 `API_PORT` 并自动生成 `VITE_API_URL`。

### 方法二：直接修改启动脚本

如果你使用 `start.bat` 启动：

编辑 `start.bat`，找到并修改：

```batch
start "LangGraph Backend" cmd /k "venv\Scripts\activate && uvicorn src.api.main:app --host 0.0.0.0 --port <API_PORT>"
```

改为：

```batch
start "LangGraph Backend" cmd /k "venv\Scripts\activate && uvicorn src.api.main:app --host 0.0.0.0 --port 9999"
```

同时修改显示信息部分的端口号。

### 方法三：手动启动时指定端口

**后端：**
```bash
./venv/Scripts/uvicorn src.api.main:app --reload --port 9999
```

**前端：**

临时设置环境变量（Windows CMD）：
```bash
set API_PORT=9999
cd frontend
npm run dev
```

临时设置环境变量（Windows PowerShell）：
```powershell
$env:API_PORT="9999"
cd frontend
npm run dev
```

## 常见问题

### Q: 修改了端口但前端连不上后端

**A:** 确保根目录 `.env` 中的 `API_PORT` 已修改并重启前端服务。

### Q: 端口被占用怎么办？

**A:**

1. 检查哪个进程占用了端口：
```bash
netstat -ano | findstr :<API_PORT>
```

2. 结束占用端口的进程：
```bash
taskkill /F /PID <进程ID>
```

3. 或者直接改用其他端口（参考上面的配置方法）

### Q: 生产环境应该用什么端口？

**A:**

- 如果使用 Nginx/Apache 反向代理，后端可以用任意端口（如 `<API_PORT>`）
- 如果直接暴露，建议使用 80（HTTP）或 443（HTTPS）
- 修改 `src/api/config.py` 中的 `api_host` 为 `0.0.0.0` 允许外部访问

## 配置文件位置总结

| 配置项 | 文件位置 | 说明 |
|--------|---------|------|
| 后端端口 | `.env` (API_PORT) | 通过环境变量配置 |
| 后端主机 | `.env` (API_HOST) | 默认 0.0.0.0 |
| 前端 API URL | 根目录 `.env` (API_PORT) | 前端由 Vite 自动生成 VITE_API_URL |
| 启动脚本 | `start.bat` | 读取 `.env` 的 API_PORT |

## 注意事项

1. **前后端端口必须一致**：修改后端端口时，前端会自动跟随 `.env` 中的 `API_PORT`
2. **CORS 配置**：如果前端使用非默认端口，需要在 `.env` 中更新 `CORS_ORIGINS`
3. **环境变量优先级**：`.env` 文件中的配置会被实际的环境变量覆盖
