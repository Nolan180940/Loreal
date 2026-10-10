"""让 ``python -m jev_guard`` 可用。"""

from __future__ import annotations

from .cli import main

raise SystemExit(main())