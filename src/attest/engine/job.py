"""Job mode execution engine (REQ-3.3): batch evaluation across targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from attest.engine.evaluator import evaluate_controls
from attest.policy.loader import load_profile_bundle
from attest.report.canonical import build_report
from attest.resources.builtin import build_builtin_registry


@dataclass
class JobTarget:
    """A target system for evaluation in job mode."""

    host: str
    description: str = ""
    ssh_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Results from evaluating a single target in a job."""

    target_host: str
    report: dict[str, Any]
    exit_code: int


class JobExecutor:
    """Execute compliance jobs against multiple targets."""

    def __init__(self):
        self.targets: list[JobTarget] = []
        self.results: list[JobResult] = []
        self.registry = build_builtin_registry()

    def add_target(self, host: str, description: str = "", ssh_config: dict[str, Any] | None = None) -> None:
        """Add a target to the job."""
        target = JobTarget(
            host=host,
            description=description,
            ssh_config=ssh_config or {},
        )
        self.targets.append(target)

    def execute(self, profile_dir: Path | str) -> list[JobResult]:
        """Execute the job against all targets."""
        self.results = []
        profile_path = Path(profile_dir)

        try:
            profile, controls = load_profile_bundle(profile_path)
        except Exception as exc:
            # If profile loading fails, return error results for all targets
            for target in self.targets:
                self.results.append(
                    JobResult(
                        target_host=target.host,
                        report={
                            "error": str(exc),
                            "profile": None,
                            "controls": [],
                            "results": [],
                        },
                        exit_code=4,
                    )
                )
            return self.results

        # Evaluate each target
        for target in self.targets:
            evaluated_results, cache_stats = evaluate_controls(
                host=target.host,
                controls=controls,
                registry=self.registry,
            )

            report = build_report(profile, controls, evaluated_results, host=target.host)
            report["resource_cache"] = cache_stats

            # Determine exit code
            counts = report["summary"]["counts"]
            exit_code = 0
            if counts.get("FAIL", 0):
                exit_code = 2
            elif counts.get("ERROR", 0):
                exit_code = 3

            self.results.append(
                JobResult(
                    target_host=target.host,
                    report=report,
                    exit_code=exit_code,
                )
            )

        return self.results

    def aggregate_summary(self) -> dict[str, Any]:
        """Return an aggregated summary of all target runs."""
        if not self.results:
            return {
                "total_targets": 0,
                "targets_passed": 0,
                "targets_failed": 0,
                "targets_with_errors": 0,
            }

        total = len(self.results)
        passed = sum(1 for r in self.results if r.exit_code == 0)
        failed = sum(1 for r in self.results if r.exit_code == 2)
        errors = sum(1 for r in self.results if r.exit_code == 3)

        return {
            "total_targets": total,
            "targets_passed": passed,
            "targets_failed": failed,
            "targets_with_errors": errors,
            "success_rate": round(passed / total * 100, 1) if total > 0 else 0,
        }
