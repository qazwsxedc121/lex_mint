# Worktree 初始化指南

这份文档用于多 worktree 并行开发时的快速初始化，目标是：
- 不重复手工输入 key
- 不重复排查端口和 CORS
- 用一条脚本命令完成初始化

## 端口分配规范（推荐）

为避免多 worktree 端口冲突，建议统一采用 `slot` 规则：

- `slot` 范围：`1-999`
- `API_PORT = 19000 + slot`
- `FRONTEND_PORT = 15100 + slot`

示例：

| slot | API_PORT | FRONTEND_PORT |
|---:|---:|---:|
| 1 | 19001 | 15101 |
| 23 | 19023 | 15123 |
| 101 | 19101 | 15201 |

这样每个 worktree 只需记住一个 `slot`，并且前后端端口尾号一致，便于排查。

## 为什么新 worktree 看起来像“丢配置”

以下文件本来就不会跟随 Git 切分到新 worktree（被 `.gitignore` 忽略）：
- `.env`
- `config/local/`
- `data/state/`

其中：
- `.env` 需要手动初始化（或脚本生成）
- `config/local/*.yaml` 与 `data/state/*.yaml` 会在后端首次启动时自动生成

## 一次性配置共享 key（仅用于初始化）

将 API key 放在用户目录的共享文件中，作为新 worktree 的初始化来源。
**运行时只会写 `config/local/keys_config.yaml`，不会写共享文件。**

1) 创建目录和文件（只做一次）：

```powershell
New-Item -ItemType Directory -Force "$HOME\.lex_mint" | Out-Null
Set-Content -Path "$HOME\.lex_mint\keys_config.yaml" -Value @"
providers:
  deepseek:
    api_key: "你的真实key"
"@
```

2) 之后每个 worktree 初始化时，脚本会优先读取这个共享文件来初始化 `config/local/keys_config.yaml`。
   共享文件仅用于 bootstrap，不会被脚本或后端写回。

## 每个 worktree 的标准初始化命令

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort <API_PORT> -FrontendPort <FRONTEND_PORT>
```

macOS / Linux（推荐）：

```bash
./scripts/init_worktree.sh --slot <SLOT>
```

> 注意：`-ApiPort` 和 `-FrontendPort` 要按 **当前 worktree** 单独设置，避免和其他 worktree 冲突。  
> 脚本要求显式传参，不提供默认端口。

> `scripts/init_worktree.sh` 支持自动分配：如果不传 `--slot` 和端口参数，会自动选择第一个可用 slot，并检查 worktree/进程占用冲突。

推荐做法（示例）：

| worktree | slot | API_PORT | FRONTEND_PORT |
|---|---:|---:|---:|
| main | 1 | 19001 | 15101 |
| feature/a | 2 | 19002 | 15102 |
| feature/b | 3 | 19003 | 15103 |

对应执行示例：

```powershell
# feature/a
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort 19002 -FrontendPort 15102

# feature/b
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort 19003 -FrontendPort 15103
```

```bash
# feature/a
./scripts/init_worktree.sh --slot 2

# feature/b
./scripts/init_worktree.sh --slot 3
```

脚本会做这些事：
- 创建/检查 `venv`（`python -m venv .\venv --upgrade-deps`）
- 从 `.env.example` 生成 `.env`（如不存在）
- 设置 `API_PORT` 与 `FRONTEND_PORT`
- 设置 `CORS_ORIGINS`（JSON 数组格式，避免后端解析报错）
- 只写本地 key 文件：`config/local/keys_config.yaml`
- 可从共享文件 `$HOME\.lex_mint\keys_config.yaml` 或其他 worktree 的 `config/local/keys_config.yaml` 初始化本地 key
- 共享 key 文件永远只读（bootstrap-only）
- 安装后端与前端依赖

可选参数：

```powershell
# 仅更新 .env，不安装依赖
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort <API_PORT> -FrontendPort <FRONTEND_PORT> -SkipInstall

# 指定自定义共享 key 文件路径
powershell -ExecutionPolicy Bypass -File .\scripts\init_worktree.ps1 -ApiPort <API_PORT> -FrontendPort <FRONTEND_PORT> -SharedKeysPath "D:\secrets\keys_config.yaml"
```

```bash
# 仅更新 .env，不安装依赖
./scripts/init_worktree.sh --slot <SLOT> --skip-install

# 显式指定端口（不使用 slot）
./scripts/init_worktree.sh --api-port <API_PORT> --frontend-port <FRONTEND_PORT>

# 指定自定义共享 key 文件路径
./scripts/init_worktree.sh --slot <SLOT> --shared-keys-path "/path/to/keys_config.yaml"
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
`["http://localhost:<FRONTEND_PORT>","http://localhost:3000","http://127.0.0.1:<FRONTEND_PORT>"]`

2) 新 worktree 里没有 `config/local` 或 `data/state`  
这是正常的，首次启动后端会自动创建。

3) 还是提示 key 缺失  
检查：
- `config/local/keys_config.yaml` 是否存在且包含：
  `providers.deepseek.api_key`
