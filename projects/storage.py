import os
import tempfile
from pathlib import Path


def store_bytes_atomically(field, filename, content, *, replace=False):
    name = field.name if replace else field.field.generate_filename(field.instance, filename)
    destination = Path(field.storage.path(name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        raise FileExistsError(destination)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".write-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    field.name = name
