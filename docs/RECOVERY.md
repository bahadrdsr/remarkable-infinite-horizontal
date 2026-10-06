# Recovery and removal

## Turn off infinite canvas without restarting

Use **Settings > Display settings > Infinite horizontal canvas**.

Per-notebook overrides continue to apply. Set a notebook to **Use global setting** if you want it to follow the global switch.

## Return the current runtime to stock

```powershell
python .\tools\infinite_horizontal.py stop
```

This:

- stops the modified editor through the guarded transition;
- removes only project-owned runtime service files;
- starts the original vendor service;
- verifies document sync;
- leaves the persistent boot preference unchanged.

## Disable automatic activation

```powershell
python .\tools\infinite_horizontal.py disable-autostart --approve-root-change
```

This removes the project-owned persistent systemd unit. It does not remove notebook data or backups.

## Re-enable automatic activation

First start and validate the current release manually, then:

```powershell
python .\tools\infinite_horizontal.py enable-autostart --approve-root-change
```

## Uninstall

```powershell
python .\tools\infinite_horizontal.py uninstall --approve-root-change
```

Uninstall returns to stock, disables automatic startup, and removes application code and settings. Native notebook backups remain under:

```text
/home/root/remarkable-infinite-horizontal/backups/
```

Copy or remove those backups deliberately.

## Boot completed in stock mode

This is the expected fail-closed behavior after:

- unsupported firmware;
- a failed activation;
- an interrupted previous startup;
- missing or modified release artifacts.

Connect USB and inspect:

```powershell
python .\tools\infinite_horizontal.py status
ssh root@10.11.99.1 journalctl -u remarkable-infinite-horizontal.service --no-pager
```

Do not publish unfiltered tablet logs. They may contain document names, account data, or service information.

## Tablet cannot start normally

Use the official reMarkable software recovery procedure. The project does not change boot partitions, the bootloader, kernel, or recovery components.

Official software recovery is also the supported route for leaving developer mode.
