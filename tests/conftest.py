"""
conftest.py — shared pytest fixtures and path setup.
"""
import sys
from pathlib import Path

# Ensure the project root is on the path so all modules are importable.
sys.path.insert(0, str(Path(__file__).parent.parent))
