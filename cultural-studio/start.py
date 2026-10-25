"""The key stays in this process's environment; it is never written to disk."""
import getpass
import os
import runpy
from pathlib import Path

if not os.getenv('PHAROS_API_KEY'):
    os.environ['PHAROS_API_KEY'] = getpass.getpass('Pharos API key (hidden): ').strip()
runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
