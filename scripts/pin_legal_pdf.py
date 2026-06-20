import argparse
import hashlib
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and hash an official legal PDF.")
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    request = urllib.request.Request(
        args.url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 SafeSpeak-Legal-Corpus/1.0"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
        content_type = response.headers.get_content_type()
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"URL did not return a PDF (content type: {content_type})")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"path={args.output}")
    print(f"bytes={len(data)}")
    print(f"sha256={hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
