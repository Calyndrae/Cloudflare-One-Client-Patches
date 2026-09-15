#!/usr/bin/env python3
r"""
warp_fix.py - Fix Cloudflare WARP stuck on "Connecting" (26%) on Windows.

Root cause this targets: the device registration / tunnel config in
C:\ProgramData\Cloudflare\conf.json has expired ("valid_until" in the past)
and the WARP service fails to renew it, so every connect attempt cycles
through the fallback ports and never completes.  Re-registering the device
fixes it.  The script also has a service-restart fallback and a final
network diagnosis if nothing works.

Your settings are left alone.  The tunnel protocol (MASQUE / WireGuard) and
the WARP mode are read before the device is re-registered and put back
afterwards if re-registration reset them.  Nothing else is changed.

Usage:
    python warp_fix.py            (auto-prompts for admin via UAC)
    python warp_fix.py --no-pause (don't wait for Enter at the end)

Build a standalone self-elevating EXE (on a machine with Python):
    pip install pyinstaller
    pyinstaller --onefile --uac-admin --name WarpFix warp_fix.py
    -> dist\WarpFix.exe
"""

import ctypes
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

SERVICE = "CloudflareWARP"
CONF_JSON = r"C:\ProgramData\Cloudflare\conf.json"
CLI_CANDIDATES = [
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                 "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
]
WARP_EDGE_IP = "162.159.198.2"
API_HOST = "api.cloudflareclient.com"
TRACE_URL = "https://www.cloudflare.com/cdn-cgi/trace"
CONNECT_WAIT = 30          # seconds to wait for "Connected" after each attempt

# Tunnel protocols warp-cli understands, keyed by lowercase name so that
# whatever casing the CLI prints maps back onto a value it will accept.
PROTOCOLS = {"masque": "MASQUE", "wireguard": "WireGuard"}

# `warp-cli settings` reports the mode in CamelCase, but `warp-cli mode` only
# accepts the short form.  Anything not in here is left alone rather than
# guessed at - we never want to silently change the user's mode.
MODE_ALIASES = {
    "warp": "warp",
    "warponly": "warp",
    "warpwithdnsoverhttps": "warp+doh",
    "warp+doh": "warp+doh",
    "warpwithdnsovertls": "warp+dot",
    "warp+dot": "warp+dot",
    "dnsoverhttps": "doh",
    "doh": "doh",
    "dnsovertls": "dot",
    "dot": "dot",
    "proxyonly": "proxy",
    "proxy": "proxy",
    "tunnelonly": "tunnel_only",
    "tunnel_only": "tunnel_only",
}
NO_PAUSE = "--no-pause" in sys.argv
NO_ELEVATE = "--no-elevate" in sys.argv

LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "warp_fix.log")
_log_fh = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def log(msg=""):
    global _log_fh
    line = str(msg)
    print(line, flush=True)
    try:
        if _log_fh is None:
            _log_fh = open(LOG_PATH, "a", encoding="utf-8", errors="replace")
            _log_fh.write("\n===== %s =====\n" % dt.datetime.now().isoformat(timespec="seconds"))
        _log_fh.write(line + "\n")
        _log_fh.flush()
    except OSError:
        pass


def step(title):
    log()
    log("=" * 70)
    log(title)
    log("=" * 70)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Re-launch this script/exe with a UAC prompt. Returns only on failure."""
    if getattr(sys, "frozen", False):          # PyInstaller exe
        exe = sys.executable
        params = " ".join('"%s"' % a for a in sys.argv[1:] + ["--no-elevate"])
    else:
        exe = sys.executable
        params = " ".join('"%s"' % a for a in [os.path.abspath(sys.argv[0])] + sys.argv[1:] + ["--no-elevate"])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def run(cmd, timeout=60):
    """Run a command, return (returncode, combined output)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return -1, "(timed out after %ss)" % timeout
    except FileNotFoundError as e:
        return -1, "not found: %s" % e


def find_cli():
    for p in CLI_CANDIDATES:
        if os.path.isfile(p):
            return p
    # last resort: PATH
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, "warp-cli.exe")
        if os.path.isfile(p):
            return p
    return None


class Warp:
    def __init__(self, cli):
        self.cli = cli

    def cmd(self, *args, timeout=60):
        return run([self.cli, "--accept-tos", *args], timeout=timeout)

    def status(self):
        _, out = self.cmd("status", timeout=20)
        return out

    def is_connected(self, out=None):
        out = self.status() if out is None else out
        return re.search(r"Status update:\s*Connected\b", out) is not None

    def wait_connected(self, seconds=CONNECT_WAIT):
        deadline = time.time() + seconds
        last = ""
        while time.time() < deadline:
            out = self.status()
            first = out.splitlines()[0] if out else "(no output)"
            reason = ""
            m = re.search(r"Reason:\s*(.+)", out)
            if m:
                reason = " | " + m.group(1).strip()
            line = "  ... " + first + reason
            if line != last:
                log(line)
                last = line
            if self.is_connected(out):
                return True
            time.sleep(3)
        return False

    def registration_info(self):
        _, out = self.cmd("registration", "show", timeout=20)
        info = {"raw": out, "account_type": None, "license": None}
        m = re.search(r"Account type:\s*(\S+)", out)
        if m:
            info["account_type"] = m.group(1)
        m = re.search(r"License:\s*(\S+)", out)
        if m:
            info["license"] = m.group(1)
        return info

    # --- settings we must not change -------------------------------------- #
    def settings_text(self):
        _, out = self.cmd("settings", timeout=20)
        return out

    def tunnel_protocol(self):
        """Current tunnel protocol, or None if we cannot read it with
        confidence.  Only the names warp-cli accepts are ever returned, so we
        can never hand a garbage value back to `tunnel protocol set`."""
        rc, out = self.cmd("tunnel", "protocol", "get", timeout=20)
        if rc == 0:
            m = re.search(r"\b(MASQUE|WireGuard)\b", out, re.I)
            if m:
                return PROTOCOLS[m.group(1).lower()]
        m = re.search(r"protocol\s*[:=]\s*(MASQUE|WireGuard)\b",
                      self.settings_text(), re.I)
        if m:
            return PROTOCOLS[m.group(1).lower()]
        return None

    def set_tunnel_protocol(self, proto):
        canonical = PROTOCOLS.get(proto.lower())
        if not canonical:
            return False, "unrecognised protocol %r - left as-is" % proto
        rc, out = self.cmd("tunnel", "protocol", "set", canonical, timeout=30)
        return rc == 0, out

    def mode(self):
        """Current WARP mode as warp-cli spells it, or None if unknown."""
        m = re.search(r"^\s*Mode\s*[:=]\s*(\S+)", self.settings_text(), re.M)
        return m.group(1).strip(".,") if m else None

    def set_mode(self, mode):
        short = MODE_ALIASES.get(mode.lower().replace(" ", ""))
        if not short:
            return False, "unrecognised mode %r - left as-is" % mode
        rc, out = self.cmd("mode", short, timeout=30)
        return rc == 0, out

    def snapshot_settings(self):
        """Read back the settings re-registration is known to reset."""
        snap = {"protocol": self.tunnel_protocol(), "mode": self.mode()}
        log("Current tunnel protocol: %s" % (snap["protocol"] or "(unknown)"))
        log("Current WARP mode      : %s" % (snap["mode"] or "(unknown)"))
        return snap

    def restore_settings(self, snap):
        """Put protocol/mode back if re-registering changed them. Never
        switches the user onto a protocol or mode they did not pick."""
        want = snap.get("protocol")
        if want:
            now = self.tunnel_protocol()
            if now and now.lower() != want.lower():
                ok, out = self.set_tunnel_protocol(want)
                log("Restoring tunnel protocol %s -> %s : %s"
                    % (now, want, "OK" if ok else (out or "failed")))

        want = snap.get("mode")
        if want:
            now = self.mode()
            if now and now.lower() != want.lower():
                ok, out = self.set_mode(want)
                log("Restoring WARP mode %s -> %s : %s"
                    % (now, want, "OK" if ok else (out or "failed")))


# --------------------------------------------------------------------------- #
# service management
# --------------------------------------------------------------------------- #
def service_state():
    _, out = run(["sc", "query", SERVICE], timeout=20)
    m = re.search(r"STATE\s*:\s*\d+\s+(\w+)", out)
    if m:
        return m.group(1)
    if "1060" in out or "does not exist" in out.lower():
        return "MISSING"
    return "UNKNOWN"


def wait_service(state, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if service_state() == state:
            return True
        time.sleep(1)
    return False


def ensure_service_running():
    st = service_state()
    log("Service %s state: %s" % (SERVICE, st))
    if st == "MISSING":
        log("!! The CloudflareWARP service is not installed. Reinstall WARP from")
        log("   https://1.1.1.1/ and run this script again.")
        return False
    if st != "RUNNING":
        log("Starting service ...")
        run(["sc", "config", SERVICE, "start=", "auto"], timeout=20)
        run(["sc", "start", SERVICE], timeout=30)
        if not wait_service("RUNNING"):
            log("!! Could not start the service.")
            return False
        log("Service started.")
        time.sleep(3)
    return True


def restart_service():
    log("Stopping service ...")
    run(["sc", "stop", SERVICE], timeout=30)
    wait_service("STOPPED", 30)
    time.sleep(2)
    log("Starting service ...")
    run(["sc", "start", SERVICE], timeout=30)
    ok = wait_service("RUNNING", 30)
    time.sleep(4)
    return ok


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #
def conf_validity():
    """Return (valid_until_str, expired_bool_or_None)."""
    try:
        with open(CONF_JSON, "r", encoding="utf-8", errors="replace") as fh:
            conf = json.load(fh)
        vu = conf.get("valid_until")
        if not vu:
            return None, None
        ts = dt.datetime.fromisoformat(re.sub(r"(\.\d{6})\d*", r"\1", vu).replace("Z", "+00:00"))
        return vu, ts < dt.datetime.now(dt.timezone.utc)
    except Exception:
        return None, None


def tcp_ok(host, port=443, timeout=5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def trace_check():
    """Ask Cloudflare whether traffic is going through WARP. Returns dict or None."""
    try:
        req = urllib.request.Request(TRACE_URL, headers={"User-Agent": "warp_fix"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
        return dict(l.split("=", 1) for l in body.splitlines() if "=" in l)
    except Exception as e:
        log("  (trace check failed: %s)" % e)
        return None


def network_diagnosis(warp):
    step("Network diagnosis (WARP still not connecting)")
    log("TCP 443 to WARP edge %s : %s" % (WARP_EDGE_IP, "OK" if tcp_ok(WARP_EDGE_IP) else "BLOCKED"))
    log("TCP 443 to %-22s : %s" % (API_HOST, "OK" if tcp_ok(API_HOST) else "BLOCKED"))
    log("TCP 443 to 1.1.1.1              : %s" % ("OK" if tcp_ok("1.1.1.1") else "BLOCKED"))
    log()
    log("Last status:")
    for l in warp.status().splitlines():
        log("  " + l)
    log()
    proto = warp.tunnel_protocol()
    mode = warp.mode()
    log("Tunnel protocol: %s   |   Mode: %s"
        % (proto or "(unknown)", mode or "(unknown)"))
    log()
    log("Things to try next:")
    log("  * Connect to a different network (e.g. phone hotspot). If WARP works")
    log("    there, this network is blocking UDP/VPN traffic and no client-side")
    log("    fix will help.")
    log("  * Uninstall other VPN / proxy tools (Clash, v2ray, Radmin VPN, ...)")
    log("    and reboot - their filter drivers can block the WARP tunnel.")
    if proto:
        other = "WireGuard" if proto.lower() == "masque" else "MASQUE"
        log("  * Some networks pass one tunnel protocol and block the other. You")
        log("    are on %s; switching to %s in the WARP app (Settings >" % (proto, other))
        log("    Advanced > Connection options) may get you through. This tool")
        log("    deliberately does not change that setting for you.")
    log("  * Reinstall WARP from https://1.1.1.1/ and run this script again.")
    log("  * Full log: %s" % LOG_PATH)


# --------------------------------------------------------------------------- #
# fix attempts
# --------------------------------------------------------------------------- #
def attempt_plain_connect(warp):
    step("Step 1/3: plain connect")
    warp.cmd("connect")
    return warp.wait_connected(20)


def attempt_reregister(warp, snap):
    step("Step 2/3: re-register device (fixes expired registration)")
    info = warp.registration_info()
    acct = info["account_type"] or "unknown"
    lic = info["license"]
    log("Current account type: %s" % acct)
    if lic and acct.lower() != "free":
        log("Saving paid license key to re-apply: %s" % lic)
    else:
        lic = None

    warp.cmd("disconnect")
    time.sleep(1)
    rc, out = warp.cmd("registration", "delete")
    log("registration delete -> %s" % (out or rc))
    time.sleep(2)
    rc, out = warp.cmd("registration", "new", timeout=90)
    log("registration new    -> %s" % (out or rc))
    if rc != 0 or "Success" not in out:
        log("!! Registration failed. WARP's API may be unreachable from this network.")
        return False
    if lic:
        rc, out = warp.cmd("registration", "license", lic, timeout=60)
        log("re-apply license    -> %s" % (out or rc))
    # A fresh registration can come back on WARP's defaults - put the user's
    # own tunnel protocol and mode back rather than leaving ours in place.
    warp.restore_settings(snap)
    time.sleep(2)
    warp.cmd("connect")
    return warp.wait_connected()


def attempt_service_restart(warp):
    step("Step 3/3: restart the WARP service and reconnect")
    if not restart_service():
        log("!! Service did not come back up.")
        return False
    warp.cmd("connect")
    return warp.wait_connected()


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def finish(code):
    if _log_fh:
        _log_fh.close()
    if not NO_PAUSE:
        try:
            input("\nPress Enter to close ...")
        except EOFError:
            pass
    sys.exit(code)


def main():
    if os.name != "nt":
        print("This script is for Windows only.")
        return 1

    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    if not is_admin():
        if NO_ELEVATE:
            print("!! Not running as administrator and elevation was refused.")
            print("   Right-click -> 'Run as administrator' and try again.")
            return 1
        print("Requesting administrator rights (UAC prompt) ...")
        if relaunch_as_admin():
            return 0        # elevated copy takes over
        print("!! UAC elevation was cancelled or failed.")
        print("   Right-click -> 'Run as administrator' and try again.")
        return 1

    step("Cloudflare WARP fix  -  stuck on 'Connecting' / 26%")
    log("Log file: %s" % LOG_PATH)

    cli = find_cli()
    if not cli:
        log("!! warp-cli.exe not found. Install Cloudflare WARP from https://1.1.1.1/")
        return 1
    log("warp-cli: %s" % cli)
    warp = Warp(cli)

    if not ensure_service_running():
        return 1

    vu, expired = conf_validity()
    if vu:
        log("Registration valid_until: %s  -> %s" % (vu, "EXPIRED (this is the usual cause)" if expired else "still valid"))
    else:
        log("Registration config: not found / unreadable (will register fresh)")

    st = warp.status()
    log("Current status: %s" % (st.splitlines()[0] if st else "(no output)"))

    # Read the settings we must hand back unchanged before touching anything.
    snap = warp.snapshot_settings()

    connected = warp.is_connected(st)
    if connected:
        log("Already connected - will just verify below.")
    else:
        # If the registration is expired or missing, skip straight to re-register.
        if expired is not False:
            connected = attempt_reregister(warp, snap)
        else:
            connected = attempt_plain_connect(warp)
            if not connected:
                connected = attempt_reregister(warp, snap)
        if not connected:
            connected = attempt_service_restart(warp)
        if not connected:
            warp.restore_settings(snap)

    if not connected:
        network_diagnosis(warp)
        log()
        log("RESULT: NOT FIXED")
        return 2

    step("Verifying traffic goes through WARP")
    tr = trace_check()
    if tr:
        log("  warp=%s  colo=%s  loc=%s  ip=%s" % (tr.get("warp"), tr.get("colo"), tr.get("loc"), tr.get("ip")))
        if tr.get("warp") == "on":
            log()
            log("RESULT: FIXED - WARP is connected and routing traffic.")
            return 0
        log("  WARP reports connected but traffic is not going through the tunnel.")
        log("  Try: disconnect/reconnect from the app, or reboot.")
        return 3
    log("RESULT: WARP reports connected (could not reach the trace endpoint to double-check).")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except KeyboardInterrupt:
        rc = 130
    except Exception as e:      # never die silently in a console that will close
        log("!! Unexpected error: %r" % (e,))
        rc = 1
    finish(rc)
