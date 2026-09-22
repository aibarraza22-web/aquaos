import os
import warnings
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parents[1]
SCENARIOS = ROOT / "scenarios"

warnings.filterwarnings("ignore", category=UserWarning)
os.environ.setdefault("AQUAOS_OFFLINE", "1")  # tests never touch the network unless marked


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES
