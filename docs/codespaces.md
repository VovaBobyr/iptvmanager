# GitHub Codespaces workflow

IPTV Manager supports the same dashboard and scanner on a local computer and in GitHub
Codespaces. Each environment owns a separate SQLite database; backups are the deliberate transfer
mechanism between them.

## Create and use a Codespace

1. Open the repository on GitHub.
2. Select **Code**, **Codespaces**, then **Create codespace on main**.
3. Wait for the dev container to finish. It installs the Python package, starts Uvicorn on port
   8000, and opens the dashboard through a private forwarded port. Codespaces uses HTTP stream
   validation by default; FFprobe remains an optional enhancement for other deployments.
4. Import or restore a playlist database and start a scan from the dashboard.

Application state is stored at `data/iptv.db` under `/workspaces`, so it survives stopping,
starting, and rebuilding the same Codespace. Download a backup before deleting the Codespace.

## Move state between environments

Use **Download backup** to create a consistent SQLite snapshot while the application is running.
Use **Restore backup** in the destination environment. Restore:

- accepts only a valid IPTV Manager SQLite database;
- runs SQLite's integrity check;
- is refused while a health scan is active;
- keeps `data/before-restore-YYYYMMDD-HHMMSS.db` as a local safety copy;
- marks any scan that was active in the imported database as interrupted and resumable.

The `data` directory is intentionally excluded from Git. Never synchronize a live SQLite database
through Git commits, cloud file mirroring, or simultaneous writers.

## Scan behavior

Health results record `IPTV_RUNNER_NAME`. Codespaces automatically uses
`codespace:<codespace-name>`; local installations default to `local`. Set a descriptive value such
as `local-prague` when useful.

A Codespace scan originates from GitHub's network rather than the home network, so availability
and geographic restrictions may differ. Both results are evidence from their respective runner.

Codespaces normally stop after an idle timeout and have a maximum continuous lifetime. When this
happens, restart the Codespace and use **Resume previous scan**. Increasing the personal idle
timeout can reduce interruptions, but resumption remains the recovery mechanism.

## Port and Hot Player limitations

The management port is private by default. Making it public would expose the dashboard and all
mutation APIs, and public visibility is not a durable hosting contract. Do not use a Codespaces URL
as the permanent Hot Player playlist URL.

For permanent TV access, run the same container on an always-on host with persistent storage,
HTTPS, authentication for management routes, and a protected playlist URL.
