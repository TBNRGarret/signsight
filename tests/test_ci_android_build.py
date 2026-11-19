"""CI retries repository outages, never ordinary build failures."""
import sys

import pytest

from scripts.ci_android_build import build_with_retries, stream_attempt


OUTAGE = (
    "Could not resolve org.jetbrains.kotlin:kotlin-stdlib:2.2.21.\n"
    "Could not GET 'https://repo.maven.apache.org/maven2/example.pom'. "
    "Received status code 429 from server: Too Many Requests"
)


def run_sequence(outcomes):
    attempts, waits = [], []

    def attempt():
        attempts.append(True)
        return next(outcomes)

    code = build_with_retries(attempt, sleep=waits.append)
    return code, len(attempts), waits


def test_success_without_retry():
    assert run_sequence(iter([(0, "BUILD SUCCESSFUL")])) == (0, 1, [])


def test_repository_429_recovers_with_backoff():
    assert run_sequence(iter([(1, OUTAGE), (0, "ok")])) == (0, 2, [30])


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_mirror_temporary_http_errors_can_retry(status):
    log = ("Could not HEAD 'https://maven-central.storage-download.googleapis.com/maven2/example.jar'. "
           f"Received status code {status} from server")
    assert run_sequence(iter([(1, log), (0, "ok")])) == (0, 2, [30])


@pytest.mark.parametrize("message", [
    "Compilation error: unresolved reference",
    "Execution failed for task ':app:compileDebugKotlin'.",
    "Could not resolve dependency: Received status code 403 from server",
    "Received status code 429 from https://unrelated.example/upload",
    "Could not GET 'https://repo.maven.apache.org/example'. Received status code 404",
])
def test_deterministic_or_unrelated_failure_is_not_retried(message):
    assert run_sequence(iter([(7, message)])) == (7, 1, [])


def test_repository_failure_is_bounded_and_preserves_failure():
    assert run_sequence(iter([(9, OUTAGE)] * 3)) == (9, 3, [30, 90])


def test_retry_stops_when_next_failure_is_a_compile_error():
    assert run_sequence(iter([(1, OUTAGE), (4, "Compilation error")])) == (4, 2, [30])


def test_real_child_output_and_exit_status_are_preserved(capsys):
    code, log = stream_attempt([
        sys.executable, "-c",
        "import sys; print('stdout'); print('stderr', file=sys.stderr); sys.exit(6)",
    ])
    assert code == 6
    assert "stdout" in log and "stderr" in log
    assert "stdout" in capsys.readouterr().out


def test_missing_build_tool_fails_without_retry():
    with pytest.raises(FileNotFoundError):
        stream_attempt(["signsight-no-such-build-tool"])
