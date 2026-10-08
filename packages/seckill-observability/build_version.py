"""Build-time identity of application and telemetry source, without Git/secrets."""
import hashlib
from pathlib import Path

digest = hashlib.sha256()
for root in (Path('/app'), Path('/opt/seckill-observability/src')):
    for path in sorted(root.rglob('*')):
        if path.is_file() and (path.suffix == '.py' or path.name == 'requirements.txt') and '__pycache__' not in path.parts:
            digest.update(str(path.relative_to(root)).encode())
            digest.update(b'\0')
            digest.update(path.read_bytes())
Path('/app/.observability-version').write_text('source-sha256:' + digest.hexdigest()[:16], encoding='ascii')
