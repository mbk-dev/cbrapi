"""Static scanner fixture. Never execute this module's example function."""
import os
import subprocess


def untrusted_command_aliases():
    dynamic_program = [os.environ['PROGRAM'], 'worker.py']
    # ruleid: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(dynamic_program)

    shell = ['bash', '-c', os.environ['PAYLOAD']]
    # ruleid: 7a5f349ed5a408cd-0-0-dangerous-subprocess-use-tainted-env-args
    subprocess.run(shell)
