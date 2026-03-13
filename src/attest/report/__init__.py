# Reporting layer: emit canonical JSON first, then derived formats.

from attest.report.html import build_html, write_html

__all__ = ["build_html", "write_html"]
