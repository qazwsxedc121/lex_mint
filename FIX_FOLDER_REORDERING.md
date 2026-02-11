# 修复：文件夹拖拽重排序功能

## 问题描述
用户反馈：移动对话到文件夹工作正常，但拖拽文件夹来调整顺序没有效果。

## 根本原因分析

### 1. 类型不匹配问题
文件夹头部同时充当两个角色：
- **Droppable（接收区）**：接收会话，data.type = `'folder-drop'`
- **Draggable（可拖拽）**：用于重排序，data.type = `'folder'`

原来的 `handleDragEnd` 逻辑：
```typescript
// 只匹配 folder → folder
if (dragData?.type === 'folder' && dropData?.type === 'folder') {
  // 重排序逻辑
}
```

但实际上拖拽文件夹到另一个文件夹时：
- dragData.type = `'folder'` ✓
- dropData.type = `'folder-drop'` ✗ (不匹配！)

### 2. 拖拽监听器覆盖整个头部
原来的实现把拖拽监听器放在整个容器上，导致：
- 点击展开/折叠按钮 → 触发拖拽
- 点击编辑/删除按钮 → 触发拖拽
- 用户体验混乱

## 解决方案

### 1. 修改 Droppable 数据结构
在 `DroppableFolderHeader.tsx` 中添加标志：
```typescript
useDroppable({
  id: `folder-drop-${folder.id}`,
  data: {
    type: 'folder-drop',
    folderId: folder.id,
    acceptsFolder: true,  // 新增：表明可接收文件夹
    folderOrder: folder.order,
  },
});
```

### 2. 更新拖拽结束逻辑
在 `ChatSidebar.tsx` 的 `handleDragEnd` 中：
```typescript
// 文件夹重排序：检查 acceptsFolder 标志
if (dragData?.type === 'folder' && dropData?.type === 'folder-drop' && dropData?.acceptsFolder) {
  const oldIndex = folders.findIndex(f => f.id === dragData.folderId);
  const newIndex = folders.findIndex(f => f.id === dropData.folderId);

  if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
    await reorderFolder(dragData.folderId, newIndex);
  }
}
```

### 3. 重构文件夹头部结构
将文件夹头部分为三个独立区域：

```
┌─────────────────────────────────────────┐
│ [▼] │  📁 Folder Name (3)  │  [✏️] [🗑️] │
│ 按钮 │   可拖拽区域        │   按钮     │
└─────────────────────────────────────────┘
```

- **左侧**：展开/折叠按钮 - 不可拖拽
- **中间**：文件夹名称 - 仅此区域可拖拽（应用 `{...listeners}`）
- **右侧**：编辑/删除按钮 - 不可拖拽

代码结构：
```tsx
<div ref={setDropNodeRef}>  {/* 整个容器可接收drop */}
  {/* 左侧按钮 */}
  <button onClick={onToggle}>▼</button>

  {/* 中间可拖拽区域 */}
  <div ref={setDragNodeRef} {...dragAttributes} {...listeners}>
    📁 {folder.name}
  </div>

  {/* 右侧按钮 */}
  <div>
    <button onClick={onRename}>✏️</button>
    <button onClick={onDelete}>🗑️</button>
  </div>
</div>
```

## 修改的文件

### 1. `DroppableFolderHeader.tsx`
- ✅ 添加 `acceptsFolder` 和 `folderOrder` 到 droppable data
- ✅ 重构结构：分离拖拽区域和按钮区域
- ✅ 移除 `setRefs` 组合函数（不再需要）
- ✅ 只在中间文件夹名称区域应用拖拽监听器

### 2. `ChatSidebar.tsx`
- ✅ 修改 `handleDragEnd` 逻辑，支持 `folder → folder-drop` 的重排序
- ✅ 添加早期返回（`return`）避免重复处理
- ✅ 保留兼容性代码处理 `folder → folder` 情况

## 测试验证

刷新浏览器后，测试以下功能：

### ✅ 文件夹重排序（现在应该工作）
1. 从文件夹名称区域开始拖拽
2. 拖到另一个文件夹上方
3. 释放鼠标
4. **预期**：文件夹顺序改变，刷新页面后顺序保持

### ✅ 按钮点击（不受影响）
1. 点击 ▼ 按钮 → 展开/折叠文件夹
2. 点击 ✏️ 按钮 → 重命名文件夹
3. 点击 🗑️ 按钮 → 删除文件夹
4. **预期**：所有按钮正常工作，不会触发拖拽

### ✅ 会话移动（不受影响）
1. 拖拽会话到文件夹
2. **预期**：会话移动到目标文件夹

### ✅ 视觉反馈
1. 拖拽文件夹时：
   - 被拖拽的文件夹 → 半透明（opacity: 0.5）
   - 目标文件夹 → 蓝色边框和背景
   - 跟随鼠标的 ghost 预览
2. 拖拽会话时：
   - 目标文件夹 → 蓝色边框和背景

## 技术细节

### 为什么分离拖拽区域？
1. **用户体验**：用户期望只拖拽文件夹名称，而不是整个头部
2. **避免冲突**：按钮和拖拽功能不应该混在一起
3. **符合直觉**：类似文件管理器（Windows Explorer、Finder）的行为

### 为什么使用 acceptsFolder 标志？
1. **清晰的意图**：明确表示这个 drop 区域可以接收文件夹
2. **类型安全**：通过标志而不是 type 来区分功能
3. **向后兼容**：保留原有的 type 值，不破坏会话移动功能

### Refs 的使用
```typescript
// Drag ref: 只应用到中间名称区域
<div ref={setDragNodeRef} {...listeners}>

// Drop ref: 应用到整个容器
<div ref={setDropNodeRef}>
```

这样确保：
- 整个文件夹头部都可以作为 drop 目标（无论拖到哪里都行）
- 只有名称区域可以被拖拽（避免意外拖拽）

## 常见问题

### Q: 为什么拖拽文件夹时会有延迟？
A: 这是正常的，因为需要调用后端 API 并刷新文件夹列表。

### Q: 可以拖拽到第一个位置吗？
A: 可以，拖到最上方的文件夹上即可。后端会自动计算新的 order 值。

### Q: 如果拖到同一个文件夹上会怎样？
A: 不会有任何操作，代码中有检查 `oldIndex !== newIndex`。

### Q: 拖拽会影响折叠状态吗？
A: 不会，折叠状态存储在 localStorage 中，与 order 无关。

## 后续优化建议

1. **拖拽指示器**：在目标位置显示插入线（类似 VS Code 文件拖拽）
2. **长列表性能**：如果文件夹超过 20 个，考虑虚拟滚动
3. **撤销功能**：添加撤销按钮，可以还原文件夹顺序
4. **拖拽中间位置**：支持拖到两个文件夹之间（而不只是上方）

## 调试提示

如果重排序仍然不工作：
1. 打开浏览器控制台（F12）
2. 拖拽文件夹时观察 Network 标签
3. 应该看到 `PATCH /api/folders/{id}/order` 请求
4. 检查请求是否成功（状态码 200）
5. 检查 `config/local/chat_folders.yaml` 中的 order 值是否改变
