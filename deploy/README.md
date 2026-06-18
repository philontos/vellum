# Vellum — VPS deploy runbook

Single-user, **localhost-only** backend + built web, reached over an **SSH
tunnel**. No public exposure, no domain, no ICP filing. Mainland-to-mainland.

> **One-command deploy (after the one-time setup in §1):** `deploy/start.sh` builds
> the web, installs/refreshes the systemd service, and starts it — it does §2–§3
> for you. Re-run it after every `git pull`.
> ```bash
> VELLUM_PORT=18090 ./deploy/start.sh   # drop VELLUM_PORT= to use the default 18080
> ```
> The numbered steps below document what it does, plus prereqs (§0), data
> migration (§1), the firewall (§4), tunnel access (§5), and backups (§6).

## 0. Prereqs (Debian/Ubuntu VPS)
- `sudo apt-get install -y python3.12 python3.12-venv libsqlcipher-dev pkg-config git`
  — the **`python3.12-venv`** package is required; without it `setup.sh` can't build the venv.
- Node 18+ and **pnpm**. If `pnpm` is missing even though Node is installed:
  `npm install -g pnpm` (or `corepack enable pnpm`).
- Decide where it lives and who runs it. The steps below assume `/opt/vellum` and a
  dedicated `vellum` user (cleanest). Running **as root under your home dir** also
  works — just adjust the paths in `vellum.service` and drop its `User=`/`Group=` lines.

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
Default port is **18080**. If it's already taken (check `ss -ltn | grep :18080`),
set a free one in the unit — edit `vellum.service` and change `Environment=VELLUM_PORT=`
to e.g. `18090` — and use that same port in the tunnel (§5) and the curl below.

```bash
sudo cp /opt/vellum/deploy/vellum.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vellum
systemctl status vellum                     # active (running)
curl -s http://127.0.0.1:18080/health       # {"status":"ok"}  (use your VELLUM_PORT)
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
# local 18080  ->  VPS 127.0.0.1:<VELLUM_PORT>   (remote = the port you set in §3)
ssh -N -L 18080:127.0.0.1:18080 <user>@<VPS_IP>
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

## 8. Updating / restarting

Update to the latest code and redeploy in one shot — `update.sh` runs `git pull`
then `start.sh` (rebuild web + refresh unit + restart):
```bash
VELLUM_PORT=18090 ./deploy/update.sh     # the port you deployed with
```
Or do it by hand: `git pull` then `VELLUM_PORT=18090 ./deploy/start.sh`.

Lower-level controls when you don't need a rebuild:
```bash
sudo systemctl restart vellum    # restart now
sudo systemctl status vellum     # is it running?
journalctl -u vellum -f          # live logs (Ctrl-C to stop)
```
Data isn't touched by an update — it lives in `api/data/` (and your backup remote).
