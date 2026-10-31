"""Capture native UI evidence while the disposable Android integration test runs.

Run the disposable tests/browser_server.py first. No personal runtime is used.
Paths to installed tools are arguments, never committed machine configuration.
"""
import argparse
from pathlib import Path
import re
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flutter', required=True)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--device', default='emulator-5554')
    parser.add_argument('--test', default='integration_test/user_flow_test.dart')
    parser.add_argument('--output', default='.impeccable/review')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / args.output
    output.mkdir(parents=True, exist_ok=True)

    def adb(*command):
        return subprocess.check_output([args.adb, '-s', args.device, *command])

    night = adb('shell', 'cmd', 'uimode', 'night').decode().strip().split()[-1]
    scale = adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip()
    adb('reverse', 'tcp:8765', 'tcp:8765')
    try:
        adb('shell', 'cmd', 'uimode', 'night', 'no')
        adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        command = [args.flutter, 'test', args.test,
                   '-d', args.device, '--dart-define=SIGNSIGHT_TEST_API=http://127.0.0.1:8765',
                   '--dart-define=SIGNSIGHT_CAPTURE_VISUALS=true']
        with subprocess.Popen(command, cwd=root / 'mobile', stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                              errors='replace') as child, (output / 'native-test.log').open('w', encoding='utf-8') as log:
            for line in child.stdout:
                log.write(line)
                log.flush()
                match = re.search(r'SIGNSIGHT_VISUAL_READY:([a-z-]+)', line)
                if match:
                    time.sleep(.5)
                    png = adb('exec-out', 'screencap', '-p')
                    if not png.startswith(b'\x89PNG\r\n\x1a\n'):
                        raise RuntimeError('adb returned an invalid PNG')
                    (output / (match[1] + '.png')).write_bytes(png)
                    print('Captured ' + match[1], flush=True)
                elif 'SIGNSIGHT_VISUAL_PROFILE:dark-large' in line:
                    adb('shell', 'cmd', 'uimode', 'night', 'yes')
                    adb('shell', 'settings', 'put', 'system', 'font_scale', '1.3')
                elif 'All tests passed' in line or '[E]' in line or 'FAIL' in line:
                    print(line.strip(), flush=True)
            result = child.wait()
        if result:
            print((output / 'native-test.log').read_text(encoding='utf-8')[-9000:], flush=True)
        raise SystemExit(result)
    finally:
        adb('shell', 'cmd', 'uimode', 'night', night)
        if scale == 'null':
            adb('shell', 'settings', 'delete', 'system', 'font_scale')
        else:
            adb('shell', 'settings', 'put', 'system', 'font_scale', scale)
        adb('reverse', '--remove', 'tcp:8765')


if __name__ == '__main__':
    main()
