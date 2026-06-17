# Vellum — VPS deploy runbook

Single-user, **localhost-only** backend + built web, reached over an **SSH
tunnel**. No public exposure, no domain, no ICP filing. Mainland-to-mainland.

## 0. Prereqs (Debian/Ubuntu VPS)
- Python 3.12, Node 18+ with `pnpm`, `git`
- `sudo apt-get install -y libsqlcipher-dev pkg-config`
- a non-root user `vellum`

## 1. Backend
```bash
sudo mkdir -p /opt/vellum && sudo chown vellum:vellum /opt/vellum
sudo -u vellum git clone <your-repo-url> /opt/vellum
cd /opt/vellum/api
./setup.sh        # venv + deps + sqlcipher driver + key handling
```
- **Brand-new data:** `setup.sh` generates `VELLUM_DB_KEY` and prints it — back it up.
- **Migrating existing data:** put your **existing** key into `api/.env` *before*
  running `setup.sh` (it never overwrites an existing key), and bring your
  encrypted db over (`python -m app.sync pull` against your backup remote, or
  `scp` `api/data/vellum.db`).

Fill `api/.env`: `LLM_*`, `EMBED_*`, `VELLUM_DB_KEY`, and (for backups)
`VELLUM_SYNC_REMOTE`.

## 2. Build the web (served by FastAPI on one origin)
```bash
cd /opt/vellum/web && pnpm install && pnpm build   # -> web/dist
```

## 3. Install + start the service
```bash
sudo cp /opt/vellum/deploy/vellum.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vellum
systemctl status vellum                     # active (running)
curl -s http://127.0.0.1:18080/health       # {"status":"ok"}
```

## 4. Lock down the network (the "ACL")
- The app binds `127.0.0.1` only (the unit enforces `--host 127.0.0.1`) — it is
  not reachable on the public IP.
- Firewall: allow inbound **SSH only**.
  ```bash
  sudo ufw default deny incoming
  sudo ufw allow 22/tcp
  sudo ufw enable
  ```
  (If your provider has a cloud security group, mirror it: only 22 inbound.)
- Optional tighter ACL: restrict SSH source to your usual IP ranges.

## 5. Access from each PC (SSH tunnel)
```bash
ssh -N -L 18080:127.0.0.1:18080 vellum@<VPS_IP>
```
then open <http://localhost:18080>. Convenience: add a `~/.ssh/config` host +
a shell alias, or `autossh` / a login launch agent so it reconnects.

## 6. Encrypted backups (replaces the multi-device baton)
- One-time: create an empty **private** repo; set `VELLUM_SYNC_REMOTE` in `api/.env`.
- Cron for the `vellum` user (`crontab -e`):
  ```cron
  30 3 * * * /opt/vellum/deploy/backup.sh >> /tmp/vellum-backup.log 2>&1
  ```
- Confirm the remote only ever holds ciphertext.

## 7. Verification checklist
- [ ] `sudo reboot` → service comes back (`systemctl status vellum`).
- [ ] `sudo systemctl kill vellum` (or kill the uvicorn PID) → systemd restarts it.
- [ ] Second PC via the tunnel: chat works, history loads.
- [ ] From another host: `curl http://<VPS_IP>:18080/health` is refused/times
      out (app is **not** public).
- [ ] `deploy/backup.sh` runs clean; the remote repo shows only the encrypted
      `vellum.db`.
