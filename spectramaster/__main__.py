"""`python -m spectramaster ...` -> command line (no arguments -> GUI)."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
