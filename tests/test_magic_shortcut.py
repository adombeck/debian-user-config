"""Repository routing for the desktop clipboard shortcut."""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def load_shortcut():
    path = Path(__file__).resolve().parents[1] / "scripts/magic-shortcut"
    loader = importlib.machinery.SourceFileLoader("magic_shortcut", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    gi = types.ModuleType("gi")
    gi.require_version = Mock()
    repository = types.ModuleType("gi.repository")
    repository.GLib = Mock()
    repository.Notify = Mock()
    gi.repository = repository
    with patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}):
        with patch.dict(os.environ):
            loader.exec_module(module)
    return module


shortcut = load_shortcut()


class RepositoryRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.projects = self.home / "projects"
        self.projects.mkdir()
        home = patch.object(shortcut.Path, "home", return_value=self.home)
        home.start()
        self.addCleanup(home.stop)

    def checkout(self, name, remote):
        path = self.projects / name
        path.mkdir()
        subprocess.run(["git", "init", "--quiet", str(path)], check=True)
        subprocess.run(
            ["git", "-C", str(path), "remote", "add", "origin", remote], check=True,
        )
        return path

    def active_project(self, path):
        cache = self.home / ".cache"
        cache.mkdir(exist_ok=True)
        (cache / "current-intellij-project").write_text(str(path))

    def test_url_selects_its_checkout_not_the_active_project(self):
        authd = self.checkout("authd", "git@github.com:canonical/authd.git")
        adsys = self.checkout("adsys", "https://github.com/ubuntu/adsys.git")
        self.active_project(authd)
        self.assertEqual(
            shortcut.github_repository_dir("https://github.com/ubuntu/adsys/issues/42"),
            adsys,
        )

    def test_finds_renamed_checkout_by_remote_instead_of_directory_name(self):
        self.checkout("adsys", "https://github.com/someone/another-project.git")
        checkout = self.checkout("adsys-dev", "ssh://git@github.com/ubuntu/adsys.git")
        self.assertEqual(
            shortcut.github_repository_dir("https://github.com/ubuntu/adsys/issues/42"),
            checkout,
        )

    def test_active_linked_worktree_is_preferred_for_matching_repository(self):
        main = self.checkout("adsys", "git@github.com:ubuntu/adsys.git")
        subprocess.run(
            ["git", "-C", str(main), "-c", "user.name=Test",
             "-c", "user.email=test@example.invalid", "commit", "--quiet",
             "--allow-empty", "-m", "Initial commit"],
            check=True,
        )
        worktree = self.projects / "adsys-topic"
        subprocess.run(
            ["git", "-C", str(main), "worktree", "add", "--quiet", "-b", "topic",
             str(worktree)], check=True,
        )
        self.active_project(worktree)
        self.assertEqual(
            shortcut.github_repository_dir("https://github.com/ubuntu/adsys/issues/42"),
            worktree,
        )

    def test_missing_checkout_does_not_fall_back_to_authd(self):
        self.active_project(self.checkout("authd", "git@github.com:canonical/authd.git"))
        with self.assertRaisesRegex(ValueError, "No local checkout found for ubuntu/adsys"):
            shortcut.github_repository_dir("https://github.com/ubuntu/adsys/issues/42")

    def test_shared_workflow_preserves_desktop_launch_options(self):
        adsys = self.checkout("adsys", "git@github.com:ubuntu/adsys.git")
        url = "https://github.com/ubuntu/adsys/actions/runs/123/job/456"
        with patch.object(shortcut, "desktop_tool", return_value="/tools/de-debug-ci-job"):
            with patch.object(shortcut, "run_command_with_error_notification", return_value=0) as run:
                status = shortcut.run_github_workflow(
                    "de-debug-ci-job", url, "Debugging CI job", "Failed to debug CI job",
                )
        self.assertEqual(status, 0)
        self.assertEqual(run.call_args.args[0], [
            "/tools/de-debug-ci-job", "--repo-dir", str(adsys),
            "--terminal", "guake", "--intellij", url,
        ])

    def test_tool_resolution_uses_configured_checkout_then_path(self):
        tool = self.home / "shared/bin/de-fix-issue"
        tool.parent.mkdir(parents=True)
        tool.touch(mode=0o755)
        with patch.dict(os.environ, {"DESKTOP_ENGINEERING_DIR": str(self.home / "shared")}):
            with patch.object(shortcut.shutil, "which", return_value="/path/de-fix-issue"):
                self.assertEqual(shortcut.desktop_tool("de-fix-issue"), str(tool))
                tool.unlink()
                self.assertEqual(shortcut.desktop_tool("de-fix-issue"), "/path/de-fix-issue")


class ClipboardDispatchTests(unittest.TestCase):
    def dispatch(self, url, status=0):
        with (
            patch.object(shortcut.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["wl-paste"], 0, url,
            )),
            patch.object(shortcut, "run_github_workflow", return_value=status) as workflow,
            patch.object(shortcut, "start_background_jira_claim", return_value=(123, "/log")) as claim,
            patch.object(shortcut, "notify") as notify,
        ):
            shortcut.main()
        return workflow, claim, notify

    def test_adsys_urls_use_shared_workflows_without_jira_claim(self):
        for suffix, tool in (
            ("issues/42", "de-fix-issue"),
            ("actions/runs/123/job/456?pr=42", "de-debug-ci-job"),
            ("pull/42#discussion_r123", "de-address-review-comment"),
            ("pull/42#issuecomment-123", "de-address-review-comment"),
            ("pull/42#pullrequestreview-123", "de-address-review-comment"),
        ):
            with self.subTest(suffix=suffix):
                url = f"https://github.com/ubuntu/adsys/{suffix}"
                workflow, claim, _ = self.dispatch(url)
                self.assertEqual(workflow.call_args.args[:2], (tool, url))
                claim.assert_not_called()

    def test_canonical_jira_claim_still_runs_only_after_success(self):
        url = "https://github.com/canonical/authd/issues/42"
        with patch.object(shortcut.Path, "exists", return_value=True):
            for status in (0, 1):
                with self.subTest(status=status):
                    _, claim, _ = self.dispatch(url, status)
                    self.assertEqual(claim.called, status == 0)

    def test_issues_work_without_the_optional_jira_script(self):
        with patch.object(shortcut.Path, "exists", return_value=False):
            workflow, claim, _ = self.dispatch("https://github.com/canonical/authd/issues/42")
        workflow.assert_called_once()
        claim.assert_not_called()

    def test_missing_shared_tool_notifies_instead_of_launching(self):
        with (
            patch.object(shortcut, "desktop_tool", side_effect=FileNotFoundError("missing tool")),
            patch.object(shortcut, "notify") as notify,
            patch.object(shortcut, "run_command_with_error_notification") as run,
        ):
            status = shortcut.run_github_workflow(
                "de-fix-issue", "https://github.com/ubuntu/adsys/issues/42",
                "Preparing worktree", "Failed to prepare worktree",
            )
        self.assertEqual(status, 1)
        notify.assert_called_once_with("Failed to prepare worktree", "missing tool")
        run.assert_not_called()


class BranchWorktreeTests(unittest.TestCase):
    def test_active_repository_and_reported_worktree_path_are_used(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for alternate in (False, True):
                with (
                    self.subTest(alternate=alternate),
                    patch.object(shortcut, "current_project", return_value=path),
                    patch.object(shortcut, "desktop_tool", return_value="/tools/de-worktree"),
                    patch.object(shortcut, "notify"),
                    patch.object(shortcut, "ALT", alternate),
                    patch.object(shortcut.subprocess, "Popen") as popen,
                    patch.object(shortcut.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 0, "topic\n"),
                        subprocess.CompletedProcess([], 0, str(path) + "\n", ""),
                        subprocess.CompletedProcess([], 0),
                        subprocess.CompletedProcess([], 0),
                    ]) as run,
                ):
                    self.assertTrue(shortcut.open_branch_worktree("topic"))
                    self.assertEqual(run.call_args_list[1].args[0], [
                        "/tools/de-worktree", "-C", str(path), "--intellij", "topic",
                    ])
                    if alternate:
                        popen.assert_called_once_with(["idea", str(path)])
                    else:
                        self.assertEqual(run.call_args_list[2].args[0][-1], str(path))

    def test_remote_fetch_failure_does_not_create_worktree(self):
        with (
            patch.object(shortcut, "current_project", return_value=Path("/repo")),
            patch.object(shortcut.Path, "exists", return_value=True),
            patch.object(shortcut, "desktop_tool", return_value="/tools/de-worktree"),
            patch.object(shortcut.subprocess, "run", side_effect=[
                subprocess.CompletedProcess([], 0, ""),
                subprocess.CompletedProcess([], 0, "origin\n"),
            ]) as run,
            patch.object(shortcut, "run_command_with_error_notification", return_value=1) as fetch,
        ):
            self.assertTrue(shortcut.open_branch_worktree("origin:topic"))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(fetch.call_args.args[0], [
            "git", "--no-pager", "fetch", "--no-recurse-submodules", "origin", "topic",
        ])


if __name__ == "__main__":
    unittest.main()
