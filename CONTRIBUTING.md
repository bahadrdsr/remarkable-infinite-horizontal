# Contributing

Thanks for helping.

## Ground rules

- Keep changes focused on the native notebook implementation.
- Do not commit reMarkable stock QML, notebook files, backups, credentials, screenshots containing passwords, SDK installers, or downloaded binaries.
- Do not weaken device, firmware, artifact, ownership, or recovery checks.
- Preserve document sync and stock fallback behavior.
- Treat new firmware and devices as unsupported until they have their own reviewed hashes and physical acceptance.

## Development

```powershell
python -m pip install -r .\tools\requirements.txt
.\tools\Build-Local.ps1
```

Device work also requires the matching official SDK:

```powershell
.\tools\Build-Device.ps1
```

## Pull requests

Describe:

- the behavior being changed;
- the practical reason;
- safety/recovery implications;
- exact tests run;
- physical device and firmware used, if applicable.

Never include private tablet logs or notebook content.
