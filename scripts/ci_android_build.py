"""Build the emulator APK; retry only explicit transient repository HTTP failures."""
from collections import deque
import re
import subprocess
import time


_REPOSITORY_OUTAGE = re.compile(
    r"Could not (?:GET|HEAD) ['\"]https://(?:"
    r"repo\.maven\.apache\.org|repo1\.maven\.org|plugins\.gradle\.org|"
    r"dl\.google\.com|maven\.google\.com|"
    r"maven-central\.storage-download\.googleapis\.com)/[^\s]*['\"]"
    r"[^\n]*Received status code (?:429|502|503|504)\b"
)


def stream_attempt(command):
    # Stream live logs; retain only a bounded tail for error classification.
    tail = deque(maxlen=400)
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            tail.append(line)
        code = process.wait()
    return code, "".join(tail)


def build_with_retries(attempt, *, sleep=time.sleep, delays=(30, 90)):
    for index in range(len(delays) + 1):
        code, log = attempt()
        if code == 0 or not _REPOSITORY_OUTAGE.search(log) or index == len(delays):
            return code
        delay = delays[index]
        print(f"Repository HTTP outage; retry {index + 1}/{len(delays)} in {delay}s.", flush=True)
        sleep(delay)


def main():
    command = ["flutter", "build", "apk", "--debug", "--target-platform", "android-x64", "--no-pub"]
    return build_with_retries(lambda: stream_attempt(command))


if __name__ == "__main__":
    raise SystemExit(main())
