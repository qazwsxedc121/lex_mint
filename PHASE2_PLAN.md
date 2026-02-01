# Chat 模块阶段2计划：创建可复用组件

## 目标

将 chat 模块提取为通用的可复用组件，使其可以在多个模块（Projects、独立助手页面等）中使用。

## 核心任务

### 1. 创建 shared/chat 目录结构

```
frontend/src/shared/chat/
├── components/          # 通用聊天组件
│   ├── ChatInterface.tsx       # 🆕 高级封装组件
│   ├── ChatSidebar.tsx        # 从 modules/chat 移动
│   ├── ChatView.tsx           # 从 modules/chat 移动
│   ├── MessageList.tsx        # 从 modules/chat/components 移动
│   ├── MessageBubble.tsx      # 从 modules/chat/components 移动
│   ├── InputBox.tsx           # 从 modules/chat/components 移动
│   └── AssistantSelector.tsx  # 从 modules/chat/components 移动
├── hooks/              # 通用hooks
│   ├── useChat.ts            # 从 modules/chat/hooks 移动
│   ├── useSessions.ts        # 从 modules/chat/hooks 移动
│   └── useModelCapabilities.ts # 从 modules/chat/hooks 移动
├── services/           # 服务接口和实现
│   ├── interfaces.ts         # 从 modules/chat/services 移动
│   ├── ChatServiceProvider.tsx # 从 modules/chat/services 移动
│   └── defaultChatAPI.ts     # 从 modules/chat/services 移动
└── index.ts            # 🆕 统一导出文件
```

### 2. 创建 ChatInterface 高级组件

**新文件**: `frontend/src/shared/chat/components/ChatInterface.tsx`

这是一个完全封装的聊天界面组件，包含：
- ChatSidebar
- ChatView（消息列表 + 输入框）
- 自动会话管理

**用法示例**:
```tsx
import { ChatInterface } from '@/shared/chat';

// 最简单的用法（使用默认配置）
<ChatInterface />

// 自定义API和导航
<ChatInterface
  api={customAPI}
  navigation={customNavigation}
  sessionId={currentSessionId}
/>
```

### 3. 更新 modules/chat 使用 shared 组件

**修改文件**: `frontend/src/modules/chat/index.tsx`

将 chat 模块改为使用 shared/chat 中的组件，保持现有路由和功能不变。

### 4. 创建统一导出文件

**新文件**: `frontend/src/shared/chat/index.ts`

导出所有公共API：
```typescript
// Components
export { ChatInterface } from './components/ChatInterface';
export { ChatSidebar } from './components/ChatSidebar';
export { ChatView } from './components/ChatView';

// Services
export { ChatServiceProvider, useChatServices } from './services/ChatServiceProvider';
export { defaultChatAPI } from './services/defaultChatAPI';

// Types
export type {
  ChatAPI,
  ChatNavigation,
  ChatContextData,
  ChatServiceContextValue,
} from './services/interfaces';

// Hooks
export { useChat } from './hooks/useChat';
export { useSessions } from './hooks/useSessions';
export { useModelCapabilities } from './hooks/useModelCapabilities';
```

## 实施步骤

### Step 1: 创建目录结构
- 创建 `frontend/src/shared/chat/` 及子目录

### Step 2: 移动文件
- 将 services/ 移动到 shared/chat/services/
- 将 hooks/ 移动到 shared/chat/hooks/
- 将核心组件移动到 shared/chat/components/

### Step 3: 创建 ChatInterface 组件
- 封装 ChatSidebar + ChatView
- 提供简洁的API

### Step 4: 更新导入路径
- 修复所有组件的相对导入路径
- 确保类型导入正确

### Step 5: 创建 index.ts 导出
- 统一导出所有公共API

### Step 6: 更新 modules/chat
- 改为使用 shared/chat 组件
- 保持路由和功能不变

### Step 7: 验证
- TypeScript 编译通过
- 功能测试通过

## 向后兼容性

- ✅ modules/chat 的所有功能保持不变
- ✅ 现有路由 /chat/:sessionId 继续工作
- ✅ API 接口不变

## 预期成果

1. **可复用性**: 其他模块可以直接使用 `<ChatInterface />`
2. **简洁性**: 一行代码即可集成完整聊天功能
3. **灵活性**: 支持自定义 API 和导航
4. **一致性**: 所有使用chat的地方界面和行为一致

## 未来使用示例

### Projects 模块集成
```tsx
// frontend/src/modules/projects/components/ProjectChat.tsx
import { ChatInterface } from '@/shared/chat';
import type { ChatAPI, ChatNavigation } from '@/shared/chat';

export const ProjectChat: React.FC<{ projectId: string }> = ({ projectId }) => {
  // 自定义API（添加项目上下文）
  const projectAPI: ChatAPI = {
    ...defaultChatAPI,
    createSession: async (modelId, assistantId) => {
      const sessionId = await defaultChatAPI.createSession(modelId, assistantId);
      await api.linkSessionToProject(sessionId, projectId);
      return sessionId;
    },
  };

  const navigation: ChatNavigation = {
    navigateToSession: (id) => navigate(`/projects/${projectId}/chat/${id}`),
    navigateToRoot: () => navigate(`/projects/${projectId}`),
    getCurrentSessionId: () => sessionIdFromParams,
  };

  return <ChatInterface api={projectAPI} navigation={navigation} />;
};
```

### 独立助手页面
```tsx
// frontend/src/pages/AssistantPage.tsx
import { ChatInterface } from '@/shared/chat';

export const AssistantPage: React.FC = () => {
  const assistantAPI = createAssistantAPI(assistantId);

  return <ChatInterface api={assistantAPI} />;
};
```

## 成功标准

- ✅ shared/chat 目录创建完成
- ✅ ChatInterface 组件可独立使用
- ✅ modules/chat 使用 shared 组件
- ✅ TypeScript 编译通过
- ✅ 所有 chat 功能正常工作
- ✅ 代码量减少（消除重复）
