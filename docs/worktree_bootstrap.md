# Worktree 初始化指南

这份文档用于多 worktree 并行开发时的快速初始化，目标是：
- 不重复手工输入 key
- 不重复排查端口和 CORS
- 用一条脚本命令完成初始化

## 为什么新 worktree 看起来像“丢配置”

以下文件本来就不会跟随 Git 切分到新 worktree（被 `.gitignore` 忽略）：
- `.env`
- `config/local/`
- `data/state/`

其中：
- `.env` 需要手动初始化（或脚本生成）
- `config/local/*.yaml` 与 `data/state/*.yaml` 会在后端首次启动时自动生成

## 一次性配置共享 key（推荐）

将 API key 放在用户目录的共享文件中，后续每个 worktree 自动复用。

1) 创建目录和文件（只做一次）：

```powershell
New-Item -ItemType Directory -Force "$HOME\.lex_mint" | Out-Null
Set-Content -Path "$HOME\.lex_mint\keys_config.yaml" -Value @"
providers:
  deepseek:
    api_key: "你的真实key"
"@
```

2) 之后每个 worktree 初始化时，脚本优先使用这个共享文件，不再依赖 `.env` 保存 API key。

## 每个 worktree 的标准初始化命令

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort <API_PORT> -FrontendPort <FRONTEND_PORT>
```

> 注意：`-ApiPort` 和 `-FrontendPort` 要按 **当前 worktree** 单独设置，避免和其他 worktree 冲突。  
> 不建议省略参数直接用脚本默认值（默认是 `8901/5181`，容易撞端口）。

推荐做法（示例）：

| worktree | API_PORT | FRONTEND_PORT |
|---|---:|---:|
| main | 8901 | 5181 |
| feature/a | 8902 | 5182 |
| feature/b | 8903 | 5183 |

对应执行示例：

```powershell
# feature/a
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort 8902 -FrontendPort 5182

# feature/b
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort 8903 -FrontendPort 5183
```

脚本会做这些事：
- 创建/检查 `venv`（`python -m venv .\venv --upgrade-deps`）
- 从 `.env.example` 生成 `.env`（如不存在）
- 设置 `API_PORT` 与 `FRONTEND_PORT`
- 设置 `CORS_ORIGINS`（JSON 数组格式，避免后端解析报错）
- 读取/写入共享 key 文件：`$HOME\.lex_mint\keys_config.yaml`
- 若共享 key 缺失，脚本会尝试从当前/其他 worktree 的 `config/local/keys_config.yaml` 自动迁移
- 安装后端与前端依赖

可选参数：

```powershell
# 仅更新 .env，不安装依赖
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort 8903 -FrontendPort 5183 -SkipInstall

# 指定自定义共享 key 文件路径
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort 8903 -FrontendPort 5183 -SharedKeysPath "D:\secrets\keys_config.yaml"
```

## 启动命令模板

后端：

```powershell
.\venv\Scripts\uvicorn src.api.main:app --host 0.0.0.0 --port <API_PORT>
```

前端：

```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port <FRONTEND_PORT> --strictPort
```

## 快速验收

```powershell
Invoke-WebRequest http://127.0.0.1:<API_PORT>/api/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:<FRONTEND_PORT> -UseBasicParsing
```

## 常见问题

1) 后端启动报 `cors_origins` 解析错误  
`CORS_ORIGINS` 必须是 JSON 数组格式，例如：
`["http://localhost:5181","http://localhost:5173","http://localhost:3000","http://127.0.0.1:5181"]`

2) 新 worktree 里没有 `config/local` 或 `data/state`  
这是正常的，首次启动后端会自动创建。

3) 还是提示 key 缺失  
检查：
- `$HOME\.lex_mint\keys_config.yaml` 是否存在且包含：
  `providers.deepseek.api_key`
