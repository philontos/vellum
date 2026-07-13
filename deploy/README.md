# Vellum — VPS deploy runbook

Single-user backend + built web. It is **localhost-only by default** and can
instead bind to an explicit private interface such as WireGuard. It never needs
to bind the public interface, use a domain, or require ICP filing.

> **Every deploy is one command.** After the one-time setup (§1), you pull the
> code yourself and run:
> ```bash
> git pull --ff-only
> VELLUM_PORT=18090 ./deploy/start.sh   # drop VELLUM_PORT= to use the default 18080
> # WireGuard-only alternative:
> VELLUM_HOST=10.10.0.1 VELLUM_PORT=18090 ./deploy/start.sh
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
# Or bind only the WireGuard interface:
VELLUM_HOST=10.10.0.1 VELLUM_PORT=18090 ./deploy/start.sh
```
`start.sh` re-runs `api/setup.sh` (picking up any new Python deps), rebuilds the
web (`pnpm install && pnpm build`), writes `/etc/systemd/system/vellum.service`,
`daemon-reload`s, enables, and restarts the service — then curls `/health` on the
configured host. `VELLUM_HOST` defaults to `127.0.0.1`; set it to the exact
private-interface address, never `0.0.0.0`, for direct private-network access.
The restart applies any new DB migrations via the app's startup. Data in
`api/data/` is never touched.

Lower-level controls when you don't need a full redeploy:
```bash
sudo systemctl restart vellum    # restart now
sudo systemctl status vellum     # is it running?
journalctl -u vellum -f          # live logs (Ctrl-C to stop)
```

## 3. Lock down the network (the "ACL")
- The default binds `127.0.0.1` and is reached through an SSH tunnel.
- For WireGuard-only access, bind the exact interface address, for example
  `VELLUM_HOST=10.10.0.1`. Do not use `0.0.0.0`.
- After direct WireGuard access is verified, restrict the application port by
  ingress interface. Adapt the interface, addresses, and ports to the host:
  ```bash
  sudo ufw default deny incoming
  sudo ufw allow 22/tcp
  sudo ufw allow 51820/udp
  sudo ufw allow in on wg0 to 10.10.0.1 port 18090 proto tcp
  sudo ufw enable
  ```
  (If your provider has a cloud security group, do not add the Vellum TCP port;
  only the public WireGuard UDP port needs to reach `wg0`.)
- Optional tighter ACL: restrict SSH source to your usual IP ranges.

## 4. Access from each PC

With WireGuard active on the PC and Vellum bound to `10.10.0.1`, open
<http://10.10.0.1:18090> directly.

For the default localhost-only deployment, use an SSH tunnel:

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
- [ ] Each intended WireGuard peer (or second PC via SSH tunnel): chat works and
      history loads.
- [ ] From outside WireGuard: `curl http://<VPS_PUBLIC_IP>:<VELLUM_PORT>/health`
      is refused/times out (app is **not** public).
- [ ] `deploy/backup.sh` runs clean; the remote repo shows only the encrypted
      `vellum.db`.
