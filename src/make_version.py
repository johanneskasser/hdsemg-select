# src/make_version.py

import os
from version import __version__

# Zerlege die Versionsnummer in vier Ganzzahlen
parts = __version__.split('.')
# Fülle ggf. bis 4 Teile auf, z.B. "1.2" → [ "1","2","0","0" ]
while len(parts) < 4:
    parts.append('0')
# Formatiere für FixedFileInfo (Ganzzahlen)
file_ver = ', '.join(parts[:4])
prod_ver = file_ver

# PyInstaller VSVersionInfo Block
template = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    FileVersion=({file_ver}),
    ProductVersion=({prod_ver}),
    FileFlagsMask=0x3f,
    FileFlags=0x00,
    FileOS=0x4,
    FileType=0x1,
    FileSubtype=0x0
  ),
  StringFileInfo([
    StringTable(
      '040904B0',
      [
        StringStruct('FileDescription', 'hdsemg-select'),
        StringStruct('FileVersion', '{__version__}'),
        StringStruct('InternalName', 'hdsemg-select.exe'),
        StringStruct('OriginalFilename', 'hdsemg-select_v{__version__}.exe'),
        StringStruct('ProductName', 'hdsemg-select'),
        StringStruct('ProductVersion', '{__version__}'),
        StringStruct('CompanyName', 'University of Applied Sciences Vienna - Department Physiotherapy'),
      ]
    )
  ]),
  VarFileInfo([VarStruct('Translation', [0x0409, 1252])])
)
'''

out = 'version.txt'
with open(out, 'w', encoding='utf-8') as f:
    f.write(template)

print(f" Generated {out} for version {__version__}")
