"""Application configuration (member 1).

Paths are resolved from the project root rather than the current working
directory, so the app behaves the same no matter where it is launched from.
"""

import os
from pathlib import Path

# config.py -> backend/app/config.py -> project root = parents[2]
BASE_DIR = Path(__file__).resolve().parents[2]


class Config:
    """Delivery configuration. Tests override values via ``create_app(test_config=...)``."""

    # 数据文件：项目根 data/records.json，不依赖启动目录（README 8.1）。
    # 环境变量仅用于开发/调试覆盖，测试一律通过 test_config 传入临时路径。
    DATA_FILE = os.environ.get('LEDGER_DATA_FILE', str(BASE_DIR / 'data' / 'records.json'))

    # 静态资源目录：发布包指向 web/；开发构建检查可指向 frontend/dist/。
    WEB_DIST_DIR = os.environ.get('LEDGER_WEB_DIST_DIR', str(BASE_DIR / 'web'))

    # 交付版：仅监听本机回环、关闭调试与自动重载、单进程运行（README 8.1）。
    HOST = '127.0.0.1'
    PORT = 5000
    DEBUG = False
