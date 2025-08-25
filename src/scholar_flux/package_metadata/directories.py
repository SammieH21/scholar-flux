from pathlib import Path
from typing import Optional, Literal


PARENT_DIRECTORY_CANDIDATES = [
    lambda: Path(__file__).parent.parent,
    lambda: Path.home() / '.scholar_flux'
]

def get_default_writable_directory(directory_type: Literal['package_cache', 'logs'],
                           subdirectory: Optional[str | Path] = None) -> Path:
    """
    This is a helper function that, in case a default directory is not specified 
    for caching and logging in package-specific functionality, it can serve as a
    fallbaack, identifying writeable package directories where required.

    Args:
        directory_type (Literal['package_cache','logs'])
    Returns:
        Path: The path of a default writeable directory if found

    Raises:
        RuntimeError if a writeable directory cannot be identified
    """

    if not directory_type in ['package_cache', 'logs']:
        raise ValueError("Received an incorrect directory_type when identifying writable directories.")
    
    for candidate_func in PARENT_DIRECTORY_CANDIDATES:
        try:
            base_path = candidate_func()
            full_path = base_path / (subdirectory or directory_type)
            
            # Test writeability
            full_path.mkdir(parents=True, exist_ok=True)
            return full_path
            
        except (PermissionError, OSError):
            continue
    
    raise RuntimeError(f"Could not locate a writable {directory_type} directory for scholar_flux")
