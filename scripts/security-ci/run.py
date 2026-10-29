"""Pinned, advisory source audit. Raw reports stay in a private temporary directory."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.parse

from summary import summarize
from baseline import apply_known_gaps, load_source_policy

HERE = Path(__file__).resolve().parent


class HttpsRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('tool_redirect_scheme')
        return super().redirect_request(request, response, code, message, headers, newurl)


STOP_GRACE_SECONDS = 10


def stop_process_group(process):
    """Collect the scanner tree, including children left after a successful parent."""
    def send(sig):
        try:
            os.killpg(process.pid, sig)
            return True
        except ProcessLookupError:
            return False
    if not send(signal.SIGTERM):
        process.wait()
        return
    deadline = time.monotonic() + STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        if not send(0):
            break
        time.sleep(.05)
    send(signal.SIGKILL)
    process.wait()


def command(args, log, timeout=600, env=None, diagnostics=None):
    started = time.monotonic()
    status, returncode = 'launch_error', None
    process = None
    previous = {}
    def cancel(signum, frame):
        raise SystemExit(128 + signum)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, cancel)
        with log.open('wb') as output:
            process = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT,
                                       env=env, cwd=log.parent, start_new_session=True)
            try:
                returncode = process.wait(timeout=timeout)
                status = 'exited'
                return returncode
            except subprocess.TimeoutExpired:
                status = 'timeout'
                return 124
            except SystemExit:
                status = 'cancelled'
                raise
    except OSError:
        return 124
    finally:
        # A repeated cancellation must not interrupt the bounded tree cleanup.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if process is not None:
                stop_process_group(process)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            if diagnostics is not None:
                diagnostics.clear()
                diagnostics.update(status=status, returncode=returncode,
                                   duration_ms=min(2_147_483_647, max(0, round((time.monotonic() - started) * 1000))))


def execution_budget(deadline, maximum):
    """Leave time to publish aggregates and collect descendants before host stop."""
    if deadline is None:
        return maximum
    remaining = int(deadline - time.monotonic()) - 20
    if remaining < 1:
        raise ValueError('audit_budget_expired')
    return min(maximum, remaining)


def download(pin, destination, deadline=None):
    if urllib.parse.urlsplit(pin['url']).scheme != 'https':
        raise ValueError('tool_url_scheme')
    deadline = time.monotonic() + execution_budget(deadline, 300)
    with urllib.request.build_opener(HttpsRedirects()).open(pin['url'], timeout=min(30, max(1, int(deadline - time.monotonic())))) as response, destination.open('wb') as output:
        if urllib.parse.urlsplit(response.url).scheme != 'https':
            raise ValueError('tool_redirect_scheme')
        digest = hashlib.sha256()
        size = 0
        while chunk := response.read1(65536):
            if time.monotonic() > deadline:
                raise ValueError('tool_download_deadline')
            size += len(chunk)
            if size > 200_000_000:
                raise ValueError('tool_size_limit')
            output.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != pin['sha256']:
        raise ValueError('tool_digest_mismatch')


def pack_rules(archive, output):
    from ruamel.yaml import YAML
    yaml = YAML(typ='safe')
    rules = []
    with tarfile.open(archive) as tar:
        for member in sorted(tar.getmembers(), key=lambda m: m.name):
            parts = Path(member.name).parts
            if not member.isfile() or member.size > 2_000_000 or len(parts) < 3:
                continue
            if parts[1] not in {'python', 'javascript', 'typescript', 'php', 'generic', 'yaml', 'terraform', 'dockerfile', 'bash'}:
                continue
            if (not member.name.endswith(('.yaml', '.yml')) or '.test.' in parts[-1]
                    or any(p in {'tests', 'test', 'fixtures'} for p in parts[2:])):
                continue
            for document, data in enumerate(yaml.load_all(tar.extractfile(member).read())):
                if not isinstance(data, dict) or not isinstance(data.get('rules'), list):
                    continue
                for index, rule in enumerate(data['rules']):
                    if not isinstance(rule, dict) or not isinstance(rule.get('id'), str):
                        raise ValueError('invalid_upstream_rule')
                    rule['id'] = hashlib.sha256(member.name.encode()).hexdigest()[:16] + '-' + str(document) + '-' + str(index) + '-' + rule['id']
                    rules.append(rule)
    if not rules:
        raise ValueError('empty_rules')
    with output.open('w') as stream:
        yaml.dump({'rules': rules}, stream)


def checkpoint(result, phase, state):
    """Publish only aggregate observations before a later stage can be killed."""
    record = {'version': 1, 'phase': phase, 'state': state,
              'scanners': result['scanners']}
    line = 'Security audit checkpoint: ' + json.dumps(record, sort_keys=True)
    print(line, flush=True)
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(path, 'a') as stream:
            stream.write(line + '\n')
            stream.flush()


def audit():  # noqa: C901 - Keep the redacted failure boundary around the complete scanner pipeline.
    os.umask(0o077)
    root = Path.cwd()
    state = Path(tempfile.mkdtemp(prefix='security-audit-', dir=os.environ.get('RUNNER_TEMP')))
    engine = os.environ.get('SECURITY_ENGINE', 'semgrep')
    stage = os.environ.get('SECURITY_STAGE', 'all')
    pins = [p for p in json.loads((HERE / 'tools.json').read_text())
            if p['tool'] != 'opengrep' or engine == 'opengrep']
    result = {'version': 1, 'mode': 'advisory', 'scanners': {}, 'tools': [{k: p[k] for k in ('tool', 'version', 'sha256')} for p in pins],
                  'limitations': ['Source only; deployed images, host OS and live configuration are not checked.',
                               'No application installation. Unlocked, vendored and unsupported inputs require separate review.',
                               'Counts are candidates, not confirmed vulnerabilities. No automatic baseline suppression.']}
    failed = False
    interrupted_code = None
    checkpoint(result, 'bootstrap', 'started')
    try:
        if engine not in {'semgrep', 'opengrep'} or stage not in {'all', 'sast', 'secrets', 'dependencies'}:
            raise ValueError('unsupported_engine_or_stage')
        deadline = None
        if raw_budget := os.environ.get('SECURITY_RUNTIME_SECONDS'):
            budget = int(raw_budget)
            if not 60 <= budget <= 2700:
                raise ValueError('invalid_audit_budget')
            deadline = time.monotonic() + budget
        result['stage'] = stage
        selected = {'all': {'gitleaks', 'trivy', engine}, 'sast': {engine},
                    'secrets': {'gitleaks'}, 'dependencies': {'trivy'}}[stage]
        needs_sast = engine in selected
        needed_tools = selected | ({'semgrep', 'semgrep-rules'} if needs_sast else set())
        pins = [p for p in pins if p['tool'] in needed_tools]
        result['tools'] = [{k: p[k] for k in ('tool', 'version', 'sha256')} for p in pins]
        policy = None
        if needs_sast:
            policy = load_source_policy(root, os.environ.get('SECURITY_BASE_SHA', ''), pins, engine)
            result['baseline'] = {'sha256': hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
                                 'policy': 'reviewed_parser_gaps_only',
                                 'source': 'pull_request_base' if os.environ.get('SECURITY_BASE_SHA') else 'checkout'}
        for pin in pins:
            archive = state / (pin['tool'] + ('.whl' if pin['tool'] == 'semgrep' else '.tar.gz'))
            if pin['tool'] == 'semgrep':
                archive = state / pin['url'].rsplit('/', 1)[1]
            download(pin, archive, deadline=deadline)
            if pin['tool'] in ('trivy', 'gitleaks'):
                with tarfile.open(archive) as tar:
                    member = tar.getmember(pin['tool'])
                    if not member.isfile() or member.size > 200_000_000:
                        raise ValueError('invalid_tool_archive')
                    binary = state / pin['tool']
                    binary.write_bytes(tar.extractfile(member).read())
                    binary.chmod(0o700)
            elif pin['tool'] == 'opengrep':
                binary = state / 'opengrep'
                archive.replace(binary)
                binary.chmod(0o700)
        venv = state / 'venv'
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'LC_ALL', 'RUNNER_TEMP', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}}
        (state / 'home').mkdir()
        env['HOME'] = str(state / 'home')
        env.update(SEMGREP_SEND_METRICS='off', SEMGREP_ENABLE_VERSION_CHECK='0', TRIVY_CACHE_DIR=str(state / 'trivy-cache'))
        rules = state / 'rules.yaml'
        if needs_sast:
            if command([sys.executable, '-m', 'venv', str(venv)], state / 'venv.log', timeout=execution_budget(deadline, 600), env=env):
                raise ValueError('venv_failed')
            python = str(venv / 'bin/python')
            wheel = next(state.glob('semgrep-*.whl'))
            if command([python, '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--index-url', 'https://pypi.org/simple', '-c', str(HERE / 'constraints.txt'), str(wheel)], state / 'pip.log', timeout=execution_budget(deadline, 600), env=env):
                raise ValueError('scanner_install_failed')
            if command([python, str(HERE / 'run.py'), '--pack', str(state / 'semgrep-rules.tar.gz'), str(rules)], state / 'rules.log', timeout=execution_budget(deadline, 600), env=env):
                raise ValueError('rules_failed')
        config = state / 'gitleaks.toml'
        config.write_text('[extend]\nuseDefault = true\n')
        ignore = state / 'empty-ignore'
        ignore.touch()
        trivy_config = state / 'trivy.yaml'
        trivy_config.write_text('{}\n')
        scope = os.environ.get('SECURITY_BASE_SHA', '')
        log_opts = '--all'
        if scope:
            if not re.fullmatch(r'[0-9a-f]{40}', scope):
                raise ValueError('invalid_base_sha')
            log_opts = scope + '..HEAD'
        if 'gitleaks' in selected:
            result['secret_scope'] = 'pr_commits' if scope else 'all_history'
        jobs = {
            'gitleaks': [str(state / 'gitleaks'), 'git', str(root), '--config', str(config), '--log-opts=' + log_opts, '--ignore-gitleaks-allow', '--gitleaks-ignore-path', str(ignore), '--redact=100', '--exit-code=10', '--report-format=json', '--report-path', str(state / 'gitleaks.json')],
            'trivy': [str(state / 'trivy'), 'fs', '--config', str(trivy_config), '--ignorefile', str(ignore), '--scanners=vuln', '--include-dev-deps', '--list-all-pkgs', '--format=json', '--output', str(state / 'trivy.json'), '--skip-dirs=.git,node_modules,.venv,tmp', '--timeout=8m', str(root)],
            engine: [str(venv / 'bin/semgrep') if engine == 'semgrep' else str(state / 'opengrep'), 'scan', '--config', str(rules), *(['--metrics=off'] if engine == 'semgrep' else []), '--disable-version-check', '--disable-nosem', '--x-ignore-semgrepignore-files', '--timeout=20', '--jobs=1', '--max-memory=512', '--no-git-ignore', '--exclude=.git', '--exclude=node_modules', '--exclude=.venv', '--exclude=tmp', '--json', '--output', str(state / (engine + '.json')), str(root)],
        }
        jobs = {name: args for name, args in jobs.items() if name in selected}
        checkpoint(result, 'bootstrap', 'finished')
        for tool, args in jobs.items():
            execution = {}
            wall_limit_seconds = execution_budget(deadline, 3600 if tool in {'semgrep', 'opengrep'} else 600)
            checkpoint(result, tool, 'started')
            try:
                code = command(args, state / (tool + '.log'), timeout=wall_limit_seconds,
                               env=env, diagnostics=execution)
            except SystemExit:
                result['scanners'][tool] = {
                    'status': 'tool_error', 'findings': None, 'errors': 1, 'inputs': None,
                    'execution': execution, 'report_state': 'unverified_after_cancel',
                }
                checkpoint(result, tool, 'cancelled')
                raise
            execution['wall_limit_seconds'] = wall_limit_seconds
            report_state = 'json'  # Syntax only; summarize still validates the scanner schema.
            try:
                payload = json.loads((state / (tool + '.json')).read_text())
            except FileNotFoundError:
                payload, report_state = None, 'missing'
            except ValueError:
                payload, report_state = None, 'invalid_json'
            except OSError:
                payload, report_state = None, 'unreadable'
            result['scanners'][tool] = summarize(tool, payload, code)
            if tool in {'semgrep', 'opengrep'}:
                result['scanners'][tool] = apply_known_gaps(result['scanners'][tool], payload, policy, root)
            result['scanners'][tool].update(execution=execution, report_state=report_state)
            failed |= result['scanners'][tool]['status'] in ('tool_error', 'partial')
            failed |= tool in {'semgrep', 'opengrep'} and result['scanners'][tool]['status'] == 'coverage_gap'
            checkpoint(result, tool, 'finished')
    except SystemExit as error:
        failed = True
        interrupted_code = error.code if type(error.code) is int and error.code != 0 else 1
        result['execution_status'] = 'cancelled'
        if not result['scanners']:
            result['bootstrap_status'] = 'cancelled'
    except Exception:
        # Exception messages can contain attacker-controlled URLs, paths or source text.
        result['bootstrap_status'] = 'tool_error'
        failed = True
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a') as stream:
            stream.write('Security audit (advisory findings; tool errors fail the job)\n\n```json\n' + output + '\n```\n')
    return interrupted_code if interrupted_code is not None else int(failed)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--pack':
        pack_rules(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        sys.exit(audit())
