"""Convenience launcher for the campOS simulation prototype.

The simulation implementation lives in src/campos/campos_sim.py.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).parent / "src" / "campos" / "campos_sim.py"), run_name="__main__")
