import os
import sys
import tempfile
from pathlib import Path

# 让测试可以直接 import backend 下的模块（config / schemas / storyboard ...）。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 必须在 import config 之前设置：dotenv 不会覆盖已存在的环境变量，
# 所以这里可以把测试指向独立的临时数据库，绝不碰真实 recut.db。
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="recut-test-db-"))
os.environ.setdefault("APP_DB_URL", f"sqlite:///{_TEST_DB_DIR / 'test.db'}")
os.environ.setdefault("APP_MAX_LOGIN_ATTEMPTS", "3")
os.environ.setdefault("APP_LOCKOUT_MINUTES", "15")
os.environ.setdefault("APP_PASSWORD_MIN_LENGTH", "10")
