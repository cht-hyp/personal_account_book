"""Build a Windows runtime ZIP from current backend and fresh Vite output."""
import argparse
import hashlib
import re
import subprocess
import zipfile
from pathlib import Path


def write_package(project: Path, version: str, output: Path) -> Path:
    """Include runtime files only; normalize batch files without deleting releases."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', version):
        raise ValueError('Version must contain only letters, digits, dots, underscores and hyphens')
    if not (project / 'frontend/dist/index.html').is_file():
        raise FileNotFoundError('Build frontend/dist first')
    entries = {}
    for path in (project / 'backend').rglob('*.py'):
        if '__pycache__' not in path.parts:
            entries[path.relative_to(project).as_posix()] = path.read_bytes()
    for path in (project / 'frontend/dist').rglob('*'):
        if path.is_file():
            entries['web/' + path.relative_to(project / 'frontend/dist').as_posix()] = path.read_bytes()
    for name in ['requirements.txt', 'scripts/setup.bat', 'scripts/start.bat']:
        entries[name] = (project / name).read_bytes()
    sample = project / 'examples/demo_records.json'
    if sample.is_file():
        entries['examples/demo_records.json'] = sample.read_bytes()
    entries['README.md'] = (project / 'docs/运行包说明.md').read_bytes()
    entries['docs/代码要点.md'] = (project / 'docs/代码要点.md').read_bytes()
    entries['SOURCE_VERSION.txt'] = (
        f'Local runtime {version}\nBuilt from current backend/ and frontend/dist/.\n'
    ).encode('utf-8')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'{version}.zip'
    prefix = f'qing-ledger-{version}-windows/'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for name, content in sorted(entries.items()):
            if name.endswith('.bat'):
                content = content.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
            zipped.writestr(prefix + name, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='v1.0.0')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    # Commands are static; user-provided versions never become shell command text.
    for command in ('npm --prefix frontend ci', 'npm --prefix frontend run build'):
        subprocess.run(['cmd.exe', '/d', '/c', command], cwd=project, check=True)
    print(write_package(project, args.version, project / 'release'))


if __name__ == '__main__':
    main()
