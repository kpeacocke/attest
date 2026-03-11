"""Tests for job mode execution engine (REQ-3.3)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from attest.engine.job import JobExecutor, JobTarget


class TestJobTarget:
    def test_create_job_target(self) -> None:
        target = JobTarget(host="prod-01", description="Production server")
        assert target.host == "prod-01"
        assert target.description == "Production server"


class TestJobExecutor:
    def test_create_job_executor(self) -> None:
        executor = JobExecutor()
        assert len(executor.targets) == 0
        assert len(executor.results) == 0

    def test_add_targets(self) -> None:
        executor = JobExecutor()
        executor.add_target("host1")
        executor.add_target("host2", description="Test host")
        assert len(executor.targets) == 2
        assert executor.targets[0].host == "host1"
        assert executor.targets[1].description == "Test host"

    def test_execute_job_with_passing_control(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "test-profile"
        profile_dir.mkdir()
        (profile_dir / "profile.yml").write_text(
            textwrap.dedent(
                """
                name: test-profile
                title: Test Profile
                version: 1.0.0
                """
            ),
            encoding="utf-8",
        )

        controls_dir = profile_dir / "controls"
        controls_dir.mkdir()
        (controls_dir / "os.yml").write_text(
            textwrap.dedent(
                """
                id: OS-001
                title: OS facts available
                tests:
                  - name: system fact exists
                    resource: os_facts
                    operator: exists
                    params:
                      field: system
                """
            ),
            encoding="utf-8",
        )

        executor = JobExecutor()
        executor.add_target("prod-01", description="Production")
        executor.add_target("dev-01", description="Development")

        results = executor.execute(profile_dir)
        assert len(results) == 2
        assert results[0].target_host == "prod-01"
        assert results[1].target_host == "dev-01"
        assert results[0].exit_code == 0  # Should pass
        assert results[1].exit_code == 0  # Should pass

    def test_aggregate_summary(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "test-profile"
        profile_dir.mkdir()
        (profile_dir / "profile.yml").write_text(
            textwrap.dedent(
                """
                name: test-profile
                title: Test Profile
                version: 1.0.0
                """
            ),
            encoding="utf-8",
        )

        controls_dir = profile_dir / "controls"
        controls_dir.mkdir()
        (controls_dir / "os.yml").write_text(
            textwrap.dedent(
                """
                id: OS-001
                title: OS facts available
                tests:
                  - name: system fact exists
                    resource: os_facts
                    operator: exists
                    params:
                      field: system
                """
            ),
            encoding="utf-8",
        )

        executor = JobExecutor()
        executor.add_target("host1")
        executor.add_target("host2")
        executor.add_target("host3")

        executor.execute(profile_dir)
        summary = executor.aggregate_summary()

        assert summary["total_targets"] == 3
        assert summary["targets_passed"] >= 0
        assert "success_rate" in summary

    def test_execute_with_missing_profile(self, tmp_path: Path) -> None:
        executor = JobExecutor()
        executor.add_target("host1")

        results = executor.execute(tmp_path / "nonexistent")
        assert len(results) == 1
        assert results[0].exit_code == 4
        assert "error" in results[0].report
