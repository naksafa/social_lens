import re
import unicodedata
from pathlib import PurePath

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """Return a filesystem-safe version of a user-supplied filename.

    Strips directory components (both / and \\ separators), normalises unicode to
    ASCII, replaces unsafe characters and prevents hidden/empty names.
    """
    name = PurePath(filename.replace("\\", "/")).name
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = _UNSAFE_CHARS.sub("_", name).strip("._")
    if not name:
        name = "upload"
    if len(name) > max_length:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 10:
            name = stem[: max_length - len(ext) - 1] + "." + ext
        else:
            name = name[:max_length]
    return name


def file_extension(filename: str) -> str:
    return PurePath(filename).suffix.lower()
