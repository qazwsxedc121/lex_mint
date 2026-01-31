# 端口配置指南

## 默认端口

项目默认使用以下端口：
- **后端 API**: 8888
- **前端**: 5173 (Vite 默认)

## 为什么改为 8888？

之前的默认端口 8000 容易与其他服务冲突，改为 8888 可以减少端口冲突。

## 如何修改端口

### 方法一：修改 .env 文件（推荐）

1. **修改后端端口**

编辑项目根目录的 `.env` 文件：

```bash
API_PORT=9999  # 改为你想要的端口
```

2. **修改前端配置**

编辑 `frontend/.env` 文件：

```bash
VITE_API_URL=http://localhost:9999  # 必须与后端端口一致
```

3. **重启服务**

修改配置后需要重启前后端服务才能生效。

### 方法二：直接修改启动脚本

如果你使用 `start.bat` 启动：

编辑 `start.bat`，找到并修改：

```batch
start "LangGraph Backend" cmd /k "venv\Scripts\activate && uvicorn src.api.main:app --host 0.0.0.0 --port 8888"
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
set VITE_API_URL=http://localhost:9999
cd frontend
npm run dev
```

临时设置环境变量（Windows PowerShell）：
```powershell
$env:VITE_API_URL="http://localhost:9999"
cd frontend
npm run dev
```

## 常见问题

### Q: 修改了端口但前端连不上后端

**A:** 确保 `frontend/.env` 中的 `VITE_API_URL` 与后端端口一致，并且重启了前端服务。

### Q: 端口被占用怎么办？

**A:**

1. 检查哪个进程占用了端口：
```bash
netstat -ano | findstr :8888
```

2. 结束占用端口的进程：
```bash
taskkill /F /PID <进程ID>
```

3. 或者直接改用其他端口（参考上面的配置方法）

### Q: 生产环境应该用什么端口？

**A:**

- 如果使用 Nginx/Apache 反向代理，后端可以用任意端口（如 8888）
- 如果直接暴露，建议使用 80（HTTP）或 443（HTTPS）
- 修改 `src/api/config.py` 中的 `api_host` 为 `0.0.0.0` 允许外部访问

## 配置文件位置总结

| 配置项 | 文件位置 | 说明 |
|--------|---------|------|
| 后端端口 | `.env` (API_PORT) | 通过环境变量配置 |
| 后端主机 | `.env` (API_HOST) | 默认 0.0.0.0 |
| 前端 API URL | `frontend/.env` (VITE_API_URL) | 必须与后端端口匹配 |
| 启动脚本 | `start.bat` | 硬编码端口 8888 |

## 注意事项

1. **前后端端口必须一致**：修改后端端口时，务必同步修改前端的 `VITE_API_URL`
2. **CORS 配置**：如果前端使用非默认端口，需要在 `.env` 中更新 `CORS_ORIGINS`
3. **环境变量优先级**：`.env` 文件中的配置会被实际的环境变量覆盖
