"""Allow `python -m cloudflare_memory` (slim MCP) and `python -m cloudflare_memory serve --full`."""

from __future__ import annotations

import sys

from cloudflare_memory.main import main

if len(sys.argv) == 1:
    sys.argv.append("serve")
main()
