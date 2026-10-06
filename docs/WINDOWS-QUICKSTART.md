# Windows quick start

This guide is for people who use reMarkable but do not normally develop software.

## What the installer changes

The installer adds infinite horizontal panning to handwritten notebooks. It does not replace the notebook app, writing tools, sync service, firmware, kernel, or recovery system.

It is unofficial software. Keep a backup and understand how to use official software recovery before continuing.

## Step 1: Verify the tablet version

On the tablet:

1. Open **Settings**.
2. Open **Software**.
3. Confirm the version is exactly `3.28.0.172`.

Stop if the version is different.

## Step 2: Back up your notebooks

Confirm important notebooks are synchronized or independently exported. Open a few files from the backup location before continuing.

## Step 3: Enable developer mode

Developer mode must already be enabled. Enabling it factory-resets the tablet.

Follow reMarkable's official developer-mode instructions and save the generated SSH password somewhere secure.

The SSH password is not the tablet screen PIN.

## Step 4: Install Windows prerequisites

Install:

1. [Python 3](https://www.python.org/downloads/windows/)
2. Ubuntu using:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if requested, open Ubuntu once, and complete its first-time username setup.

## Step 5: Download this project

On the GitHub repository page:

1. Select **Code**.
2. Select **Download ZIP**.
3. Extract the ZIP.
4. Open the extracted folder.
5. Right-click empty space and choose **Open in Terminal**.

## Step 6: Connect the tablet

Wake and unlock the tablet. Connect it using a data-capable USB-C cable.

Leave it awake during installation.

## Step 7: Run the guided installer

In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Easy-Install.ps1
```

The installer asks you to type:

```text
I HAVE A BACKUP
```

It then installs host dependencies, downloads the matching official SDK, builds/tests the project, and asks for the generated tablet SSH password.

The process can take several minutes. There are deliberate three-minute pauses between notebook-editor transitions.

## Step 8: Use infinite canvas

After installation:

1. Open **Settings > Display settings**.
2. Enable **Infinite horizontal canvas**.
3. Open a handwritten notebook.
4. Use two fingers to pan left and right.

For one notebook:

1. Open **Notebook settings**.
2. Enable **Override global canvas setting**.
3. Choose **Infinite for this notebook** on or off.
4. Tap **Save**.

## If installation stops

The installer is designed to return to the original stock editor on failure.

Keep the tablet awake and connected, then run:

```powershell
python .\tools\infinite_horizontal.py status
```

See [Recovery and removal](RECOVERY.md) for the full set of recovery commands.
