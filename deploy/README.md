# Vellum — VPS deploy runbook

Single-user, **localhost-only** backend + built web, reached over an **SSH
tunnel**. No public exposure, no domain, no ICP filing. Mainland-to-mainland.

> **Every deploy is one command.** After the one-time setup (§1), you pull the
> code yourself and run:
> ```bash
> git pull --ff-only
> VELLUM_PORT=18090 ./deploy/start.sh   # drop VELLUM_PORT= to use the default 18080
> ```
> `start.sh` refreshes the backend (venv + Python deps + sqlcipher + schema, via
> `api/setup.sh` — so a pull that adds requirements is picked up automatically),
> rebuilds the web, writes/refreshes the systemd unit, and restarts the service
> (whose startup also applies any new DB migrations). Idempotent — re-run it
> anytime. The numbered sections below document what it does, plus prereqs (§0),
> data migration (§1), the firewall (§3), tunnel access (§4), and backups (§5).

## 0. Prereqs (Debian/Ubuntu VPS)
- `sudo apt-get install -y python3.12 python3.12-venv libsqlcipher-dev pkg-config git`
  — the **`python3.12-venv`** package is required; without it `setup.sh` can't build the venv.
- Node 18+ and **pnpm**. If `pnpm` is missing even though Node is installed:
  `npm install -g pnpm` (or `corepack enable pnpm`).
- Decide where it lives and who runs it. The steps below assume `/opt/vellum` and a
  dedicated `vellum` user (cleanest). Running **as root under your home dir** also
  works — `start.sh` writes the unit with the user/paths it actually runs as.

## 1. First-time setup (once)
```bash
sudo mkdir -p /opt/vellum && sudo chown vellum:vellum /opt/vellum
sudo -u vellum git clone <your-repo-url> /opt/vellum
cd /opt/vellum/api
./setup.sh        # venv + deps + sqlcipher driver + key handling + schema
```
- **Brand-new data:** `setup.sh` generates `VELLUM_DB_KEY` and prints it — back it up.
- **Migrating existing data:** put your **existing** key into `api/.env` *before*
  running `setup.sh` (it never overwrites an existing key), and bring your
  encrypted db over (`python -m app.sync pull` against your backup remote, or
  `scp` `api/data/vellum.db`).

Fill `api/.env`: `LLM_*`, `EMBED_*`, `VELLUM_DB_KEY`, and (for backups)
`VELLUM_SYNC_REMOTE`. You own this file — `start.sh` never creates or edits it; it
only refuses to deploy if it's missing.

That's the whole one-time part. From here on, **§2 is every deploy**.

## 2. Deploy / redeploy (every time)
Default port is **18080**. If it's taken (check `ss -ltn | grep :18080`), pass a
free one — `start.sh` bakes it into the unit, so use the same port in the tunnel (§4).
```bash
cd /opt/vellum && git pull --ff-only
VELLUM_PORT=18090 ./deploy/start.sh
```
`start.sh` re-runs `api/setup.sh` (picking up any new Python deps), rebuilds the
web (`pnpm install && pnpm build`), writes `/etc/systemd/system/vellum.service`
(bound to `127.0.0.1`, auto-restart, boot-start, hardened), `daemon-reload`s,
enables, and restarts the service — then curls `/health`. The restart applies any
new DB migrations via the app's startup. Data in `api/data/` is never touched.

Lower-level controls when you don't need a full redeploy:
```bash
sudo systemctl restart vellum    # restart now
sudo systemctl status vellum     # is it running?
journalctl -u vellum -f          # live logs (Ctrl-C to stop)
```

## 3. Lock down the network (the "ACL")
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

## 4. Access from each PC (SSH tunnel)
```bash
# local 18888  ->  VPS 127.0.0.1:<VELLUM_PORT>   (remote = the port you deployed with)
ssh -N -L 18888:127.0.0.1:18090 <user>@<VPS_IP>
```
then open <http://localhost:18888>. Convenience: add a `~/.ssh/config` host +
a shell alias, or `autossh` / a login launch agent so it reconnects. (VS Code's
port-forwarding works too — forward the VPS port and open the localhost link.)

## 5. Encrypted backups (replaces the multi-device baton)
- One-time: create an empty **private** repo; set `VELLUM_SYNC_REMOTE` in `api/.env`.
- Cron for the `vellum` user (`crontab -e`):
  ```cron
  30 3 * * * /opt/vellum/deploy/backup.sh >> /tmp/vellum-backup.log 2>&1
  ```
  (`backup.sh` checkpoints + pushes the ciphertext db; override its location with
  `VELLUM_API_DIR=` if you didn't deploy to `/opt/vellum`.)
- Confirm the remote only ever holds ciphertext.

## 6. Verification checklist
- [ ] `sudo reboot` → service comes back (`systemctl status vellum`).
- [ ] `sudo systemctl kill vellum` (or kill the uvicorn PID) → systemd restarts it.
- [ ] Second PC via the tunnel: chat works, history loads.
- [ ] From another host: `curl http://<VPS_IP>:18080/health` is refused/times
      out (app is **not** public).
- [ ] `deploy/backup.sh` runs clean; the remote repo shows only the encrypted
      `vellum.db`.
