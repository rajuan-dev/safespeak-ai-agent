import hashlib
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata"
SHA256 = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "tools" / "tessdata" / "eng.traineddata"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen(URL, timeout=60).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        raise RuntimeError(f"Unexpected tessdata SHA-256: {digest}")
    target.write_bytes(data)
    print(f"Installed verified English tessdata at {target}")


if __name__ == "__main__":
    main()

