"""Launch the RouteGuard dashboard: ``python dashboard/app.py [config.yaml]``.

Equivalent to ``routeguard demo --config <config>``; requires ``pip install -e '.[dashboard]'``.
"""

import sys

from routeguard.dashboard import launch

if __name__ == "__main__":
    launch(sys.argv[1] if len(sys.argv) > 1 else "configs/demo.yaml")
