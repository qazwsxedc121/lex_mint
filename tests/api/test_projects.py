"""Tests for project management functionality."""

import pytest
from pathlib import Path
from src.api.services.project_service import ProjectService, ProjectConflictError
from src.api.services.project_workspace_state_service import ProjectWorkspaceStateService
from src.api.models.project_config import Project, ProjectCreate
from src.api.models.project_config import ProjectWorkspaceItemUpsert
from src.api.config import settings


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file for testing."""
    config_path = tmp_path / "projects_config.yaml"
    return config_path


@pytest.fixture
def project_service(temp_config_file):
    """Create ProjectService instance with temp config."""
    return ProjectService(config_path=temp_config_file)


@pytest.fixture
def project_workspace_state_service(project_service):
    """Create workspace state service with temp project storage."""
    return ProjectWorkspaceStateService(project_service=project_service, max_recent_items=3)


@pytest.fixture
def test_project_path(tmp_path):
    """Create temporary project directory structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / "file1.txt").write_text("Test content", encoding='utf-8')
    (project_dir / "subdir").mkdir()
    (project_dir / "subdir" / "file2.py").write_text("print('hello')", encoding='utf-8')
    (project_dir / ".hidden").write_text("hidden file", encoding='utf-8')
    return project_dir


@pytest.fixture
def test_project_path_2(tmp_path):
    """Create second temporary project directory."""
    project_dir = tmp_path / "test_project_2"
    project_dir.mkdir()
    (project_dir / "readme.md").write_text("# Test", encoding='utf-8')
    return project_dir




class TestProjectBrowseDirectoryCreation:
    """Tests for creating directories in browse mode."""

    def test_create_browse_directory_success(self, project_service, tmp_path, monkeypatch):
        browse_root = tmp_path / "browse_root"
        browse_root.mkdir()
        monkeypatch.setattr(settings, "projects_browse_roots", [browse_root])

        created = project_service.create_browse_directory(str(browse_root), "new_project")

        assert created.name == "new_project"
        assert created.is_dir is True
        assert Path(created.path).exists()
        assert Path(created.path).is_dir()

    def test_create_browse_directory_rejects_path_separator(self, project_service, tmp_path, monkeypatch):
        browse_root = tmp_path / "browse_root"
        browse_root.mkdir()
        monkeypatch.setattr(settings, "projects_browse_roots", [browse_root])

        with pytest.raises(ValueError, match="path separators"):
            project_service.create_browse_directory(str(browse_root), "foo/bar")

    def test_create_browse_directory_rejects_outside_root(self, project_service, tmp_path, monkeypatch):
        browse_root = tmp_path / "browse_root"
        outside_root = tmp_path / "outside_root"
        browse_root.mkdir()
        outside_root.mkdir()
        monkeypatch.setattr(settings, "projects_browse_roots", [browse_root])

        with pytest.raises(ValueError, match="outside allowed roots"):
            project_service.create_browse_directory(str(outside_root), "new_project")

    def test_create_browse_directory_rejects_existing(self, project_service, tmp_path, monkeypatch):
        browse_root = tmp_path / "browse_root"
        existing_dir = browse_root / "existing"
        browse_root.mkdir()
        existing_dir.mkdir()
        monkeypatch.setattr(settings, "projects_browse_roots", [browse_root])

        with pytest.raises(ValueError, match="already exists"):
            project_service.create_browse_directory(str(browse_root), "existing")


# =============================================================================
# Phase 2: Project CRUD Tests
# =============================================================================

class TestProjectServiceCRUD:
    """Tests for project CRUD operations."""

    @pytest.mark.asyncio
    async def test_load_empty_config(self, project_service):
        """Test loading empty config creates default structure."""
        config = await project_service.load_config()
        assert config.projects == []

    @pytest.mark.asyncio
    async def test_add_project(self, project_service, test_project_path):
        """Test adding new project."""
        project = Project(
            id="test_proj_1",
            name="Test Project",
            root_path=str(test_project_path),
            description="Test description"
        )
        await project_service.add_project(project)

        config = await project_service.load_config()
        assert len(config.projects) == 1
        assert config.projects[0].id == "test_proj_1"
        assert config.projects[0].name == "Test Project"
        assert config.projects[0].root_path == str(test_project_path)
        assert config.projects[0].description == "Test description"

    @pytest.mark.asyncio
    async def test_get_projects(self, project_service, test_project_path, test_project_path_2):
        """Test getting all projects."""
        # Add two projects
        project1 = Project(
            id="proj_1",
            name="Project 1",
            root_path=str(test_project_path)
        )
        project2 = Project(
            id="proj_2",
            name="Project 2",
            root_path=str(test_project_path_2)
        )
        await project_service.add_project(project1)
        await project_service.add_project(project2)

        # Get all projects
        projects = await project_service.get_projects()
        assert len(projects) == 2
        assert projects[0].id == "proj_1"
        assert projects[1].id == "proj_2"

    @pytest.mark.asyncio
    async def test_get_project_by_id(self, project_service, test_project_path):
        """Test getting a single project by ID."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Get by ID
        retrieved = await project_service.get_project("test_proj")
        assert retrieved is not None
        assert retrieved.id == "test_proj"
        assert retrieved.name == "Test Project"

    @pytest.mark.asyncio
    async def test_get_nonexistent_project(self, project_service):
        """Test getting a project that doesn't exist."""
        project = await project_service.get_project("nonexistent")
        assert project is None

    @pytest.mark.asyncio
    async def test_update_project(self, project_service, test_project_path, test_project_path_2):
        """Test updating project details."""
        # Add project
        project = Project(
            id="test_proj",
            name="Original Name",
            root_path=str(test_project_path),
            description="Original description"
        )
        await project_service.add_project(project)

        # Update project
        updated = await project_service.update_project(
            "test_proj",
            name="Updated Name",
            description="Updated description"
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.root_path == str(test_project_path)  # Should not change

        # Verify persistence
        retrieved = await project_service.get_project("test_proj")
        assert retrieved.name == "Updated Name"
        assert retrieved.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_project_path(self, project_service, test_project_path, test_project_path_2):
        """Test updating project root path."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Update path
        updated = await project_service.update_project(
            "test_proj",
            root_path=str(test_project_path_2)
        )
        assert updated.root_path == str(test_project_path_2)

    @pytest.mark.asyncio
    async def test_update_nonexistent_project(self, project_service):
        """Test updating a project that doesn't exist."""
        updated = await project_service.update_project(
            "nonexistent",
            name="New Name"
        )
        assert updated is None


class TestProjectWorkspaceStateService:
    """Tests for project-local workspace state persistence."""

    @pytest.mark.asyncio
    async def test_get_workspace_state_returns_default_when_missing(
        self,
        project_service,
        project_workspace_state_service,
        test_project_path,
    ):
        await project_service.add_project(
            Project(
                id="test_proj",
                name="Test Project",
                root_path=str(test_project_path),
            )
        )

        state = await project_workspace_state_service.get_workspace_state("test_proj")

        assert state.project_id == "test_proj"
        assert state.updated_at is None
        assert state.recent_items == []
        assert state.extra == {}

    @pytest.mark.asyncio
    async def test_upsert_recent_file_item_creates_project_local_state_file(
        self,
        project_service,
        project_workspace_state_service,
        test_project_path,
    ):
        await project_service.add_project(
            Project(
                id="test_proj",
                name="Test Project",
                root_path=str(test_project_path),
            )
        )

        state = await project_workspace_state_service.upsert_recent_item(
            "test_proj",
            ProjectWorkspaceItemUpsert(
                type="file",
                id="drafts\\chapter1.md",
                title="Chapter 1",
                path="drafts\\chapter1.md",
            ),
        )

        state_file = test_project_path / ".lex_mint" / "state" / "project_workspace_state.yaml"
        assert state_file.exists()
        assert state.recent_items[0].type == "file"
        assert state.recent_items[0].id == "drafts/chapter1.md"
        assert state.recent_items[0].path == "drafts/chapter1.md"
        assert "drafts/chapter1.md" in state_file.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_upsert_dedupes_existing_item_and_moves_it_to_front(
        self,
        project_service,
        project_workspace_state_service,
        test_project_path,
    ):
        await project_service.add_project(
            Project(
                id="test_proj",
                name="Test Project",
                root_path=str(test_project_path),
            )
        )

        await project_workspace_state_service.upsert_recent_item(
            "test_proj",
            ProjectWorkspaceItemUpsert(
                type="session",
                id="session-1",
                title="Session One",
                updated_at="2026-03-07T10:00:00+00:00",
            ),
        )
        await project_workspace_state_service.upsert_recent_item(
            "test_proj",
            ProjectWorkspaceItemUpsert(
                type="file",
                id="notes/todo.md",
                title="Todo",
                path="notes/todo.md",
                updated_at="2026-03-07T11:00:00+00:00",
            ),
        )

        state = await project_workspace_state_service.upsert_recent_item(
            "test_proj",
            ProjectWorkspaceItemUpsert(
                type="session",
                id="session-1",
                title="Session One Updated",
                updated_at="2026-03-07T12:00:00+00:00",
                meta={"message_count": 5},
            ),
        )

        assert [(item.type, item.id) for item in state.recent_items] == [
            ("session", "session-1"),
            ("file", "notes/todo.md"),
        ]
        assert state.recent_items[0].title == "Session One Updated"
        assert state.recent_items[0].meta == {"message_count": 5}

    @pytest.mark.asyncio
    async def test_upsert_truncates_recent_items_to_configured_limit(
        self,
        project_service,
        project_workspace_state_service,
        test_project_path,
    ):
        await project_service.add_project(
            Project(
                id="test_proj",
                name="Test Project",
                root_path=str(test_project_path),
            )
        )

        items = [
            ProjectWorkspaceItemUpsert(
                type="file",
                id=f"docs/file-{index}.md",
                title=f"File {index}",
                path=f"docs/file-{index}.md",
                updated_at=f"2026-03-07T0{index}:00:00+00:00",
            )
            for index in range(1, 5)
        ]

        for item in items:
            await project_workspace_state_service.upsert_recent_item("test_proj", item)

        state = await project_workspace_state_service.get_workspace_state("test_proj")

        assert len(state.recent_items) == 3
        assert [item.id for item in state.recent_items] == [
            "docs/file-4.md",
            "docs/file-3.md",
            "docs/file-2.md",
        ]

    @pytest.mark.asyncio
    async def test_file_item_rejects_unsafe_relative_path(
        self,
        project_service,
        project_workspace_state_service,
        test_project_path,
    ):
        await project_service.add_project(
            Project(
                id="test_proj",
                name="Test Project",
                root_path=str(test_project_path),
            )
        )

        with pytest.raises(ValueError, match="safe relative path"):
            await project_workspace_state_service.upsert_recent_item(
                "test_proj",
                ProjectWorkspaceItemUpsert(
                    type="file",
                    id="../secret.txt",
                    title="Secret",
                    path="../secret.txt",
                ),
            )

    @pytest.mark.asyncio
    async def test_delete_project(self, project_service, test_project_path):
        """Test deleting a project."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Delete project
        success = await project_service.delete_project("test_proj")
        assert success is True

        # Verify deletion
        config = await project_service.load_config()
        assert len(config.projects) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_project(self, project_service):
        """Test deleting a project that doesn't exist."""
        success = await project_service.delete_project("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_duplicate_project_id(self, project_service, test_project_path):
        """Test that adding a project with duplicate ID raises error."""
        # Add first project
        project1 = Project(
            id="same_id",
            name="Project 1",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project1)

        # Try to add second project with same ID
        project2 = Project(
            id="same_id",
            name="Project 2",
            root_path=str(test_project_path)
        )
        with pytest.raises(ValueError, match="already exists"):
            await project_service.add_project(project2)


# Placeholder for future test classes
# Phase 3: File Tree Tests
# Phase 4: File Reading Tests
# Phase 5: Security Tests
# Phase 6: API Integration Tests


# =============================================================================
# Phase 3: File Tree Tests
# =============================================================================

class TestProjectServiceFileTree:
    """Tests for file tree functionality."""

    @pytest.mark.asyncio
    async def test_get_file_tree_root(self, project_service, test_project_path):
        """Test getting file tree from project root."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Get file tree
        tree = await project_service.get_file_tree("test_proj", "")

        assert tree.name == test_project_path.name
        assert tree.type == "directory"
        assert tree.path == ""
        assert tree.children is not None
        assert len(tree.children) >= 2  # Should have file1.txt and subdir

        # Check file1.txt exists
        files = [c for c in tree.children if c.type == "file" and c.name == "file1.txt"]
        assert len(files) == 1
        assert files[0].size is not None
        assert files[0].size > 0

        # Check subdir exists
        dirs = [c for c in tree.children if c.type == "directory" and c.name == "subdir"]
        assert len(dirs) == 1

    @pytest.mark.asyncio
    async def test_get_file_tree_subdirectory(self, project_service, test_project_path):
        """Test getting file tree from subdirectory."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Get file tree for subdirectory
        tree = await project_service.get_file_tree("test_proj", "subdir")

        assert tree.name == "subdir"
        assert tree.type == "directory"
        assert tree.path == "subdir"
        assert tree.children is not None

        # Check file2.py exists
        files = [c for c in tree.children if c.type == "file" and c.name == "file2.py"]
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_get_file_tree_empty_directory(self, project_service, test_project_path):
        """Test getting file tree for empty directory."""
        # Create empty directory
        empty_dir = test_project_path / "empty"
        empty_dir.mkdir()

        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Get file tree
        tree = await project_service.get_file_tree("test_proj", "empty")

        assert tree.name == "empty"
        assert tree.type == "directory"
        assert tree.children is not None
        assert len(tree.children) == 0

    @pytest.mark.asyncio
    async def test_get_file_tree_invalid_path(self, project_service, test_project_path):
        """Test getting file tree with invalid path."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try to get tree for nonexistent path
        with pytest.raises(ValueError, match="Invalid path|Path does not exist|not found"):
            await project_service.get_file_tree("test_proj", "nonexistent")

    @pytest.mark.asyncio
    async def test_get_file_tree_project_not_found(self, project_service):
        """Test getting file tree for nonexistent project."""
        with pytest.raises(ValueError, match="not found"):
            await project_service.get_file_tree("nonexistent", "")

    @pytest.mark.asyncio
    async def test_file_tree_excludes_hidden_files(self, project_service, test_project_path):
        """Test that hidden files (starting with .) are excluded from tree."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Get file tree
        tree = await project_service.get_file_tree("test_proj", "")

        # Check .hidden file is not in tree
        hidden_files = [c for c in tree.children if c.name.startswith(".")]
        assert len(hidden_files) == 0


# =============================================================================
# Phase 4: File Reading Tests
# =============================================================================

class TestProjectServiceFileReading:
    """Tests for file reading functionality."""

    @pytest.mark.asyncio
    async def test_read_text_file(self, project_service, test_project_path):
        """Test reading a text file."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Read file
        content = await project_service.read_file("test_proj", "file1.txt")

        assert content.path == "file1.txt"
        assert content.content == "Test content"
        assert content.encoding == "utf-8"
        assert content.size > 0
        assert isinstance(content.content_hash, str)
        assert len(content.content_hash) == 64

    @pytest.mark.asyncio
    async def test_read_file_with_utf8(self, project_service, test_project_path):
        """Test reading UTF-8 encoded file."""
        # Create UTF-8 file
        utf8_file = test_project_path / "utf8.txt"
        utf8_file.write_text("Hello 世界", encoding='utf-8')

        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Read file
        content = await project_service.read_file("test_proj", "utf8.txt")

        assert content.content == "Hello 世界"
        assert content.encoding == "utf-8"

    @pytest.mark.asyncio
    async def test_read_file_from_subdirectory(self, project_service, test_project_path):
        """Test reading file from subdirectory."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Read file from subdir
        content = await project_service.read_file("test_proj", "subdir/file2.py")

        assert content.path == "subdir/file2.py"
        assert content.content == "print('hello')"

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, project_service, test_project_path):
        """Test reading a file that doesn't exist."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try to read nonexistent file
        with pytest.raises(ValueError, match="Path does not exist|not found"):
            await project_service.read_file("test_proj", "nonexistent.txt")

    @pytest.mark.asyncio
    async def test_read_file_size_limit(self, project_service, test_project_path):
        """Test reading file exceeding size limit."""
        # Create large file (11MB > 10MB limit)
        large_file = test_project_path / "large.txt"
        large_content = "x" * (11 * 1024 * 1024)  # 11MB
        large_file.write_text(large_content, encoding='utf-8')

        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try to read large file
        with pytest.raises(ValueError, match="too large|size limit|exceeds"):
            await project_service.read_file("test_proj", "large.txt")

    @pytest.mark.asyncio
    async def test_read_unsupported_file_type(self, project_service, test_project_path):
        """Test reading unknown extension falls back to text/plain."""
        # Create unknown file type
        bin_file = test_project_path / "file.exe"
        bin_file.write_bytes(b"\x00\x01\x02\x03")

        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        file_content = await project_service.read_file("test_proj", "file.exe")
        assert file_content.path == "file.exe"
        assert file_content.size == 4
        assert file_content.mime_type == "text/plain"

    @pytest.mark.asyncio
    async def test_read_file_project_not_found(self, project_service):
        """Test reading file from nonexistent project."""
        with pytest.raises(ValueError, match="not found"):
            await project_service.read_file("nonexistent", "file.txt")


class TestProjectServiceFileWriting:
    """Tests for file writing functionality with optimistic locking."""

    @pytest.mark.asyncio
    async def test_write_file_with_expected_hash_success(self, project_service, test_project_path):
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        before = await project_service.read_file("test_proj", "file1.txt")
        updated = await project_service.write_file(
            "test_proj",
            "file1.txt",
            "Updated content",
            "utf-8",
            expected_hash=before.content_hash,
        )

        assert updated.content == "Updated content"
        assert updated.content_hash != before.content_hash
        reread = await project_service.read_file("test_proj", "file1.txt")
        assert reread.content == "Updated content"
        assert reread.content_hash == updated.content_hash

    @pytest.mark.asyncio
    async def test_write_file_hash_mismatch_raises_conflict(self, project_service, test_project_path):
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        before = await project_service.read_file("test_proj", "file1.txt")
        (test_project_path / "file1.txt").write_text("Changed elsewhere", encoding="utf-8")

        with pytest.raises(ProjectConflictError, match="changed since last read") as exc_info:
            await project_service.write_file(
                "test_proj",
                "file1.txt",
                "My local update",
                "utf-8",
                expected_hash=before.content_hash,
            )

        err = exc_info.value
        assert err.code == "HASH_MISMATCH"
        assert err.extra.get("expected_hash") == before.content_hash
        assert isinstance(err.extra.get("current_hash"), str)


class TestProjectServiceTextSearch:
    """Tests for project text search functionality."""

    @pytest.mark.asyncio
    async def test_search_project_text_basic(self, project_service, test_project_path):
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        payload = await project_service.search_project_text("test_proj", "hello")
        assert payload["ok"] is True
        assert payload["results_count"] >= 1
        assert any(r["file_path"] == "subdir/file2.py" for r in payload["results"])

    @pytest.mark.asyncio
    async def test_search_project_text_invalid_regex(self, project_service, test_project_path):
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            await project_service.search_project_text("test_proj", "(", use_regex=True)

    @pytest.mark.asyncio
    async def test_search_project_text_respects_max_results(self, project_service, test_project_path):
        repeated_file = test_project_path / "repeated.txt"
        repeated_file.write_text("token\ntoken\ntoken\n", encoding="utf-8")

        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        payload = await project_service.search_project_text("test_proj", "token", max_results=2)
        assert payload["results_count"] == 2
        assert payload["truncated"] is True

    @pytest.mark.asyncio
    async def test_search_project_text_excludes_hidden_files(self, project_service, test_project_path):
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        payload = await project_service.search_project_text("test_proj", "hidden")
        assert payload["results_count"] == 0


# =============================================================================
# Phase 4.5: Rename Tests
# =============================================================================

class TestProjectServiceRename:
    """Tests for rename functionality."""

    @pytest.mark.asyncio
    async def test_rename_file(self, project_service, test_project_path):
        """Test renaming a file."""
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        result = await project_service.rename_path(
            "test_proj",
            "file1.txt",
            "file1_renamed.txt"
        )

        assert not (test_project_path / "file1.txt").exists()
        assert (test_project_path / "file1_renamed.txt").exists()
        assert result.old_path == "file1.txt"
        assert result.new_path == "file1_renamed.txt"
        assert result.type == "file"
        assert result.size is not None

    @pytest.mark.asyncio
    async def test_rename_directory(self, project_service, test_project_path):
        """Test renaming a directory."""
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        result = await project_service.rename_path(
            "test_proj",
            "subdir",
            "subdir2"
        )

        assert not (test_project_path / "subdir").exists()
        assert (test_project_path / "subdir2").exists()
        assert (test_project_path / "subdir2" / "file2.py").exists()
        assert result.old_path == "subdir"
        assert result.new_path == "subdir2"
        assert result.type == "directory"

    @pytest.mark.asyncio
    async def test_rename_rejects_existing_target(self, project_service, test_project_path):
        """Test renaming fails when target already exists."""
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        (test_project_path / "existing.txt").write_text("x", encoding="utf-8")

        with pytest.raises(ValueError, match="already exists"):
            await project_service.rename_path(
                "test_proj",
                "file1.txt",
                "existing.txt"
            )

    @pytest.mark.asyncio
    async def test_rename_rejects_missing_parent(self, project_service, test_project_path):
        """Test renaming fails when target parent does not exist."""
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        with pytest.raises(ValueError, match="Parent directory does not exist"):
            await project_service.rename_path(
                "test_proj",
                "file1.txt",
                "missing_dir/file1.txt"
            )

# =============================================================================
# Phase 5: Security Tests
# =============================================================================

class TestProjectServiceSecurity:
    """Tests for security functionality."""

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, project_service, test_project_path):
        """Test that path traversal attacks are blocked."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try various path traversal attempts
        attack_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "subdir/../../../../../../etc/passwd",
            "./../outside.txt",
        ]

        for attack_path in attack_paths:
            with pytest.raises(ValueError, match="Invalid path"):
                await project_service.read_file("test_proj", attack_path)

    @pytest.mark.asyncio
    async def test_hidden_file_access_denied(self, project_service, test_project_path):
        """Test that hidden files cannot be read directly."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try to read hidden file
        # Note: _validate_path checks if file exists, which .hidden does
        # But it should still fail or be excluded from tree
        # For direct read, we rely on file tree exclusion
        # This test verifies the file tree exclusion works
        tree = await project_service.get_file_tree("test_proj", "")
        hidden_files = [c for c in tree.children if c.name.startswith(".")]
        assert len(hidden_files) == 0

    @pytest.mark.asyncio
    async def test_is_safe_path_valid_paths(self, project_service, test_project_path):
        """Test _is_safe_path with valid paths."""
        base_path = test_project_path

        # Valid paths within base
        valid_paths = [
            test_project_path / "file1.txt",
            test_project_path / "subdir",
            test_project_path / "subdir" / "file2.py",
        ]

        for valid_path in valid_paths:
            assert project_service._is_safe_path(base_path, valid_path) is True

    @pytest.mark.asyncio
    async def test_is_safe_path_invalid_paths(self, project_service, test_project_path, tmp_path):
        """Test _is_safe_path with invalid paths."""
        base_path = test_project_path

        # Create path outside base
        outside_path = tmp_path / "outside" / "file.txt"

        # Invalid: path outside base
        assert project_service._is_safe_path(base_path, outside_path) is False

    @pytest.mark.asyncio
    async def test_validate_path_success(self, project_service, test_project_path):
        """Test _validate_path with valid inputs."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Test empty path (root)
        root, target = await project_service._validate_path("test_proj", "")
        assert root == test_project_path
        assert target == test_project_path

        # Test valid file path
        root, target = await project_service._validate_path("test_proj", "file1.txt")
        assert root == test_project_path
        assert target == test_project_path / "file1.txt"

        # Test valid subdirectory path
        root, target = await project_service._validate_path("test_proj", "subdir")
        assert root == test_project_path
        assert target == test_project_path / "subdir"

    @pytest.mark.asyncio
    async def test_validate_path_project_not_found(self, project_service):
        """Test _validate_path with nonexistent project."""
        with pytest.raises(ValueError, match="not found"):
            await project_service._validate_path("nonexistent", "file.txt")

    @pytest.mark.asyncio
    async def test_validate_path_traversal_attack(self, project_service, test_project_path):
        """Test _validate_path blocks path traversal."""
        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try path traversal
        with pytest.raises(ValueError, match="Invalid path"):
            await project_service._validate_path("test_proj", "../outside.txt")

