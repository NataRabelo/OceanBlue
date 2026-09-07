import hashlib
import json
from pathlib import Path


def main():
    files = []
    for directory in ("app", "tests", "scripts", "migrations"):
        files.extend(path for path in Path(directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    files.extend(path for pattern in ("requirements*", "Dockerfile*", "compose.test.yml", "pytest.ini", ".coveragerc", "package*.json")
                 for path in Path(".").glob(pattern) if path.is_file())
    print(json.dumps({path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}, indent=2))


if __name__ == "__main__":
    main()
