# Security

## Supported version

Only reMarkable Paper Pure software `3.28.0.172` is currently supported.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for the repository when available. Do not open a public issue containing credentials, notebook data, private logs, or a working exploit against a modified tablet.

## Security boundaries

- SSH host keys are verified.
- Passwords are entered interactively.
- Downloaded upstream artifacts are hash checked.
- Generated stock resources and backups remain local.
- Installation paths and service overrides are ownership checked.
- Unsupported firmware fails closed.
- Automatic startup is bounded and disables itself after failure.

Developer mode weakens the tablet security model. Users should understand that risk before installation.
