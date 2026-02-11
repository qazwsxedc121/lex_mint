"""
Chat folder management service

Handles loading, saving, and managing chat folder configurations
"""
import yaml
import aiofiles
import uuid
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from ..paths import (
    config_defaults_dir,
    config_local_dir,
    ensure_local_file,
)


class Folder(BaseModel):
    """Folder model"""
    id: str
    name: str
    order: int


class FoldersConfig(BaseModel):
    """Folders configuration model"""
    folders: List[Folder]


class FolderService:
    """Chat folder management service"""

    def __init__(self, config_path: Path = None):
        """
        Initialize folder service

        Args:
            config_path: Configuration file path, defaults to config/local/chat_folders.yaml
        """
        self.defaults_path: Optional[Path] = None

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "chat_folders.yaml"
            self.config_path = config_local_dir() / "chat_folders.yaml"
        else:
            self.config_path = Path(config_path)

        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Ensure configuration file exists, create default if not"""
        if self.defaults_path is not None:
            default_config = self._get_default_config()
            initial_text = yaml.safe_dump(default_config, allow_unicode=True, sort_keys=False)
            ensure_local_file(
                local_path=self.config_path,
                defaults_path=self.defaults_path,
                legacy_paths=[],
                initial_text=initial_text,
            )
            return

        if not self.config_path.exists():
            default_config = self._get_default_config()
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {"folders": []}

    async def _load_config(self) -> FoldersConfig:
        """Load configuration from file"""
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content) or {}
            return FoldersConfig(**data)

    async def _save_config(self, config: FoldersConfig):
        """Save configuration to file"""
        async with aiofiles.open(self.config_path, 'w', encoding='utf-8') as f:
            await f.write(yaml.safe_dump(
                config.model_dump(),
                allow_unicode=True,
                sort_keys=False
            ))

    async def list_folders(self) -> List[Folder]:
        """
        List all folders ordered by order field

        Returns:
            List of folders sorted by order
        """
        config = await self._load_config()
        return sorted(config.folders, key=lambda f: f.order)

    async def get_folder(self, folder_id: str) -> Optional[Folder]:
        """
        Get a specific folder by ID

        Args:
            folder_id: Folder ID

        Returns:
            Folder if found, None otherwise
        """
        config = await self._load_config()
        for folder in config.folders:
            if folder.id == folder_id:
                return folder
        return None

    async def create_folder(self, name: str) -> Folder:
        """
        Create a new folder

        Args:
            name: Folder name

        Returns:
            Created folder
        """
        config = await self._load_config()

        # Generate unique ID
        folder_id = str(uuid.uuid4())

        # Calculate next order (append to end)
        next_order = len(config.folders)

        # Create folder
        new_folder = Folder(
            id=folder_id,
            name=name,
            order=next_order
        )

        config.folders.append(new_folder)
        await self._save_config(config)

        return new_folder

    async def update_folder(self, folder_id: str, name: str) -> Folder:
        """
        Update folder name

        Args:
            folder_id: Folder ID
            name: New name

        Returns:
            Updated folder

        Raises:
            ValueError: If folder not found
        """
        config = await self._load_config()

        # Find folder
        folder_index = None
        for i, folder in enumerate(config.folders):
            if folder.id == folder_id:
                folder_index = i
                break

        if folder_index is None:
            raise ValueError(f"Folder '{folder_id}' not found")

        # Update folder
        config.folders[folder_index].name = name
        await self._save_config(config)

        return config.folders[folder_index]

    async def delete_folder(self, folder_id: str):
        """
        Delete a folder

        Args:
            folder_id: Folder ID

        Raises:
            ValueError: If folder not found

        Note:
            Sessions in this folder will have their folder_id set to null
            by the caller (handled in router/storage layer)
        """
        config = await self._load_config()

        # Find and remove folder
        original_count = len(config.folders)
        config.folders = [f for f in config.folders if f.id != folder_id]

        if len(config.folders) == original_count:
            raise ValueError(f"Folder '{folder_id}' not found")

        # Reorder remaining folders
        for i, folder in enumerate(sorted(config.folders, key=lambda f: f.order)):
            folder.order = i

        await self._save_config(config)
