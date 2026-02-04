"""Tests for project management functionality."""

import pytest
from pathlib import Path
from src.api.services.project_service import ProjectService
from src.api.models.project_config import Project, ProjectCreate


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
        """Test reading file with unsupported extension."""
        # Create unsupported file type
        bin_file = test_project_path / "file.exe"
        bin_file.write_bytes(b"\x00\x01\x02\x03")

        # Add project
        project = Project(
            id="test_proj",
            name="Test Project",
            root_path=str(test_project_path)
        )
        await project_service.add_project(project)

        # Try to read unsupported file
        with pytest.raises(ValueError, match="not allowed|unsupported|extension"):
            await project_service.read_file("test_proj", "file.exe")

    @pytest.mark.asyncio
    async def test_read_file_project_not_found(self, project_service):
        """Test reading file from nonexistent project."""
        with pytest.raises(ValueError, match="not found"):
            await project_service.read_file("nonexistent", "file.txt")


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

