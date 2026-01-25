# 快速开始 - 模型管理功能

## 🚀 立即使用

### 1. 启动应用

**终端 1 - 后端：**
```bash
uvicorn src.api.main:app --reload --port 8000
```

**终端 2 - 前端：**
```bash
cd frontend
npm run dev
```

访问：http://localhost:5173

### 2. 基本操作

#### 切换模型（最简单）
1. 打开任意会话
2. 点击顶部的模型名称下拉框
3. 选择想要的模型（如 DeepSeek Coder）
4. 开始对话！

#### 管理模型配置
1. 点击右上角 ⚙️ 图标
2. 查看"模型管理"和"提供商管理"
3. 添加/编辑/删除模型和提供商

### 3. 添加新 LLM（如 OpenAI）

**方式一：通过 UI**
1. 打开设置 → 提供商管理 → 添加提供商
2. 填写 OpenAI 信息（已预设，只需启用）
3. 在 `.env` 添加：`OPENAI_API_KEY=sk-...`
4. 刷新页面

**方式二：编辑 YAML**
1. 编辑 `models_config.yaml`
2. 将 OpenAI 的 `enabled: false` 改为 `enabled: true`
3. 在 `.env` 添加：`OPENAI_API_KEY=sk-...`
4. 重启后端

## 📁 关键文件

- `models_config.yaml` - 模型配置文件
- `.env` - API 密钥（已在 .gitignore）
- `conversations/*.md` - 会话文件（包含 model_id）

## 🎯 主要功能

✅ 多个 LLM 提供商（DeepSeek、OpenAI、自定义）
✅ 每个会话独立选择模型
✅ 可视化配置界面
✅ 默认模型设置
✅ 模型参数调整（温度等）
✅ 向后兼容旧会话

## 📖 详细文档

- `IMPLEMENTATION_COMPLETE.md` - 完整实施报告
- `MODEL_MANAGEMENT_IMPLEMENTATION.md` - 后端实施详情
- API 文档：http://localhost:8000/docs

## 🐛 故障排除

**问题：模型列表为空**
- 检查后端是否启动
- 确认 `models_config.yaml` 存在

**问题：切换模型无效**
- 确保提供商已启用（`enabled: true`）
- 检查 API 密钥环境变量是否正确

**问题：API 调用失败**
- 验证 API 密钥是否有效
- 检查网络连接
- 查看后端日志

## ✨ 快速测试

```bash
# 测试配置加载
python -c "
from src.api.services.model_config_service import ModelConfigService
import asyncio
asyncio.run(ModelConfigService().load_config())
print('配置加载成功！')
"

# 查看 API 文档
# 访问 http://localhost:8000/docs
```

---

现在就开始使用多模型支持功能吧！🎉
