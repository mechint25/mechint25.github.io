#!/usr/bin/env python3
"""Generate and decode-check final QR assets for a verified public HTTPS URL.

Inputs: one canonical HTTPS URL and an optional output directory.
Outputs: QR SVG, high-resolution PNG, and a labelled poster SVG. Existing files
are overwritten. Placeholder, local, and non-HTTPS destinations are rejected.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from urllib.parse import urlparse


def validate_url(url: str) -> str:
    """Return a canonical-looking HTTPS URL or raise for unsafe placeholders."""
    parsed = urlparse(url)
    blocked = {"example.com", "localhost", "127.0.0.1", "0.0.0.0"}
    if parsed.scheme != "https" or not parsed.netloc or parsed.hostname in blocked:
        raise ValueError("Use the exact public HTTPS URL; placeholders and local URLs are refused.")
    return url


def main() -> None:
    """Write QR assets and verify that the PNG decodes to the requested URL."""
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output", type=Path, default=Path("assets/qr"))
    args = parser.parse_args()
    url = validate_url(args.url)
    try:
        import cv2
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError as exc:
        raise SystemExit("Install QR tooling first: python -m pip install 'qrcode[pil]' opencv-python") from exc

    args.output.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=24, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    png_path = args.output / "experiment-qr.png"
    svg_path = args.output / "experiment-qr.svg"
    qr.make_image(fill_color="black", back_color="white").save(png_path)
    qr.make_image(image_factory=SvgPathImage).save(svg_path)

    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(png_path)))
    if decoded != url:
        raise RuntimeError(f"QR decode verification failed: {decoded!r}")

    qr_markup = svg_path.read_text(encoding="utf-8").split("?>", 1)[-1]
    poster = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="740" viewBox="0 0 1400 740">
  <rect width="1400" height="740" rx="32" fill="#f4f0e8"/>
  <text x="650" y="238" font-family="Georgia,serif" font-size="72" fill="#17212b">Explore the experiment</text>
  <text x="650" y="322" font-family="Arial,sans-serif" font-size="30" fill="#65717b">Multiple Recovery Paths in a Lesioned Transformer</text>
  <text x="650" y="500" font-family="Arial,sans-serif" font-size="26" fill="#17212b">{html.escape(url)}</text>
  <g transform="translate(70 70) scale(.52)">{qr_markup}</g>
</svg>'''
    (args.output / "explore-the-experiment.svg").write_text(poster, encoding="utf-8")
    print(f"Verified payload: {decoded}")


if __name__ == "__main__":
    main()
