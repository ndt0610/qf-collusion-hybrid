"""Download exact historical snapshot files, with SHA-256 verification."""
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT/"data/manifests/sources.json").read_text(encoding="utf-8"))
DEST = ROOT/"data/raw"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for filename, meta in MANIFEST["files"].items():
        target = DEST/filename
        if target.exists():
            digest = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
            if digest == meta["sha256"]:
                print(f"verified existing {filename}: {digest}")
                continue
            raise ValueError(f"Existing {filename} has wrong SHA-256; inspect it before replacing")
        temp = DEST/(filename+".partial")
        try:
            request = urllib.request.Request(meta["url"], headers={"User-Agent": "qf-collusion-hybrid/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as out:
                shutil.copyfileobj(response, out)
            digest = hashlib.file_digest(temp.open("rb"), "sha256").hexdigest()
            if digest != meta["sha256"]:
                raise ValueError(f"Downloaded {filename} has SHA-256 {digest}, expected {meta['sha256']}")
            temp.replace(target)
            print(f"downloaded and verified {filename}: {digest}")
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
