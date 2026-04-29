"""__main__ entry point for Spectra."""

import asyncio
import sys

from spectra.orchestrator import main

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    asyncio.run(main(mode))