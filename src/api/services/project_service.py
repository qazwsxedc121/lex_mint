"""Service for managing projects and file operations."""

import yaml
import logging
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from src.api.models.project_config import (
    Project,
    ProjectsConfig,
    FileNode,
    FileContent,
    FileRenameResult
)
from src.api.config import settings

logger = logging.getLogger(__name__)

class ProjectService:
    """Service for managing projects and file operations."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize project service.

        Args:
            config_path: Path to projects config file (for testing)
        """
        self.config_path = config_path or settings.projects_config_path
        self._lock = asyncio.Lock()

    async def load_config(self) -> ProjectsConfig:
        """Load projects configuration from YAML file.

        Returns:
            ProjectsConfig with all projects
        """
        async with self._lock:
            if not self.config_path.exists():
                return ProjectsConfig(projects=[])

            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data is None:
                        return ProjectsConfig(projects=[])
                    raw_projects = data.get('projects', [])
                    valid_projects: List[Project] = []
                    if isinstance(raw_projects, list):
                        for index, raw in enumerate(raw_projects):
                            try:
                                valid_projects.append(Project.model_validate(raw))
                            except Exception as e:
                                logger.warning(f"Skipping invalid project entry at index {index}: {e}")
                    return ProjectsConfig(projects=valid_projects)
            except Exception as e:
                raise ValueError(f"Failed to load config: {e}")

    async def save_config(self, config: ProjectsConfig) -> None:
        """Save projects configuration to YAML file atomically.

        Args:
            config: ProjectsConfig to save
        """
        async with self._lock:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file first, then rename
            temp_path = self.config_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(
                        config.model_dump(),
                        f,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False
                    )
                # Atomic rename
                temp_path.replace(self.config_path)
            except Exception as e:
                # Clean up temp file on error
                if temp_path.exists():
                    temp_path.unlink()
                raise ValueError(f"Failed to save config: {e}")

    async def get_projects(self) -> List[Project]:
        """Get all projects.

        Returns:
            List of all projects
        """
        config = await self.load_config()
        return config.projects

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a single project by ID.

        Args:
            project_id: Project ID to find

        Returns:
            Project if found, None otherwise
        """
        config = await self.load_config()
        for project in config.projects:
            if project.id == project_id:
                return project
        return None

    async def add_project(self, project: Project) -> Project:
        """Add a new project.

        Args:
            project: Project to add

        Returns:
            The added project

        Raises:
            ValueError: If project ID already exists
        """
        config = await self.load_config()

        # Check for duplicate ID
        for existing in config.projects:
            if existing.id == project.id:
                raise ValueError(f"Project with ID '{project.id}' already exists")

        # Add project
        config.projects.append(project)
        await self.save_config(config)
        return project

    async def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        root_path: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Project]:
        """Update an existing project.

        Args:
            project_id: ID of project to update
            name: New name (optional)
            root_path: New root path (optional)
            description: New description (optional)

        Returns:
            Updated project if found, None otherwise
        """
        config = await self.load_config()

        # Find project
        for i, project in enumerate(config.projects):
            if project.id == project_id:
                # Update fields
                update_data = {}
                if name is not None:
                    update_data['name'] = name
                if root_path is not None:
                    update_data['root_path'] = root_path
                if description is not None:
                    update_data['description'] = description

                # Update timestamp
                update_data['updated_at'] = datetime.now().isoformat()

                # Create updated project
                updated_project = project.model_copy(update=update_data)
                config.projects[i] = updated_project
                await self.save_config(config)
                return updated_project

        return None

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project.

        Args:
            project_id: ID of project to delete

        Returns:
            True if deleted, False if not found
        """
        config = await self.load_config()
        original_count = len(config.projects)

        # Filter out the project
        config.projects = [p for p in config.projects if p.id != project_id]

        if len(config.projects) < original_count:
            await self.save_config(config)
            return True
        return False

    # Placeholder methods for Phase 3, 4, 5
    # These will be implemented in later phases

    async def get_file_tree(
        self,
        project_id: str,
        relative_path: str = ""
    ) -> FileNode:
        """Get file tree for a project directory.

        Args:
            project_id: Project ID
            relative_path: Relative path from project root (default: root)

        Returns:
            FileNode representing the directory tree

        Raises:
            ValueError: If project not found or path is invalid
        """
        # Validate path and get resolved paths
        root_path, target_path = await self._validate_path(project_id, relative_path)

        # Check that target is a directory
        if not target_path.is_dir():
            raise ValueError(f"Path is not a directory: {relative_path}")

        # Build and return tree
        return self._build_tree_node(root_path, target_path, relative_path)

    async def create_file(
        self,
        project_id: str,
        relative_path: str,
        content: str = "",
        encoding: str = "utf-8"
    ) -> FileContent:
        """Create a new file in a project.

        Args:
            project_id: Project ID
            relative_path: Relative path to file from project root
            content: Initial file content
            encoding: File encoding (default: utf-8)

        Returns:
            FileContent with created file data

        Raises:
            ValueError: If project not found, path invalid, or file cannot be created
        """
        # Get project
        project = await self.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        # Get root path
        root_path = Path(project.root_path)

        # Validate path
        if not relative_path or relative_path == ".":
            raise ValueError("File path is required")

        target_path = root_path / relative_path

        # Security check: prevent path traversal
        if not self._is_safe_path(root_path, target_path):
            raise ValueError(f"Invalid path: {relative_path}")

        # Check if file already exists
        if target_path.exists():
            raise ValueError(f"File already exists: {relative_path}")

        # Ensure parent directory exists
        if not target_path.parent.exists() or not target_path.parent.is_dir():
            parent_relative = (
                str(target_path.parent.relative_to(root_path))
                if target_path.parent.is_relative_to(root_path)
                else str(target_path.parent)
            )
            raise ValueError(f"Parent directory does not exist: {parent_relative}")

        # Check content size
        content_bytes = content.encode(encoding)
        content_size = len(content_bytes)
        max_size_bytes = settings.max_file_read_size_mb * 1024 * 1024
        if content_size > max_size_bytes:
            raise ValueError(
                f"Content size ({content_size} bytes) exceeds limit "
                f"({settings.max_file_read_size_mb}MB)"
            )

        # Create file (fail if exists)
        try:
            with target_path.open("x", encoding=encoding) as f:
                f.write(content)
        except FileExistsError:
            raise ValueError(f"File already exists: {relative_path}")
        except Exception as e:
            raise ValueError(f"Failed to create file: {e}")

        # Get file info and return
        file_size = target_path.stat().st_size
        file_ext = target_path.suffix.lower()
        mime_type = self._get_mime_type(file_ext)

        return FileContent(
            path=relative_path,
            content=content,
            encoding=encoding,
            size=file_size,
            mime_type=mime_type
        )

    async def create_directory(
        self,
        project_id: str,
        relative_path: str
    ) -> FileNode:
        """Create a new directory in a project.

        Args:
            project_id: Project ID
            relative_path: Relative path to directory from project root

        Returns:
            FileNode representing the created directory

        Raises:
            ValueError: If project not found, path invalid, or directory cannot be created
        """
        project = await self.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        root_path = Path(project.root_path)

        if not relative_path or relative_path == ".":
            raise ValueError("Directory path is required")

        target_path = root_path / relative_path

        if not self._is_safe_path(root_path, target_path):
            raise ValueError(f"Invalid path: {relative_path}")

        if target_path.exists():
            raise ValueError(f"Directory already exists: {relative_path}")

        if not target_path.parent.exists() or not target_path.parent.is_dir():
            parent_relative = (
                str(target_path.parent.relative_to(root_path))
                if target_path.parent.is_relative_to(root_path)
                else str(target_path.parent)
            )
            raise ValueError(f"Parent directory does not exist: {parent_relative}")

        try:
            target_path.mkdir()
        except FileExistsError:
            raise ValueError(f"Directory already exists: {relative_path}")
        except Exception as e:
            raise ValueError(f"Failed to create directory: {e}")

        return FileNode(
            name=target_path.name,
            path=relative_path,
            type="directory",
            children=[]
        )

    def _build_tree_node(self, root_path: Path, current_path: Path, relative_path: str) -> FileNode:
        """Recursively build a file tree node.

        Args:
            root_path: Project root path
            current_path: Current absolute path being processed
            relative_path: Relative path from project root

        Returns:
            FileNode for the current path
        """
        # Get basic info
        name = current_path.name if current_path != root_path else root_path.name
        is_dir = current_path.is_dir()
        node_type = "directory" if is_dir else "file"

        # Build node data
        node_data = {
            "name": name,
            "path": relative_path,
            "type": node_type
        }

        if is_dir:
            # Get children, excluding hidden files
            children = []
            try:
                for child in sorted(current_path.iterdir()):
                    # Skip hidden files (starting with .)
                    if child.name.startswith("."):
                        continue

                    # Calculate relative path for child
                    child_relative = str(Path(relative_path) / child.name) if relative_path else child.name
                    child_relative = child_relative.replace("\\\\", "/")  # Normalize to forward slashes

                    # Recursively build child node
                    child_node = self._build_tree_node(root_path, child, child_relative)
                    children.append(child_node)

                node_data["children"] = children
            except PermissionError:
                # If we can't read the directory, return empty children
                node_data["children"] = []
        else:
            # For files, add size and modified time
            try:
                stat = current_path.stat()
                node_data["size"] = stat.st_size
                node_data["modified_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except Exception:
                # If we can't get stats, just skip them
                pass

        return FileNode(**node_data)

    async def read_file(
        self,
        project_id: str,
        relative_path: str
    ) -> FileContent:
        """Read file content from a project.

        Args:
            project_id: Project ID
            relative_path: Relative path to file from project root

        Returns:
            FileContent with file data

        Raises:
            ValueError: If project not found, path invalid, or file cannot be read
        """
        # Validate path and get resolved paths
        root_path, target_path = await self._validate_path(project_id, relative_path)

        # Check that target is a file
        if not target_path.is_file():
            raise ValueError(f"Path is not a file: {relative_path}")

        # Check file size
        file_size = target_path.stat().st_size
        max_size_bytes = settings.max_file_read_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds limit "
                f"({settings.max_file_read_size_mb}MB)"
            )

        # Detect encoding and read content
        encoding = self._detect_encoding(target_path)
        try:
            content = target_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # If UTF-8 fails, try with errors='replace'
            content = target_path.read_text(encoding=encoding, errors='replace')

        # Determine MIME type (basic implementation)
        file_ext = target_path.suffix.lower()
        mime_type = self._get_mime_type(file_ext)

        return FileContent(
            path=relative_path,
            content=content,
            encoding=encoding,
            size=file_size,
            mime_type=mime_type
        )

    async def delete_directory(
        self,
        project_id: str,
        relative_path: str,
        recursive: bool = False
    ) -> None:
        """Delete a directory in a project.

        Args:
            project_id: Project ID
            relative_path: Relative path to directory from project root
            recursive: Whether to delete contents recursively

        Raises:
            ValueError: If project not found, path invalid, or directory cannot be deleted
        """
        if not relative_path or relative_path == ".":
            raise ValueError("Cannot delete root directory")

        root_path, target_path = await self._validate_path(project_id, relative_path)

        if target_path == root_path:
            raise ValueError("Cannot delete root directory")

        if not target_path.is_dir():
            raise ValueError(f"Path is not a directory: {relative_path}")

        try:
            if recursive:
                shutil.rmtree(target_path)
            else:
                target_path.rmdir()
        except OSError as e:
            if not recursive:
                raise ValueError("Directory is not empty")
            raise ValueError(f"Failed to delete directory: {e}")
        except Exception as e:
            raise ValueError(f"Failed to delete directory: {e}")

    async def rename_path(
        self,
        project_id: str,
        source_path: str,
        target_path: str
    ) -> FileRenameResult:
        """Rename or move a file/directory within a project.

        Args:
            project_id: Project ID
            source_path: Existing relative path from project root
            target_path: New relative path from project root

        Returns:
            FileRenameResult with updated metadata

        Raises:
            ValueError: If project not found, paths invalid, or rename fails
        """
        if not source_path or source_path == ".":
            raise ValueError("Source path is required")
        if not target_path or target_path == ".":
            raise ValueError("Target path is required")

        # Validate source path
        root_path, source_abs = await self._validate_path(project_id, source_path)

        if source_abs == root_path:
            raise ValueError("Cannot rename root directory")

        # Build and validate target path
        target_abs = root_path / target_path
        if not self._is_safe_path(root_path, target_abs):
            raise ValueError(f"Invalid path: {target_path}")

        if source_abs.resolve() == target_abs.resolve():
            raise ValueError("Source and target paths are the same")

        if target_abs.exists():
            raise ValueError(f"Target path already exists: {target_path}")

        if not target_abs.parent.exists() or not target_abs.parent.is_dir():
            parent_relative = (
                str(target_abs.parent.relative_to(root_path))
                if target_abs.parent.is_relative_to(root_path)
                else str(target_abs.parent)
            )
            raise ValueError(f"Parent directory does not exist: {parent_relative}")

        try:
            source_abs.replace(target_abs)
        except Exception as e:
            raise ValueError(f"Failed to rename path: {e}")

        node_type = "directory" if target_abs.is_dir() else "file"
        size = None
        modified_at = None
        if node_type == "file":
            try:
                stat = target_abs.stat()
                size = stat.st_size
                modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except Exception:
                pass

        normalized_source = source_path.replace("\\", "/")
        normalized_target = target_path.replace("\\", "/")

        return FileRenameResult(
            old_path=normalized_source,
            new_path=normalized_target,
            type=node_type,
            size=size,
            modified_at=modified_at
        )

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding.

        Args:
            file_path: Path to file

        Returns:
            Detected encoding (defaults to utf-8)
        """
        # For now, just return UTF-8
        # In the future, could use chardet library for better detection
        return "utf-8"

    def _get_mime_type(self, file_ext: str) -> str:
        """Get MIME type for file extension.

        Args:
            file_ext: File extension (with dot)

        Returns:
            MIME type string
        """
        mime_types = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".ts": "text/typescript",
            ".tsx": "text/typescript",
            ".jsx": "text/javascript",
            ".json": "application/json",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
            ".html": "text/html",
            ".css": "text/css",
            ".xml": "text/xml",
            ".java": "text/x-java",
            ".c": "text/x-c",
            ".cpp": "text/x-c++",
            ".h": "text/x-c",
            ".go": "text/x-go",
            ".rs": "text/x-rust",
            ".sql": "text/x-sql",
        }
        return mime_types.get(file_ext, "text/plain")

    def _is_safe_path(self, base_path: Path, target_path: Path) -> bool:
        """Check if target path is safely within base path.

        Args:
            base_path: Base directory path
            target_path: Target path to check

        Returns:
            True if safe, False otherwise
        """
        try:
            # Resolve both paths to absolute paths
            base_resolved = base_path.resolve()
            target_resolved = target_path.resolve()

            # Check if target is relative to base
            return target_resolved.is_relative_to(base_resolved)
        except (ValueError, OSError):
            return False

    async def _validate_path(
        self,
        project_id: str,
        relative_path: str
    ) -> tuple[Path, Path]:
        """Validate and resolve a path within a project.

        Args:
            project_id: Project ID
            relative_path: Relative path from project root

        Returns:
            Tuple of (project_root_path, resolved_target_path)

        Raises:
            ValueError: If validation fails
        """
        # Get project
        project = await self.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        # Get root path
        root_path = Path(project.root_path)

        # If relative_path is empty, return root
        if not relative_path or relative_path == ".":
            return root_path, root_path

        # Build target path
        target_path = root_path / relative_path

        # Security check: prevent path traversal
        if not self._is_safe_path(root_path, target_path):
            raise ValueError(f"Invalid path: {relative_path}")

        # Check if path exists
        if not target_path.exists():
            raise ValueError(f"Path does not exist: {relative_path}")

        return root_path, target_path

    async def write_file(
        self,
        project_id: str,
        relative_path: str,
        content: str,
        encoding: str = "utf-8"
    ) -> FileContent:
        """Write content to a file in a project.

        Args:
            project_id: Project ID
            relative_path: Relative path to file from project root
            content: Content to write
            encoding: File encoding (default: utf-8)

        Returns:
            FileContent with updated file data

        Raises:
            ValueError: If project not found, path invalid, or file cannot be written
        """
        # Get project
        project = await self.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        # Get root path
        root_path = Path(project.root_path)

        # Build target path
        if not relative_path or relative_path == ".":
            raise ValueError("Cannot write to root directory")

        target_path = root_path / relative_path

        # Security check: prevent path traversal
        if not self._is_safe_path(root_path, target_path):
            raise ValueError(f"Invalid path: {relative_path}")

        # Check content size
        content_bytes = content.encode(encoding)
        content_size = len(content_bytes)
        max_size_bytes = settings.max_file_read_size_mb * 1024 * 1024
        if content_size > max_size_bytes:
            raise ValueError(
                f"Content size ({content_size} bytes) exceeds limit "
                f"({settings.max_file_read_size_mb}MB)"
            )

        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file first, then rename
        temp_path = target_path.with_suffix(target_path.suffix + '.tmp')
        try:
            temp_path.write_text(content, encoding=encoding)
            # Atomic rename
            temp_path.replace(target_path)
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise ValueError(f"Failed to write file: {e}")

        # Get file info and return
        file_size = target_path.stat().st_size
        file_ext = target_path.suffix.lower()
        mime_type = self._get_mime_type(file_ext)

        return FileContent(
            path=relative_path,
            content=content,
            encoding=encoding,
            size=file_size,
            mime_type=mime_type
        )

    async def delete_file(
        self,
        project_id: str,
        relative_path: str
    ) -> None:
        """Delete a file in a project.

        Args:
            project_id: Project ID
            relative_path: Relative path to file from project root

        Raises:
            ValueError: If project not found, path invalid, or file cannot be deleted
        """
        if not relative_path or relative_path == ".":
            raise ValueError("File path is required")

        root_path, target_path = await self._validate_path(project_id, relative_path)

        if target_path == root_path:
            raise ValueError("Cannot delete root directory")

        if not target_path.is_file():
            raise ValueError(f"Path is not a file: {relative_path}")

        try:
            target_path.unlink()
        except Exception as e:
            raise ValueError(f"Failed to delete file: {e}")
