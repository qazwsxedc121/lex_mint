# Project Management Module

## 概述

项目管理模块提供了基于文件系统的项目管理功能，允许用户索引和浏览外部项目的文件结构，读取文件内容。项目可以位于磁盘上的任何位置，通过 `config/projects_config.yaml` 进行索引管理。

**特性：**
- 项目 CRUD 操作（创建、读取、更新、删除）
- 文件树浏览（类似 VS Code 的文件浏览器）
- 文本文件读取
- 路径遍历攻击防护
- 文件类型和大小限制

**限制：**
- 后端实现完成，前端待开发
- 只读模式（不支持文件编辑/上传）
- 不支持二进制文件
- 隐藏文件（以 `.` 开头）自动排除

---

## API Endpoints

**Base URL:** `http://localhost:8888/api/projects`

所有端点都在 `/api/projects` 下。

### 1. List Projects

**GET** `/api/projects`

获取所有项目列表。

**Response:**
```json
[
  {
    "id": "proj_abc123456789",
    "name": "My Django Project",
    "root_path": "C:/Users/username/projects/django-app",
    "description": "Django web application",
    "created_at": "2026-02-01T10:00:00",
    "updated_at": "2026-02-01T10:00:00"
  },
  {
    "id": "proj_def987654321",
    "name": "React Frontend",
    "root_path": "D:/work/react-frontend",
    "description": "React TypeScript frontend",
    "created_at": "2026-02-01T11:00:00",
    "updated_at": "2026-02-01T11:00:00"
  }
]
```

### 2. Create Project

**POST** `/api/projects`

创建新项目。

**Request Body:**
```json
{
  "name": "My Project",
  "root_path": "C:/Users/username/my-project",
  "description": "Project description (optional)"
}
```

**注意：**
- `root_path` 必须是绝对路径
- 路径必须存在且是目录
- `name` 长度限制：1-100 字符
- `description` 长度限制：最多 500 字符

**Response (201 Created):**
```json
{
  "id": "proj_abc123456789",
  "name": "My Project",
  "root_path": "C:/Users/username/my-project",
  "description": "Project description",
  "created_at": "2026-02-01T12:00:00",
  "updated_at": "2026-02-01T12:00:00"
}
```

**Error Responses:**
- `400 Bad Request` - 验证失败（路径不存在、非绝对路径等）
- `500 Internal Server Error` - 服务器错误

### 3. Get Project

**GET** `/api/projects/{project_id}`

获取单个项目详情。

**Response:**
```json
{
  "id": "proj_abc123456789",
  "name": "My Project",
  "root_path": "C:/Users/username/my-project",
  "description": "Project description",
  "created_at": "2026-02-01T12:00:00",
  "updated_at": "2026-02-01T12:00:00"
}
```

**Error Responses:**
- `404 Not Found` - 项目不存在

### 4. Update Project

**PUT** `/api/projects/{project_id}`

更新项目信息。

**Request Body (所有字段可选):**
```json
{
  "name": "Updated Name",
  "root_path": "C:/Users/username/new-path",
  "description": "Updated description"
}
```

**Response:**
```json
{
  "id": "proj_abc123456789",
  "name": "Updated Name",
  "root_path": "C:/Users/username/new-path",
  "description": "Updated description",
  "created_at": "2026-02-01T12:00:00",
  "updated_at": "2026-02-01T13:00:00"
}
```

**Error Responses:**
- `404 Not Found` - 项目不存在
- `400 Bad Request` - 验证失败

### 5. Delete Project

**DELETE** `/api/projects/{project_id}`

删除项目（仅从配置中删除，不删除实际文件）。

**Response:** `204 No Content`

**Error Responses:**
- `404 Not Found` - 项目不存在

### 6. Get File Tree

**GET** `/api/projects/{project_id}/tree?path={relative_path}`

获取项目目录树结构。

**Query Parameters:**
- `path` (optional) - 相对于项目根目录的路径，默认为空（根目录）

**Examples:**
```bash
# 获取根目录树
GET /api/projects/proj_abc123/tree

# 获取子目录树
GET /api/projects/proj_abc123/tree?path=src/api
```

**Response:**
```json
{
  "name": "my-project",
  "path": "",
  "type": "directory",
  "size": null,
  "modified_at": null,
  "children": [
    {
      "name": "src",
      "path": "src",
      "type": "directory",
      "size": null,
      "modified_at": null,
      "children": [
        {
          "name": "main.py",
          "path": "src/main.py",
          "type": "file",
          "size": 1024,
          "modified_at": "2026-02-01T10:00:00",
          "children": null
        }
      ]
    },
    {
      "name": "README.md",
      "path": "README.md",
      "type": "file",
      "size": 512,
      "modified_at": "2026-02-01T09:00:00",
      "children": null
    }
  ]
}
```

**FileNode 字段说明：**
- `name` - 文件/目录名
- `path` - 相对于项目根目录的路径（使用 `/` 分隔）
- `type` - `"file"` 或 `"directory"`
- `size` - 文件大小（字节），仅文件有此字段
- `modified_at` - 最后修改时间（ISO 8601 格式），仅文件有此字段
- `children` - 子节点数组，仅目录有此字段

**注意：**
- 隐藏文件（以 `.` 开头）会被自动过滤
- 子节点按名称排序
- 路径使用正斜杠 `/` 作为分隔符（跨平台兼容）

**Error Responses:**
- `400 Bad Request` - 路径无效或不存在
- `404 Not Found` - 项目不存在

### 7. Read File

**GET** `/api/projects/{project_id}/files?path={relative_path}`

读取文件内容。

**Query Parameters:**
- `path` (required) - 相对于项目根目录的文件路径

**Example:**
```bash
GET /api/projects/proj_abc123/files?path=src/main.py
```

**Response:**
```json
{
  "path": "src/main.py",
  "content": "# Python code\nprint('Hello, World!')\n",
  "encoding": "utf-8",
  "size": 1024,
  "mime_type": "text/x-python"
}
```

**FileContent 字段说明：**
- `path` - 文件相对路径
- `content` - 文件文本内容
- `encoding` - 文件编码（当前固定为 utf-8）
- `size` - 文件大小（字节）
- `mime_type` - MIME 类型

**文件类型限制（allowed_file_extensions）：**
```
.txt, .md, .py, .js, .ts, .tsx, .jsx,
.json, .yaml, .yml, .html, .css, .xml,
.java, .c, .cpp, .h, .go, .rs, .sql
```

**文件大小限制：**
- 默认最大 10MB（可通过配置修改）

**Error Responses:**
- `400 Bad Request` - 路径无效、文件不存在、文件类型不支持、文件过大
- `404 Not Found` - 项目不存在

---

## 数据模型

### Project

```typescript
interface Project {
  id: string;              // 项目唯一 ID，格式：proj_xxxxxxxxxxxx
  name: string;            // 项目名称（1-100 字符）
  root_path: string;       // 项目根目录绝对路径
  description?: string;    // 项目描述（可选，最多 500 字符）
  created_at: string;      // 创建时间（ISO 8601）
  updated_at: string;      // 更新时间（ISO 8601）
}
```

### FileNode

```typescript
interface FileNode {
  name: string;            // 文件/目录名
  path: string;            // 相对路径（使用 / 分隔）
  type: 'file' | 'directory';
  size?: number;           // 文件大小（字节），仅文件
  modified_at?: string;    // 修改时间（ISO 8601），仅文件
  children?: FileNode[];   // 子节点，仅目录
}
```

### FileContent

```typescript
interface FileContent {
  path: string;            // 文件相对路径
  content: string;         // 文件内容
  encoding: string;        // 文件编码（utf-8）
  size: number;            // 文件大小（字节）
  mime_type?: string;      // MIME 类型
}
```

---

## 配置说明

### 后端配置 (src/api/config.py)

```python
# 项目配置文件路径
projects_config_path: Path = Path("config/projects_config.yaml")

# 文件读取大小限制（MB）
max_file_read_size_mb: int = 10

# 允许的文件扩展名
allowed_file_extensions: List[str] = [
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".yaml", ".yml", ".html", ".css", ".xml",
    ".java", ".c", ".cpp", ".h", ".go", ".rs", ".sql"
]
```

### 项目配置文件 (config/projects_config.yaml)

```yaml
projects:
  - id: "proj_abc123456789"
    name: "My Django Project"
    root_path: "C:/Users/username/projects/django-app"
    description: "Django web application"
    created_at: "2026-02-01T10:00:00"
    updated_at: "2026-02-01T10:00:00"

  - id: "proj_def987654321"
    name: "React Frontend"
    root_path: "D:/work/react-frontend"
    description: "React TypeScript frontend"
    created_at: "2026-02-01T11:00:00"
    updated_at: "2026-02-01T11:00:00"
```

---

## 安全特性

### 1. 路径遍历防护

所有文件路径操作都经过严格验证，防止路径遍历攻击：

```python
# 这些攻击会被拦截
../../../etc/passwd
..\\..\\..\\windows\\system32
subdir/../../../../../../etc/passwd
```

**实现方式：**
- 使用 `Path.resolve()` 解析绝对路径
- 使用 `Path.is_relative_to()` 检查是否在项目目录内
- 拒绝任何试图访问项目根目录外的请求

### 2. 文件类型限制

只允许读取白名单中的文本文件类型：

```python
allowed_extensions = [".txt", ".md", ".py", ".js", ...]
```

尝试读取其他类型（如 `.exe`, `.dll`）会返回 400 错误。

### 3. 文件大小限制

默认限制单个文件最大 10MB，防止内存溢出：

```python
max_size = 10 * 1024 * 1024  # 10MB
```

### 4. 隐藏文件过滤

以 `.` 开头的隐藏文件（如 `.env`, `.git`）会被自动排除，不会出现在文件树中，也无法直接读取。

### 5. 路径规范化

所有路径都使用 `/` 作为分隔符，避免平台差异导致的安全问题。

---

## 测试覆盖

完整的测试套件位于 `tests/api/test_projects.py`，包含 31 个测试：

### CRUD 操作测试 (11 个)
- 加载空配置
- 添加项目
- 获取项目列表
- 获取单个项目
- 更新项目信息
- 删除项目
- 重复 ID 检测

### 文件树测试 (6 个)
- 根目录树
- 子目录树
- 空目录处理
- 无效路径处理
- 隐藏文件过滤

### 文件读取测试 (7 个)
- 读取文本文件
- UTF-8 编码处理
- 子目录文件读取
- 不存在的文件
- 文件大小限制
- 不支持的文件类型

### 安全测试 (7 个)
- 路径遍历攻击防护
- 隐藏文件访问拒绝
- 安全路径验证
- 路径验证成功/失败场景

**运行测试：**
```bash
./venv/Scripts/pytest tests/api/test_projects.py -v
```

---

## 使用示例

### 前端集成示例

```typescript
// 1. 创建项目
const createProject = async (name: string, rootPath: string) => {
  const response = await fetch('http://localhost:8888/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: name,
      root_path: rootPath,
      description: 'My project'
    })
  });
  return await response.json();
};

// 2. 获取项目列表
const getProjects = async () => {
  const response = await fetch('http://localhost:8888/api/projects');
  return await response.json();
};

// 3. 获取文件树
const getFileTree = async (projectId: string, path: string = '') => {
  const url = `http://localhost:8888/api/projects/${projectId}/tree?path=${path}`;
  const response = await fetch(url);
  return await response.json();
};

// 4. 读取文件
const readFile = async (projectId: string, filePath: string) => {
  const url = `http://localhost:8888/api/projects/${projectId}/files?path=${filePath}`;
  const response = await fetch(url);
  return await response.json();
};
```

### cURL 示例

```bash
# 创建项目
curl -X POST http://localhost:8888/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "root_path": "C:/Users/username/my-project",
    "description": "Test project"
  }'

# 获取项目列表
curl http://localhost:8888/api/projects

# 获取文件树（根目录）
curl http://localhost:8888/api/projects/proj_abc123/tree

# 获取文件树（子目录）
curl "http://localhost:8888/api/projects/proj_abc123/tree?path=src"

# 读取文件
curl "http://localhost:8888/api/projects/proj_abc123/files?path=README.md"

# 更新项目
curl -X PUT http://localhost:8888/api/projects/proj_abc123 \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'

# 删除项目
curl -X DELETE http://localhost:8888/api/projects/proj_abc123
```

---

## 前端开发建议

### 推荐的 UI 组件

1. **项目列表页**
   - 显示所有项目卡片
   - 每个卡片显示：名称、路径、描述
   - 操作按钮：打开、编辑、删除

2. **项目详情页**
   - 左侧：文件树（可展开/折叠的树形结构）
   - 右侧：文件内容查看器（代码高亮）
   - 顶部：面包屑导航

3. **创建/编辑项目对话框**
   - 项目名称输入框
   - 根目录路径选择（可能需要文件夹选择器）
   - 描述输入框

### 状态管理建议

```typescript
interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  currentFileTree: FileNode | null;
  currentFile: FileContent | null;
  loading: boolean;
  error: string | null;
}
```

### 文件树组件建议

- 使用递归组件渲染 FileNode
- 懒加载：只在用户展开目录时请求子目录的树
- 图标：区分文件和目录，根据扩展名显示不同图标
- 搜索/过滤功能

### 文件查看器建议

- 使用代码高亮库（如 Prism.js, Monaco Editor）
- 根据 `mime_type` 选择语法高亮
- 显示文件大小、修改时间等元数据
- 支持搜索功能

---

## 已知限制

1. **只读模式** - 当前不支持文件编辑、创建、删除
2. **无文件搜索** - 不支持在项目内搜索文件内容
3. **无分页** - 大型目录可能导致响应过大
4. **编码检测简单** - 当前固定使用 UTF-8，未来可集成 chardet
5. **无 Git 集成** - 不显示 Git 状态信息

---

## 未来增强计划

1. **文件操作**
   - 文件编辑/保存
   - 文件创建/删除/重命名
   - 文件上传

2. **高级功能**
   - 项目内全文搜索
   - Git 集成（显示文件变更状态）
   - 文件监听（实时更新）
   - 语法高亮元数据

3. **性能优化**
   - 文件树分页/虚拟滚动
   - 大文件流式读取
   - 缓存机制

4. **用户体验**
   - 文件预览（图片、PDF）
   - 多文件对比
   - 快捷键支持
