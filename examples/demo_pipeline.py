"""End-to-end demo of the Spectra pipeline."""

import asyncio

from spectra.config import get_config
from spectra.orchestrator import PipelineOrchestrator


async def demo():
    """Run a demo of the full Scout → Analyst → Executor pipeline."""
    config = get_config()
    orchestrator = PipelineOrchestrator(config)

    print("=" * 60)
    print("  SPECTRA — Multi-Agent Market Intelligence Demo")
    print("=" * 60)
    print()

    print("[1/3] Running Scout agent — discovering signals...")
    briefs = await orchestrator.run_single_pass()

    print(f"\n[Complete] Pipeline produced {len(briefs)} intelligence briefs")
    for brief in briefs:
        print(f"\n{'─' * 60}")
        print(brief.summary)
        print(f"{'─' * 60}")

    if not briefs:
        print("\nNo briefs generated (no qualifying signals found this cycle)")
        print("This is normal — the pipeline continuously scans and only")
        print("produces briefs when meaningful signals are detected.")


if __name__ == "__main__":
    asyncio.run(demo())