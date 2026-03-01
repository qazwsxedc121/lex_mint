"""Projects API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging
import uuid
from pydantic import BaseModel

from ..services.project_service import ProjectService
from ..services.project_service import ProjectConflictError
from ..services.project_document_tool_service import (
    ConfirmPendingPatchArgs,
    ProjectDocumentToolError,
    confirm_pending_patch_apply,
)
from ..models.project_config import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    FileNode,
    FileContent,
    FileCreate,
    FileWrite,
    FileRename,
    FileRenameResult,
    DirectoryCreate,
    DirectoryEntry,
    BrowseDirectoryCreate
)
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Service instance
_project_service: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    """Get or create project service instance."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service


class ProjectChatApplyDiffResponse(BaseModel):
    """Response model for confirmed project chat diff apply."""

    ok: bool
    file_path: str
    new_content_hash: str
    updated_at: int
    content: str


@router.get("", response_model=List[Project])
async def list_projects():
    """Get all projects.

    Returns:
        List of all projects
    """
    try:
        service = get_project_service()
        projects = await service.get_projects()
        return projects
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browse/roots", response_model=List[DirectoryEntry])
async def list_browse_roots():
    """List allowed root directories for server-side project selection."""
    try:
        service = get_project_service()
        return service.list_browse_roots()
    except Exception as e:
        logger.error(f"Error listing browse roots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browse", response_model=List[DirectoryEntry])
async def list_directories(
    path: str = Query(..., description="Absolute directory path on server")
):
    """List child directories for a server-side path."""
    try:
        service = get_project_service()
        return service.list_directories(path)
    except ValueError as e:
        logger.error(f"Validation error listing directories: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing directories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browse/directories", response_model=DirectoryEntry, status_code=201)
async def create_browse_directory(directory_data: BrowseDirectoryCreate):
    """Create a new directory under an allowed server-side browse path."""
    try:
        service = get_project_service()
        return service.create_browse_directory(directory_data.parent_path, directory_data.name)
    except ValueError as e:
        logger.error(f"Validation error creating browse directory: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating browse directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Project, status_code=201)
async def create_project(project_data: ProjectCreate):
    """Create a new project.

    Args:
        project_data: Project creation data

    Returns:
        Created project

    Raises:
        HTTPException: If project creation fails
    """
    try:
        service = get_project_service()

        # Generate unique ID
        project_id = f"proj_{uuid.uuid4().hex[:12]}"

        # Create project
        project = Project(
            id=project_id,
            name=project_data.name,
            root_path=project_data.root_path,
            description=project_data.description
        )

        # Add to storage
        created = await service.add_project(project)
        return created
    except ValueError as e:
        logger.error(f"Validation error creating project: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """Get a single project by ID.

    Args:
        project_id: Project ID

    Returns:
        Project details

    Raises:
        HTTPException: If project not found
    """
    try:
        service = get_project_service()
        project = await service.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}", response_model=Project)
async def update_project(project_id: str, update_data: ProjectUpdate):
    """Update an existing project.

    Args:
        project_id: Project ID
        update_data: Fields to update

    Returns:
        Updated project

    Raises:
        HTTPException: If project not found or update fails
    """
    try:
        service = get_project_service()

        # Update project
        updated = await service.update_project(
            project_id,
            name=update_data.name,
            root_path=update_data.root_path,
            description=update_data.description
        )

        if updated is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

        return updated
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating project {project_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str):
    """Delete a project.

    Args:
        project_id: Project ID

    Raises:
        HTTPException: If project not found
    """
    try:
        service = get_project_service()
        success = await service.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/tree", response_model=FileNode)
async def get_file_tree(
    project_id: str,
    path: str = Query("", description="Relative path from project root (default: root)")
):
    """Get file tree for a project directory.

    Args:
        project_id: Project ID
        path: Relative path from project root (optional)

    Returns:
        File tree structure

    Raises:
        HTTPException: If project not found or path invalid
    """
    try:
        service = get_project_service()
        tree = await service.get_file_tree(project_id, path)
        return tree
    except ValueError as e:
        logger.error(f"Validation error getting file tree: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting file tree for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/files", response_model=FileContent)
async def read_file(
    project_id: str,
    path: str = Query(..., description="Relative path to file from project root")
):
    """Read file content from a project.

    Args:
        project_id: Project ID
        path: Relative path to file

    Returns:
        File content

    Raises:
        HTTPException: If project not found, path invalid, or file cannot be read
    """
    try:
        service = get_project_service()
        content = await service.read_file(project_id, path)
        return content
    except ValueError as e:
        logger.error(f"Validation error reading file: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reading file from {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/files", response_model=FileContent, status_code=201)
async def create_file(
    project_id: str,
    file_data: FileCreate
):
    """Create a new file in a project.

    Args:
        project_id: Project ID
        file_data: File create data (path, content, encoding)

    Returns:
        Created file content

    Raises:
        HTTPException: If project not found, path invalid, or file cannot be created
    """
    try:
        service = get_project_service()
        content = await service.create_file(
            project_id,
            file_data.path,
            file_data.content,
            file_data.encoding
        )
        return content
    except ValueError as e:
        logger.error(f"Validation error creating file: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating file in {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/directories", response_model=FileNode, status_code=201)
async def create_directory(
    project_id: str,
    directory_data: DirectoryCreate
):
    """Create a new directory in a project.

    Args:
        project_id: Project ID
        directory_data: Directory create data (path)

    Returns:
        Created directory node

    Raises:
        HTTPException: If project not found, path invalid, or directory cannot be created
    """
    try:
        service = get_project_service()
        node = await service.create_directory(
            project_id,
            directory_data.path
        )
        return node
    except ValueError as e:
        logger.error(f"Validation error creating directory: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating directory in {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/files", response_model=FileContent)
async def write_file(
    project_id: str,
    file_data: FileWrite
):
    """Write content to a file in a project.

    Args:
        project_id: Project ID
        file_data: File write data (path, content, encoding)

    Returns:
        Updated file content

    Raises:
        HTTPException: If project not found, path invalid, or file cannot be written
    """
    try:
        service = get_project_service()
        content = await service.write_file(
            project_id,
            file_data.path,
            file_data.content,
            file_data.encoding,
            file_data.expected_hash,
        )
        return content
    except ProjectConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": e.code,
                "message": e.message,
                **e.extra,
            },
        )
    except ValueError as e:
        logger.error(f"Validation error writing file: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error writing file to {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/chat/apply-diff", response_model=ProjectChatApplyDiffResponse)
async def apply_chat_diff(
    project_id: str,
    payload: ConfirmPendingPatchArgs,
):
    """Apply one pending chat-generated diff after explicit user confirmation."""
    try:
        result = await confirm_pending_patch_apply(
            project_id=project_id,
            session_id=payload.session_id,
            pending_patch_id=payload.pending_patch_id,
            expected_hash=payload.expected_hash,
            project_service=get_project_service(),
        )
        return ProjectChatApplyDiffResponse.model_validate(result)
    except ProjectDocumentToolError as e:
        logger.warning(
            "Project chat apply diff rejected (project=%s, session=%s, patch=%s, code=%s, message=%s, extra=%s)",
            project_id,
            payload.session_id,
            payload.pending_patch_id,
            e.code,
            e.message,
            e.extra,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": e.code,
                "message": e.message,
                **e.extra,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error applying chat diff for project %s: %s", project_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/paths/rename", response_model=FileRenameResult)
async def rename_path(
    project_id: str,
    rename_data: FileRename
):
    """Rename or move a file or directory within a project.

    Args:
        project_id: Project ID
        rename_data: Rename request data (source_path, target_path)

    Returns:
        Rename result metadata

    Raises:
        HTTPException: If project not found, paths invalid, or rename fails
    """
    try:
        service = get_project_service()
        result = await service.rename_path(
            project_id,
            rename_data.source_path,
            rename_data.target_path
        )
        return result
    except ValueError as e:
        logger.error(f"Validation error renaming path: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error renaming path in {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/files", status_code=204)
async def delete_file(
    project_id: str,
    path: str = Query(..., description="Relative path to file from project root")
):
    """Delete a file from a project.

    Args:
        project_id: Project ID
        path: Relative path to file

    Raises:
        HTTPException: If project not found, path invalid, or file cannot be deleted
    """
    try:
        service = get_project_service()
        await service.delete_file(project_id, path)
    except ValueError as e:
        logger.error(f"Validation error deleting file: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting file in {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/directories", status_code=204)
async def delete_directory(
    project_id: str,
    path: str = Query(..., description="Relative path to directory from project root"),
    recursive: bool = Query(False, description="Delete contents recursively")
):
    """Delete a directory from a project.

    Args:
        project_id: Project ID
        path: Relative path to directory
        recursive: Whether to delete contents recursively

    Raises:
        HTTPException: If project not found, path invalid, or directory cannot be deleted
    """
    try:
        service = get_project_service()
        await service.delete_directory(project_id, path, recursive)
    except ValueError as e:
        logger.error(f"Validation error deleting directory: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting directory in {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/files/search")
async def search_project_files(
    project_id: str,
    query: str = Query(..., description="Search query"),
    current_file: Optional[str] = Query(None, description="Current file path for proximity"),
    limit: int = Query(20, ge=1, le=100, description="Max results")
):
    """
    Search project files with proximity-based scoring.

    Returns files ranked by:
    1. Proximity to current file (same dir > child > parent > sibling > project-wide)
    2. Fuzzy match quality (exact > partial > fuzzy)
    """
    try:
        service = get_project_service()
        results = await service.search_files_with_proximity(
            project_id=project_id,
            query=query,
            current_file_path=current_file,
            limit=limit
        )
        return results
    except Exception as e:
        logger.error(f"Error searching files in project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/text/search")
async def search_project_text(
    project_id: str,
    query: str = Query(..., description="Text or regex query"),
    case_sensitive: bool = Query(False, description="Enable case-sensitive matching"),
    use_regex: bool = Query(False, description="Treat query as regex pattern"),
    include_glob: Optional[str] = Query(None, description="Include files by glob pattern"),
    exclude_glob: Optional[str] = Query(None, description="Exclude files by glob pattern"),
    max_results: int = Query(30, ge=1, le=200, description="Max number of matches to return"),
    context_lines: int = Query(0, ge=0, le=3, description="Context lines before and after each match"),
    max_chars_per_line: int = Query(300, ge=80, le=1200, description="Max chars per returned line"),
):
    """Search text content across project files."""
    try:
        service = get_project_service()
        return await service.search_project_text(
            project_id=project_id,
            query=query,
            case_sensitive=case_sensitive,
            use_regex=use_regex,
            include_glob=include_glob,
            exclude_glob=exclude_glob,
            max_results=max_results,
            context_lines=context_lines,
            max_chars_per_line=max_chars_per_line,
        )
    except ValueError as e:
        logger.error(f"Validation error searching project text: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching project text in project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

