import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class StorageService(ABC):
    @abstractmethod
    def save(self, file: FileStorage, subfolder: str) -> str:
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_folder: str):
        # Resolve to absolute: a relative UPLOAD_FOLDER would otherwise store
        # relative paths in the DB, and Werkzeug's send_file() resolves those
        # against the Flask app's root_path (backend/app/), not the cwd the
        # file was actually saved under — silently serving from the wrong place.
        self.base_folder = Path(base_folder).resolve()
        self.base_folder.mkdir(parents=True, exist_ok=True)

    def save(self, file: FileStorage, subfolder: str) -> str:
        folder = self.base_folder / subfolder
        folder.mkdir(parents=True, exist_ok=True)

        original = secure_filename(file.filename or "upload")
        unique_name = f"{uuid.uuid4().hex}_{original}"
        dest = folder / unique_name
        file.save(dest)
        return str(dest)


def validate_extension(filename: str, allowed: set[str]) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in allowed


def validate_file_size(file: FileStorage, max_mb: int) -> bool:
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    return size <= max_mb * 1024 * 1024
