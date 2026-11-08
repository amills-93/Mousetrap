import os
import sys
from pathlib import Path

os.environ["ML_INTERNAL_KEY"] = "test-key"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
