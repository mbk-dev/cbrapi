"""Static scanner fixture. Never execute this module's example function."""
import os
import subprocess
import sys


def untrusted_command_aliases():
    dynamic_program = [os.environ['PROGRAM'], 'worker.py']
    # ruleid: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(dynamic_program)

    shell = ['bash', '-c', os.environ['PAYLOAD']]
    # ruleid: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(shell)

    tuple_shell = ('bash', '-c', os.environ['PAYLOAD'])
    # ruleid: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(tuple_shell)


def aliased_source():
    get = os.getenv
    command = get('COMMAND')
    # ruleid: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(command, shell=True)


def literal_executables_with_data_arguments():
    office = ['libreoffice', sys.argv[1]]
    # ok: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(office)
    pdf = ['pdftotext', str(sys.argv[1])]
    # ok: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(pdf)
    wrapper = ['systemd-run', '--setenv', f'PATH={os.environ.get("PATH", "/usr/bin:/bin")}', sys.executable, 'worker.py']
    # ok: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(wrapper)
