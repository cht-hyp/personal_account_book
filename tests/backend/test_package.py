"""Release regressions: Windows line endings and a clean runtime ZIP."""
import zipfile

import pytest

from scripts.package import write_package


def test_runtime_zip_uses_current_files_and_preserves_other_releases(tmp_path):
    project = tmp_path / 'project'
    files = {
        'backend/run.py': 'print("current source")',
        'backend/__pycache__/cache.py': 'omit',
        'frontend/dist/index.html': '<html>current build</html>',
        'frontend/dist/assets/app.js': 'current assets',
        'scripts/setup.bat': '@echo off\necho setup\n',
        'scripts/start.bat': '@echo off\necho start\n',
        'requirements.txt': 'Flask==3.1.2\n',
        'docs/运行包说明.md': 'runtime guide',
        'docs/代码要点.md': 'code guide',
        'data/records.json': 'private ledger',
        '.git/config': 'private config',
    }
    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    output = project / 'release'
    output.mkdir()
    previous = output / 'previous.zip'
    previous.write_bytes(b'keep')
    archive = write_package(project, 'v1.0.0', output)
    prefix = 'qing-ledger-v1.0.0-windows/'
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.read(prefix + 'web/index.html') == b'<html>current build</html>'
        assert zipped.read(prefix + 'backend/run.py') == b'print("current source")'
        assert zipped.read(prefix + 'scripts/setup.bat') == b'@echo off\r\necho setup\r\n'
        assert not any('records.json' in name or '__pycache__' in name or '.git/' in name for name in zipped.namelist())
    assert previous.read_bytes() == b'keep'
    with pytest.raises(FileExistsError):
        write_package(project, 'v1.0.0', output)


def test_version_cannot_escape_release_directory(tmp_path):
    with pytest.raises(ValueError):
        write_package(tmp_path, '../outside', tmp_path / 'release')
