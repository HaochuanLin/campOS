# Streamlit Community Cloud entry point for campOS.
# The application implementation lives in src/campos/app.py.
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# Importing this module runs the Streamlit UI script.
import campos.app  # noqa: E402,F401
