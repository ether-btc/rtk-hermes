"""Contract tests for the standalone RTK-Hermes adapter."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import rtk_hermes


@pytest.fixture(autouse=True)
def reset_state():
    rtk_hermes._rtk_available = None
    rtk_hermes._rtk_missing_warned = False
    rtk_hermes.reset_metrics()
    yield
    rtk_hermes._rtk_available = None


class TestRewriteBoundary:
    def test_rewrite_mutates_terminal_command_on_success(self):
        args = {"command": "git status", "timeout": 30}
        result = subprocess.CompletedProcess([], 0, "rtk git status\n", "")
        with patch("shutil.which", return_value="/usr/bin/rtk"), patch(
            "subprocess.run", return_value=result
        ):
            rtk_hermes._pre_tool_call("terminal", args)
        assert args == {"command": "rtk git status", "timeout": 30}

    @pytest.mark.parametrize("returncode", [1, 2, 99])
    def test_rewrite_non_success_passes_through(self, returncode):
        args = {"command": "git status"}
        result = subprocess.CompletedProcess([], returncode, "", "failed")
        with patch("shutil.which", return_value="/usr/bin/rtk"), patch(
            "subprocess.run", return_value=result
        ):
            rtk_hermes._pre_tool_call("terminal", args)
        assert args["command"] == "git status"

    def test_rewrite_timeout_fails_open(self):
        args = {"command": "git status"}
        with patch("shutil.which", return_value="/usr/bin/rtk"), patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("rtk", 2)
        ):
            rtk_hermes._pre_tool_call("terminal", args)
        assert args["command"] == "git status"

    def test_pre_tool_call_ignores_other_tools(self):
        args = {"command": "git status"}
        with patch("subprocess.run") as run:
            rtk_hermes._pre_tool_call("web_search", args)
        run.assert_not_called()
        assert args["command"] == "git status"


class TestSerializedResultBoundary:
    @staticmethod
    def fake_compressor(output):
        return "compressed: " + output[:20]

    def test_preserves_envelope_and_unknown_metadata(self):
        payload = {
            "output": "repeated diagnostic line\n" * 30,
            "code": 7,
            "exit_code": 7,
            "returncode": 7,
            "error": "command failed",
            "opaque": {"owner": "test", "n": 42},
        }
        with patch.object(rtk_hermes, "_RUST_AVAILABLE", True), patch.object(
            rtk_hermes, "_rust_compress", self.fake_compressor
        ):
            transformed = rtk_hermes._pre_tool_call_result("terminal", json.dumps(payload))
        assert isinstance(transformed, str)
        result = json.loads(transformed)
        assert result["output"].startswith("[rc=7] compressed:")
        for field in ("code", "exit_code", "returncode", "error", "opaque"):
            assert result[field] == payload[field]

    def test_json_output_passes_through_unchanged(self):
        output = json.dumps({"items": [{"id": i} for i in range(30)]})
        raw = json.dumps({"output": output, "code": 0, "opaque": True})
        with patch.object(rtk_hermes, "_RUST_AVAILABLE", True), patch.object(
            rtk_hermes, "_rust_compress", side_effect=AssertionError("must not compress JSON")
        ):
            assert rtk_hermes._pre_tool_call_result("terminal", raw) is None

    @pytest.mark.parametrize("result", ["not-json", "", "[]", None, 123])
    def test_unsupported_serialized_shapes_pass_through(self, result):
        assert rtk_hermes._pre_tool_call_result("terminal", result) is None

    def test_compressor_exception_fails_open(self):
        raw = json.dumps({"output": "x\n" * 300, "code": 0})
        with patch.object(rtk_hermes, "_RUST_AVAILABLE", True), patch.object(
            rtk_hermes, "_rust_compress", side_effect=RuntimeError("compressor unavailable")
        ):
            assert rtk_hermes._pre_tool_call_result("terminal", raw) is None


class TestRegistration:
    def test_registers_verified_hooks(self):
        ctx = MagicMock()
        with patch.object(rtk_hermes, "_check_rtk", return_value=True), patch.object(
            rtk_hermes, "_RUST_AVAILABLE", True
        ):
            rtk_hermes.register(ctx)
        names = [call.args[0] for call in ctx.register_hook.call_args_list]
        assert names == ["pre_tool_call", "transform_tool_result"]

    def test_missing_rtk_does_not_raise(self):
        ctx = MagicMock()
        with patch.object(rtk_hermes, "_check_rtk", return_value=False), patch.object(
            rtk_hermes, "_RUST_AVAILABLE", False
        ):
            rtk_hermes.register(ctx)
        ctx.register_hook.assert_not_called()
