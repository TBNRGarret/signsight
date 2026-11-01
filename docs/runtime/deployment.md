# Laptop and deployment

The laptop runs FastAPI/Uvicorn, SQLite, the managed image store and YOLO. FastAPI also serves the staff web UI and the optional Flutter web build. Native Android connects to the same API. Docker is optional.

## Laptop

From the canonical source checkout, use the existing external runtime directory; do not copy its database or uploads into Git:

```powershell
.\scripts\start_local.ps1 -DataRoot 'ABSOLUTE_RUNTIME_ROOT' -PythonPath 'ABSOLUTE_PYTHON_EXE'
```

Open `/web/management.html` for staff or `/app/` for the built user preview. Android emulator debug uses `http://10.0.2.2:8000`; a physical phone uses the laptop's LAN address. For LAN access, pass `-BindAddress 0.0.0.0` and allow the chosen port on the private Windows network.

For local HTTPS, create a certificate for the actual LAN IP/hostname using [mkcert](https://github.com/FiloSottile/mkcert#installation), install its public CA certificate on each test device, then run:

```powershell
.\scripts\start_local.ps1 -DataRoot 'ABSOLUTE_RUNTIME_ROOT' -PythonPath 'ABSOLUTE_PYTHON_EXE' -BindAddress 0.0.0.0 -Port 8443 -CertificatePath 'ABSOLUTE_CERT_PEM' -PrivateKeyPath 'ABSOLUTE_KEY_PEM'
```

Both certificate paths are required. The launcher does not install certificates, change the firewall or create a signing key. A release Android app needs a trusted HTTPS endpoint; merely bypassing a browser certificate warning does not establish Android trust. Use debug HTTP over the private LAN during development, or a properly trusted HTTPS endpoint.

## Database and image recovery

In a shell with the same `DATABASE_URL` and `SIGNSIGHT_STORAGE_ROOT` as the server:

```powershell
python -m backend.manage backup-runtime --output .cache/backups/runtime-20261027.zip
python -m backend.manage restore-runtime --archive .cache/backups/runtime-20261027.zip --destination .cache/recovered-20261027
```

Backup takes a SQLite snapshot (including committed WAL transactions), verifies and copies every managed image referenced by that snapshot, then writes checksums and inventory. A missing/corrupt image aborts the backup. Originals stay unchanged. Restore verifies hashes, SQLite integrity, foreign keys and the database/image inventory before publishing a **new** directory. It refuses an existing destination and revokes restored sessions. Users log in again after recovery.

Recovery produces `signsight.db` and `images/` directly in the destination. Set `DATABASE_URL=sqlite:///ABSOLUTE_RECOVERY_PATH/signsight.db` and `SIGNSIGHT_STORAGE_ROOT=ABSOLUTE_RECOVERY_PATH/images`, then start Uvicorn with those variables; do not pass that flat recovery directory as `start_local.ps1 -DataRoot`.

Backups contain private accounts, password hashes, images and metadata. Keep them outside public Git and copy a verified backup to another private disk/location. They do not include weights, external legacy evidence URLs, environment configuration or certificates; preserve those separately. Stop the service before changing to a recovered directory. Run a recovery drill in a separate runtime before considering deployment accepted.

For a custom model, preserve the exact catalog JSON and reviewed mapping JSON alongside the weights and environment configuration. The DB backup includes the catalog identity registry, but not these external configuration files. Restore with matching `SIGNSIGHT_CATALOG_PATH` and `SIGNSIGHT_YOLO_MAPPING_PATH`; startup rejects missing/reassigned catalog identities. See [model_activation.md](model_activation.md).

## Prepared server configuration

1. Install the project's Python dependencies plus `ai_engine/requirements-yolo.txt`; build Flutter web if needed. Keep the runtime directory outside the source checkout.
2. Configure absolute database, image-store and checkpoint paths. Run `python -m backend.manage migrate` and bootstrap the initial administrator interactively.
3. Bind Uvicorn to `127.0.0.1:8000`, without `--reload`, using one worker for the current in-memory rate limiter and one model instance.
4. Set `SIGNSIGHT_HOST` to the real domain, validate `deploy/Caddyfile.example` with `caddy validate --config deploy/Caddyfile.example --adapter caddyfile`, then run Caddy as the machine's managed service. DNS and ports 80/443 must point at that host for public certificates. See [Caddy reverse proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy) and [automatic HTTPS](https://caddyserver.com/docs/automatic-https).
5. Configure supervised restart, private backup retention, uptime checks, and a restore drill. Set `SIGNSIGHT_AUTO_MIGRATE=false` after running migrations explicitly.
6. Build the Android release with that HTTPS origin, test login/camera/GPS/contribution/review on a physical phone, and record real end-to-end latency over the target network.

This is a prepared configuration. No public server, DNS, certificate trust installation or production deployment has been performed by adding these files.
