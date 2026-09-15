#!/usr/bin/env python3
"""Product smoke test that does not call a model or consume tokens."""
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'codex-team'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    manifest = json.loads((PLUGIN / '.codex-plugin' / 'plugin.json').read_text())
    marketplace = json.loads((ROOT / '.agents' / 'plugins' / 'marketplace.json').read_text())
    assert manifest['name'] == 'codex-team'
    assert marketplace['plugins'][0]['name'] == manifest['name']
    assert (PLUGIN / 'skills' / 'codex-team' / 'SKILL.md').is_file()

    port = free_port()
    with tempfile.TemporaryDirectory() as state:
        process = subprocess.Popen([
            sys.executable, str(PLUGIN / 'server.py'), '--state', state,
            '--codex', sys.executable, '--kimi', 'missing-kimi',
            '--qwen', 'missing-qwen', '--port', str(port), '--no-open'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            url = f'http://127.0.0.1:{port}'
            deadline = time.time() + 10
            while True:
                try:
                    html = urllib.request.urlopen(url + '/', timeout=1).read().decode()
                    break
                except Exception:
                    if time.time() >= deadline:
                        raise
                    time.sleep(.1)
            assert '是否可以开始' in html
            token = re.search(r'name="team-token" content="([^"]+)"', html).group(1)
            request = urllib.request.Request(url + '/api/snapshot', headers={'X-Team-Token': token})
            snapshot = json.load(urllib.request.urlopen(request, timeout=3))
            assert snapshot['version'] == manifest['version']
            assert snapshot['capabilities']['python']
            assert snapshot['capabilities']['git']
            assert snapshot['capabilities']['codex']
        finally:
            process.terminate()
            process.wait(timeout=5)
    print('Codex Team 产品冒烟检查通过')


if __name__ == '__main__':
    main()
