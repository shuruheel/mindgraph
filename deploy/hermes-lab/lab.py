"""Private remote Hermes lab. No model/API call is made at startup or by doctor."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERMES = Path('/opt/hermes')
PLUGIN = Path('/opt/mindgraph-plugin')
PROFILE = Path('/data/profile')
RUNS = Path('/data/runs')
PYTHON = HERMES / '.venv/bin/python'


def initialize():
    plugins = PROFILE / 'plugins'
    plugins.mkdir(parents=True, exist_ok=True, mode=0o700)
    link = plugins / 'mindgraph'
    if not link.exists():
        link.symlink_to(PLUGIN, target_is_directory=True)
    elif link.resolve() != PLUGIN:
        raise RuntimeError('Existing mindgraph installation differs; inspect before replacing it.')
    config = PROFILE / 'config.yaml'
    if not config.exists():
        # Existing user settings survive image updates and restarts.
        config.write_text(
            'memory:\n  provider: mindgraph\nplugins:\n  isolation: in_process\n'
            'model:\n  default: gpt-6-luna\n  provider: custom\n'
            '  base_url: https://api.openai.com/v1\n  api_mode: codex_responses\n'
            'agent:\n  max_turns: 8\n  run_budget_seconds: 120\n  reasoning_effort: none\n'
        )
        config.chmod(0o600)


def revision(path):
    # The source is owned by root, deliberately immutable to the runtime user.
    return subprocess.check_output([
        'git', '-c', f'safe.directory={path}', '-C', str(path), 'rev-parse', 'HEAD',
    ], text=True).strip()


def provenance():
    return {
        'hermes_sha': revision(HERMES), 'plugin_sha': revision(PLUGIN),
        'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version,
        'sdk': importlib.metadata.version('mindgraph-sdk'),
        'pytest': importlib.metadata.version('pytest'),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'profile': str(PROFILE),
    }


def doctor():
    result = provenance()
    # Credential values and model prompts never appear in diagnostic output.
    result['environment_credentials_present'] = {
        name: bool(os.environ.get(name)) for name in (
            'MINDGRAPH_EVAL_API_KEY', 'MINDGRAPH_API_KEY', 'OPENROUTER_API_KEY',
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
        )
    }
    result['profile_writable'] = os.access(PROFILE, os.W_OK)
    result['plugin_link_correct'] = (PROFILE / 'plugins/mindgraph').resolve() == PLUGIN
    result['uid'] = os.getuid()
    print(json.dumps(result, indent=2))
    return 0 if result['profile_writable'] and result['plugin_link_correct'] else 1


def run_check(mode):
    """Each check has fresh state and a saved exit code; never tests in the live profile."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = Path(tempfile.mkdtemp(prefix=f'{stamp}-{mode}-', dir=RUNS))
    env = os.environ.copy()
    # Isolate from real profile configuration and credentials, even after setup.
    for name in list(env):
        if name.startswith(('MINDGRAPH_', 'HERMES_')) or name.endswith(('_API_KEY', '_AUTH_TOKEN')):
            env.pop(name)
    env.update(HOME=str(directory), HERMES_HOME=str(directory / 'home'), PYTHONPATH=str(HERMES))
    if mode == 'host-checks':
        env['HERMES_HOST_TESTS'] = '1'
        command = [str(PYTHON), '-m', 'pytest', 'tests/host', '-q', '-p', 'no:cacheprovider']
    elif mode == 'unit-checks':
        command = [str(PYTHON), '-m', 'pytest', '-q', '-p', 'no:cacheprovider']
    else:
        command = [str(PYTHON), '-m', 'evals.run', '--offline', '--report', str(directory / 'outcomes.json')]
    metadata = {**provenance(), 'mode': mode, 'started_at': stamp, 'network': 'scripted local API only'}
    (directory / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with (directory / 'output.log').open('w') as output:
        result = subprocess.run(command, cwd=PLUGIN, env=env, stdout=output, stderr=subprocess.STDOUT)
    metadata['exit_code'] = result.returncode
    (directory / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print((directory / 'output.log').read_text())
    print(f'Evidence: {directory}')
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'doctor', 'host-checks', 'unit-checks', 'offline-checks', 'hermes'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.arguments and args.command != 'hermes':
        parser.error('extra arguments are only accepted after hermes')
    if args.command == 'init':
        initialize()
        return 0
    if args.command == 'doctor':
        return doctor()
    if args.command == 'hermes':
        os.chdir('/data/workspace')
        os.execv(str(HERMES / '.venv/bin/hermes'), ['hermes', *args.arguments])
    return run_check(args.command)


if __name__ == '__main__':
    raise SystemExit(main())
