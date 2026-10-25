"""Pinned, advisory source audit. Raw reports stay in a private temporary directory."""
import hashlib
import json
import os
from pathlib import Path
import re
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


def command(args, log, timeout=600, env=None, diagnostics=None):
    started = time.monotonic()
    status, returncode = 'launch_error', None
    with log.open('wb') as output:
        try:
            returncode = subprocess.run(args, stdout=output, stderr=subprocess.STDOUT,
                                        timeout=timeout, env=env, cwd=log.parent, check=False).returncode
            status = 'exited'
            return returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
            return 124
        except OSError:
            return 124
        finally:
            if diagnostics is not None:
                diagnostics.clear()
                diagnostics.update(status=status, returncode=returncode,
                                   duration_ms=min(2_147_483_647, max(0, round((time.monotonic() - started) * 1000))))


def download(pin, destination):
    if urllib.parse.urlsplit(pin['url']).scheme != 'https':
        raise ValueError('tool_url_scheme')
    deadline = time.monotonic() + 300
    with urllib.request.build_opener(HttpsRedirects()).open(pin['url'], timeout=30) as response, destination.open('wb') as output:
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


def audit():  # noqa: C901 - Keep the redacted failure boundary around the complete scanner pipeline.
    os.umask(0o077)
    root = Path.cwd()
    state = Path(tempfile.mkdtemp(prefix='security-audit-', dir=os.environ.get('RUNNER_TEMP')))
    pins = json.loads((HERE / 'tools.json').read_text())
    result = {'version': 1, 'mode': 'advisory', 'scanners': {}, 'tools': [{k: p[k] for k in ('tool', 'version', 'sha256')} for p in pins],
                  'limitations': ['Source only; deployed images, host OS and live configuration are not checked.',
                               'No application installation. Unlocked, vendored and unsupported inputs require separate review.',
                               'Counts are candidates, not confirmed vulnerabilities. No automatic baseline suppression.']}
    failed = False
    try:
        policy = load_source_policy(root, os.environ.get('SECURITY_BASE_SHA', ''), pins)
        result['baseline'] = {'sha256': hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
                                  'policy': 'reviewed_parser_gaps_only',
                                  'source': 'pull_request_base' if os.environ.get('SECURITY_BASE_SHA') else 'checkout'}
        for pin in pins:
            archive = state / (pin['tool'] + ('.whl' if pin['tool'] == 'semgrep' else '.tar.gz'))
            if pin['tool'] == 'semgrep':
                archive = state / pin['url'].rsplit('/', 1)[1]
            download(pin, archive)
            if pin['tool'] in ('trivy', 'gitleaks'):
                with tarfile.open(archive) as tar:
                    member = tar.getmember(pin['tool'])
                    if not member.isfile() or member.size > 200_000_000:
                        raise ValueError('invalid_tool_archive')
                    binary = state / pin['tool']
                    binary.write_bytes(tar.extractfile(member).read())
                    binary.chmod(0o700)
        venv = state / 'venv'
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'LC_ALL', 'RUNNER_TEMP', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}}
        (state / 'home').mkdir()
        env['HOME'] = str(state / 'home')
        env.update(SEMGREP_SEND_METRICS='off', SEMGREP_ENABLE_VERSION_CHECK='0', TRIVY_CACHE_DIR=str(state / 'trivy-cache'))
        if command([sys.executable, '-m', 'venv', str(venv)], state / 'venv.log', env=env):
            raise ValueError('venv_failed')
        python = str(venv / 'bin/python')
        wheel = next(state.glob('semgrep-*.whl'))
        if command([python, '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--index-url', 'https://pypi.org/simple', '-c', str(HERE / 'constraints.txt'), str(wheel)], state / 'pip.log', env=env):
            raise ValueError('scanner_install_failed')
        rules = state / 'rules.yaml'
        if command([python, str(HERE / 'run.py'), '--pack', str(state / 'semgrep-rules.tar.gz'), str(rules)], state / 'rules.log', env=env):
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
        result['secret_scope'] = 'pr_commits' if scope else 'all_history'
        jobs = {
            'gitleaks': [str(state / 'gitleaks'), 'git', str(root), '--config', str(config), '--log-opts=' + log_opts, '--ignore-gitleaks-allow', '--gitleaks-ignore-path', str(ignore), '--redact=100', '--exit-code=10', '--report-format=json', '--report-path', str(state / 'gitleaks.json')],
            'trivy': [str(state / 'trivy'), 'fs', '--config', str(trivy_config), '--ignorefile', str(ignore), '--scanners=vuln', '--include-dev-deps', '--list-all-pkgs', '--format=json', '--output', str(state / 'trivy.json'), '--skip-dirs=.git,node_modules,.venv,tmp', '--timeout=8m', str(root)],
            'semgrep': [str(venv / 'bin/semgrep'), 'scan', '--config', str(rules), '--metrics=off', '--disable-version-check', '--disable-nosem', '--x-ignore-semgrepignore-files', '--timeout=20', '--jobs=2', '--max-memory=512', '--no-git-ignore', '--exclude=.git', '--exclude=node_modules', '--exclude=.venv', '--exclude=tmp', '--json', '--output', str(state / 'semgrep.json'), str(root)],
        }
        for tool, args in jobs.items():
            execution = {}
            wall_limit_seconds = 1800 if tool == 'semgrep' else 600
            code = command(args, state / (tool + '.log'), timeout=wall_limit_seconds,
                           env=env, diagnostics=execution)
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
            if tool == 'semgrep':
                result['scanners'][tool] = apply_known_gaps(result['scanners'][tool], payload, policy, root)
            result['scanners'][tool].update(execution=execution, report_state=report_state)
            failed |= result['scanners'][tool]['status'] in ('tool_error', 'partial')
    except Exception:
        # Exception messages can contain attacker-controlled URLs, paths or source text.
        result['bootstrap_status'] = 'tool_error'
        failed = True
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a') as stream:
            stream.write('Security audit (advisory findings; tool errors fail the job)\n\n```json\n' + output + '\n```\n')
    return int(failed)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--pack':
        pack_rules(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        sys.exit(audit())
