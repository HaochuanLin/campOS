# Streamlit Community Cloud entry point for campOS.
# The application implementation lives in src/campos/app.py.
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# Streamlit reruns this entry point after each widget interaction. Execute the
# UI file afresh on every rerun; a normal import is cached by Python and can
# leave the page empty after the first interaction.
import runpy  # noqa: E402

runpy.run_path(str(SOURCE_ROOT / "campos" / "app.py"), run_name="__main__")
