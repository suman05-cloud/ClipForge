"""Package source, built UI and docs; exclude media, models and environments."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
destination=root.parent/'clipforge-source.zip'
excluded={'.venv','node_modules','data','test-output','__pycache__','.pytest_cache','.git'}
with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
    for file in sorted(root.rglob('*')):
        relative=file.relative_to(root)
        if not file.is_file() or any(part in excluded for part in relative.parts):
            continue
        if file.name=='.env' or file.suffix in ('.pyc','.log','.tsbuildinfo'):
            continue
        archive.write(file,Path('clipforge')/relative)
print(destination)
print(f'{destination.stat().st_size:,} bytes')
