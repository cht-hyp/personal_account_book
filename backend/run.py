"""Delivery entry point (member 1).

Run with ``scripts\\start.bat`` or ``python backend\\run.py``. The project root
is added to ``sys.path`` so the ``backend`` package imports the same way it does
in the test suite, regardless of the current working directory.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import create_app  # noqa: E402
from backend.app.config import Config  # noqa: E402

app = create_app()

if __name__ == '__main__':
    # 交付版：仅监听本机回环、关闭 debug 与自动重载、单进程（README 8.1）。
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, use_reloader=False)
