"""
Manual Test Harness for Agent Orchestration.

Allows manual triggering of the Foundry agent pipeline without deploying Azure infrastructure.
Use this to validate the end-to-end orchestration flow and agent interactions.
"""

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.pipeline import AgentPipeline
from foundry_agents.time_utils import utc_iso


class ManualTestHarness:
    """Manual trigger for testing the agent pipeline."""

    def __init__(self):
        self.pipeline = AgentPipeline()
        self.execution_log = []

    def create_mock_intake_trigger(self, *, needs_human_review: bool = False) -> dict:
        """Create a mock W-2 intake trigger event."""
        trigger = {
            "correlationId": f"manual-test-{uuid4()}",
            "tenantId": "tenant-001",
            "taxpayerId": "taxpayer-12345",
            "documentName": "W2_2024_sample.pdf",
            "blobUri": "https://taxaistg.blob.core.windows.net/raw-w2/tenant-001/taxpayer-12345/2024/20240101T000000Z_W2_2024_sample.pdf",
            "taxYear": 2024,
        }
        if needs_human_review:
            trigger["mockExtractionOverrides"] = {"employerEIN": None}
        return trigger

    def log_step(self, stage: str, agent: str, result: dict):
        """Log execution step."""
        log_entry = {
            "timestamp": utc_iso(),
            "stage": stage,
            "agent": agent,
            "result": result,
        }
        self.execution_log.append(log_entry)
        print(f"\n[{stage.upper()}] {agent} executed:")
        print(json.dumps(result, indent=2))

    def run_full_pipeline(self, intake_trigger: dict = None) -> dict:
        """Execute the full agent pipeline."""
        if intake_trigger is None:
            intake_trigger = self.create_mock_intake_trigger()

        print("\n" + "=" * 80)
        print("FOUNDRY AGENT ORCHESTRATION TEST - FULL PIPELINE")
        print("=" * 80)

        print("\n[INIT] Starting supervisor orchestrator...")
        final_result = self.pipeline.run(intake_trigger)
        print(f"Pipeline ID: {final_result['pipelineId']}")
        self.execution_log = self.pipeline.execution_log
        for entry in self.execution_log:
            print(f"\n[{entry['stage'].upper()}] {entry['agent']} executed:")
            print(json.dumps(entry["result"], indent=2))

        print("\n" + "=" * 80)
        print("PIPELINE EXECUTION COMPLETE")
        print("=" * 80)

        return final_result

    def run_pipeline_with_human_review(self, intake_trigger: dict = None) -> dict:
        """Execute pipeline with human review step."""
        if intake_trigger is None:
            intake_trigger = self.create_mock_intake_trigger(needs_human_review=True)

        print("\n" + "=" * 80)
        print("FOUNDRY AGENT ORCHESTRATION TEST - WITH HUMAN REVIEW")
        print("=" * 80)

        final_result = self.pipeline.run(intake_trigger)
        print(f"Pipeline ID: {final_result['pipelineId']}")
        self.execution_log = self.pipeline.execution_log
        for entry in self.execution_log:
            print(f"\n[{entry['stage'].upper()}] {entry['agent']} executed:")
            print(json.dumps(entry["result"], indent=2))

        print("\n" + "=" * 80)
        print("PIPELINE EXECUTION COMPLETE")
        print("=" * 80)

        return final_result

    def print_execution_summary(self):
        """Print summary of execution log."""
        print("\n" + "=" * 80)
        print("EXECUTION SUMMARY")
        print("=" * 80)
        for i, entry in enumerate(self.execution_log, 1):
            print(f"{i}. [{entry['stage'].upper()}] {entry['agent']}")
        print(f"\nTotal steps executed: {len(self.execution_log)}")


def main() -> None:
    """Run one or both local orchestration scenarios."""
    parser = argparse.ArgumentParser(description="Run local Foundry agent orchestration scenarios.")
    parser.add_argument(
        "--scenario",
        choices=["full", "human-review", "all"],
        default="all",
        help="Scenario to execute. Defaults to all.",
    )
    args = parser.parse_args()

    if args.scenario in ("full", "all"):
        harness = ManualTestHarness()
        print("\n\n### Test 1: Full Pipeline ###")
        harness.run_full_pipeline()
        harness.print_execution_summary()

    if args.scenario in ("human-review", "all"):
        harness = ManualTestHarness()
        print("\n\n### Test 2: Pipeline with Human Review ###")
        harness.run_pipeline_with_human_review()
        harness.print_execution_summary()


if __name__ == "__main__":
    main()
