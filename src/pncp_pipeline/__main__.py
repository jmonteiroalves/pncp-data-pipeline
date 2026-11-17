"""Allow ``python -m pncp_pipeline``."""

import sys

from pncp_pipeline.cli import main

if __name__ == "__main__":
    sys.exit(main())
