#!/usr/bin/env python3
r"""
warp_fix.py - Fix Cloudflare WARP stuck on "Connecting" (26%) on Windows.

Root cause this targets: the device registration / tunnel config in
C:\ProgramData\Cloudflare\conf.json has expired ("valid_until" in the past)
and the WARP service fails to renew it, so every connect attempt cycles
through the fallback ports and never completes.  Re-registering the device
fixes it.  The script also has a service-restart fallback and a final
network diagnosis if nothing works.

The other failure this handles is the one the first version of this script
could cause: warp-cli talks to the WARP service over a local IPC socket, and
while the service is grinding through a connect attempt it stops answering.
Registration commands sent into that window come back with "The IPC call hit a
timeout" *after* they have already half-applied, which can leave the device
with no registration at all - a worse problem than the one it came here with.
So the daemon is always quiesced before registration is touched, those calls
are retried, and a device that ends up unregistered is re-registered before
the script gives up.

Your settings are left alone.  The tunnel protocol (MASQUE / WireGuard) and
the WARP mode are read before the device is re-registered and put back
afterwards if re-registration reset them.  Nothing else is changed unless you
pass --try-protocols.

Usage:
    python warp_fix.py                 (auto-prompts for admin via UAC)
    python warp_fix.py --no-pause      (don't wait for Enter at the end)
    python warp_fix.py --try-protocols (also try the other tunnel protocol,
                                        and put yours back if it doesn't help)

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
QUIESCE_WAIT = 25          # seconds to wait for the daemon to leave "Connecting"

# warp-cli reaches the WARP service over a local IPC socket.  These are what it
# prints when the service is too busy connecting to answer - the command has
# not necessarily failed, it just never got a reply, so it is worth retrying
# once the daemon is idle rather than treating it as a hard error.
IPC_BUSY_RE = re.compile(r"IPC call hit a timeout|Error communicating with daemon",
                         re.I)

# Sent as one UDP datagram each in the final diagnosis.  WARP's tunnel is UDP
# only, so TCP/443 succeeding says nothing useful; these say everything.
# Cloudflare serves MASQUE (QUIC) on 443 and falls back to 500/1701/4500, which
# is exactly the port ladder a stuck client cycles through, so a QUIC probe on
# each of them mirrors what the client itself is attempting.
UDP_PROBES = [
    ("1.1.1.1", 53, "dns", "any UDP at all?"),
    ("1.1.1.1", 443, "quic", "UDP/443 in general"),
    (WARP_EDGE_IP, 443, "quic", "WARP edge, main port"),
    (WARP_EDGE_IP, 500, "quic", "WARP edge, fallback"),
    (WARP_EDGE_IP, 1701, "quic", "WARP edge, fallback"),
    (WARP_EDGE_IP, 4500, "quic", "WARP edge, fallback"),
]

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
TRY_PROTOCOLS = "--try-protocols" in sys.argv

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

    @staticmethod
    def ipc_busy(out):
        """Did the service fail to answer, rather than answer with a failure?"""
        return bool(out) and IPC_BUSY_RE.search(out) is not None

    def cmd_retry(self, *args, attempts=3, timeout=60, settle=4):
        """cmd(), but retried while the service is too busy to reply.

        Only IPC timeouts are retried - a real error from the service is
        returned as-is on the first try.  Between attempts we ask WARP to stop
        connecting, because the connect loop is what is monopolising it."""
        rc, out = -1, ""
        for attempt in range(1, attempts + 1):
            rc, out = self.cmd(*args, timeout=timeout)
            if not self.ipc_busy(out):
                return rc, out
            if attempt < attempts:
                log("   (WARP service busy - stopping the connect attempt and "
                    "retrying '%s' in %ss)" % (" ".join(args), settle))
                self.cmd("disconnect", timeout=15)
                time.sleep(settle)
                settle *= 2
        return rc, out

    def status(self):
        _, out = self.cmd("status", timeout=20)
        return out

    def state(self, out=None):
        """The one-word state WARP reports: Connected / Connecting /
        Disconnected / Unable / None if it will not say."""
        out = self.status() if out is None else out
        m = re.search(r"Status update:\s*(\w+)", out or "")
        return m.group(1) if m else None

    def quiesce(self, seconds=QUIESCE_WAIT):
        """Stop WARP connecting and wait until it has actually stopped.

        This is the important one.  A registration command issued while the
        daemon is mid-connect gets no reply, and warp-cli reporting an IPC
        timeout does not mean the daemon ignored it - `registration delete` can
        land anyway and leave the device unregistered.  Nothing touches
        registration until this returns True."""
        self.cmd("disconnect", timeout=20)
        deadline = time.time() + seconds
        while time.time() < deadline:
            st = self.state()
            if st and st.lower() != "connecting":
                return True
            time.sleep(2)
        return False

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

    def registration_present(self):
        """True / False, or None when the service will not tell us.

        None is treated as "leave it alone" everywhere: registering a device
        that already has a registration is its own kind of mess, so we only act
        on a definite no."""
        rc, out = self.cmd("registration", "show", timeout=20)
        if re.search(r"Registration Missing|Missing Registration|"
                     r"not registered|No registration", out or "", re.I):
            return False
        if rc == 0 and re.search(r"Device ID|Public Key|Account ID|"
                                 r"Account type|Registration ID", out or "", re.I):
            return True
        if re.search(r"Registration Missing", self.status() or "", re.I):
            return False
        return None

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
        """Current WARP mode as warp-cli spells it, or None if unknown.

        How `warp-cli settings` labels the mode has moved around between
        releases, so try the spellings we have seen.  Failing to read it costs
        nothing: an unknown mode is never written back."""
        text = self.settings_text()
        for pat in (r"^\s*Mode\s*[:=]\s*(\S+)",
                    r"^\s*WARP mode\s*[:=]\s*(\S+)",
                    r"^\s*Tunnel mode\s*[:=]\s*(\S+)"):
            m = re.search(pat, text, re.M | re.I)
            if m:
                return m.group(1).strip(".,")
        return None

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


def udp_probe(host, port, kind, timeout=4):
    """Send one UDP datagram that a healthy server is obliged to answer.

    "dns"  - a real DNS query for cloudflare.com; a reply carrying our
             transaction id means UDP got out and back.
    "quic" - a QUIC long header carrying version 0x0a0a0a0a, which no server
             implements.  RFC 9000 requires the server to answer with a
             Version Negotiation packet, so we learn whether UDP reaches the
             port without having to speak the rest of QUIC.  The datagram is
             padded to 1200 bytes because servers ignore shorter ones.

    Returns True (answered), False (silence) or None (the send itself failed).
    """
    if kind == "dns":
        txid = os.urandom(2)
        payload = (txid + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                   + b"\x0acloudflare\x03com\x00\x00\x01\x00\x01")
        expect = txid
    else:
        dcid, scid = os.urandom(8), os.urandom(8)
        payload = (b"\xc0\x0a\x0a\x0a\x0a"
                   + bytes([len(dcid)]) + dcid + bytes([len(scid)]) + scid)
        payload += b"\x00" * (1200 - len(payload))
        expect = None
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(payload, (host, port))
        data, _ = sock.recvfrom(2048)
        return expect is None or data[:2] == expect
    except socket.timeout:
        return False
    except OSError:
        return None
    finally:
        if sock is not None:
            sock.close()


def udp_diagnosis():
    """Probe the ports WARP's tunnel actually needs. Returns a verdict key."""
    log("UDP reachability - this is the one that matters, WARP's tunnel is UDP:")
    results = []
    for host, port, kind, note in UDP_PROBES:
        answered = udp_probe(host, port, kind)
        word = {True: "reply", False: "no reply",
                None: "no route / refused"}[answered]
        log("  UDP %-4s to %-15s (%-20s) : %s" % (port, host, note, word))
        results.append((host, port, answered))

    edge_ok = any(a for h, _, a in results if h == WARP_EDGE_IP)
    quic_ok = any(a for h, p, a in results if p != 53)
    dns_ok = any(a for _, p, a in results if p == 53)

    log()
    if edge_ok:
        log("  -> UDP does reach Cloudflare's WARP edge, so this network is not")
        log("     what is blocking the tunnel. Suspect something on this PC:")
        log("     another VPN's filter driver, or a broken registration.")
        return "edge-ok"
    if quic_ok or dns_ok:
        log("  -> UDP leaves this network, but nothing comes back from the WARP")
        log("     edge. Something here is filtering VPN traffic specifically")
        log("     (school / office / hotel networks and some ISPs do this).")
        return "edge-filtered"
    log("  -> No UDP reply from anywhere, not even a plain DNS query. This")
    log("     network blocks outbound UDP, and WARP's tunnel is UDP only, so")
    log("     no setting on this computer can get through it.")
    return "udp-blocked"


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
    log("TCP 443 - the control plane. WARP signs in over this, but the tunnel")
    log("does not use it, so an OK here does not mean the tunnel can work:")
    log("  TCP 443 to WARP edge %s : %s" % (WARP_EDGE_IP, "OK" if tcp_ok(WARP_EDGE_IP) else "BLOCKED"))
    log("  TCP 443 to %-22s : %s" % (API_HOST, "OK" if tcp_ok(API_HOST) else "BLOCKED"))
    log("  TCP 443 to 1.1.1.1              : %s" % ("OK" if tcp_ok("1.1.1.1") else "BLOCKED"))
    log()
    verdict = udp_diagnosis()
    log()
    log("Last status:")
    for l in warp.status().splitlines():
        log("  " + l)
    log()
    proto = warp.tunnel_protocol()
    mode = warp.mode()
    registered = warp.registration_present()
    log("Tunnel protocol: %s   |   Mode: %s   |   Registered: %s"
        % (proto or "(unknown)", mode or "(unknown)",
           {True: "yes", False: "NO", None: "(unknown)"}[registered]))
    log()
    log("Things to try next:")

    if verdict == "udp-blocked":
        log("  * THIS IS THE BLOCKER: the network drops outbound UDP. Move to a")
        log("    different one - a phone hotspot is the quickest test. If WARP")
        log("    connects there, nothing was ever wrong with this computer.")
        log("  * If it is your own router, look for a UDP/QUIC or 'VPN")
        log("    passthrough' setting and allow UDP out on 443 and 2408.")
    elif verdict == "edge-filtered":
        log("  * THIS IS THE BLOCKER: UDP works, but not to Cloudflare's WARP")
        log("    edge. That is deliberate filtering by whoever runs this")
        log("    network. A phone hotspot will confirm it in under a minute.")
    else:
        log("  * Uninstall other VPN / proxy tools (Clash, v2ray, Radmin VPN,")
        log("    ...) and reboot - their filter drivers can block the tunnel")
        log("    even while they look switched off.")
        log("  * Connect to a different network (e.g. phone hotspot) to rule the")
        log("    network in or out.")

    if proto:
        other = "WireGuard" if proto.lower() == "masque" else "MASQUE"
        log("  * Some networks pass one tunnel protocol and block the other. You")
        log("    are on %s. Re-run this tool with --try-protocols to let it try" % proto)
        log("    %s and put %s straight back if that does not help, or switch" % (other, proto))
        log("    by hand in the app: Settings > Advanced > Connection options.")
        log("    Without that flag the tool never touches this setting.")
    if registered is False:
        log("  * This device currently has NO WARP registration, so the app will")
        log("    show its first-run screen. Pick the LEFT card (1.1.1.1 /")
        log("    private browsing) unless your workplace or school gave you a")
        log("    Cloudflare One team name - the right-hand card asks for that")
        log("    team login and cannot be used without one.")
    log("  * Reinstall WARP from https://1.1.1.1/ and run this script again.")
    log("  * Full log: %s" % LOG_PATH)


# --------------------------------------------------------------------------- #
# fix attempts
# --------------------------------------------------------------------------- #
def attempt_plain_connect(warp):
    step("Step 1/3: plain connect")
    warp.cmd("connect")
    return warp.wait_connected(20)


def register_new(warp, timeout=90):
    """`registration new`, falling back to the older CLI's `register`."""
    rc, out = warp.cmd_retry("registration", "new", timeout=timeout)
    if re.search(r"unrecognized subcommand|unexpected argument|invalid subcommand",
                 out or "", re.I):
        rc, out = warp.cmd_retry("register", timeout=timeout)
    return rc, out


def ensure_registration(warp):
    """Never hand the machine back in a worse state than we found it.

    A registration command that the service never acknowledged can still have
    landed, so a run that fails can leave the device with no registration at
    all.  WARP then reports "Registration Missing" and the app falls back to
    its first-run screen - a worse problem than the stuck connect this tool
    came to fix.  So we try harder for a registration than for the connection
    itself, and say exactly how to get one back if we cannot."""
    if warp.registration_present() is not False:
        return True
    if getattr(warp, "repair_failed", False):
        log("(Still unregistered - see the repair section above.)")
        return False

    step("Repair: this device has been left without a WARP registration")
    log("Nothing can connect without one, so this gets fixed before we give up.")
    for attempt in (1, 2):
        warp.quiesce()
        rc, out = register_new(warp)
        log("registration new -> %s" % (out or rc))
        if warp.registration_present() is not False:
            log("Registration restored.")
            return True
        if attempt == 1:
            log("Restarting the WARP service and trying once more ...")
            restart_service()

    log("!! Could not register this device again - Cloudflare's API is not")
    log("   reachable from this network.")
    log("   Once you are on a network that works, either open the WARP app and")
    log("   answer its first-run screen, or run this one line as administrator:")
    log('     "%s" --accept-tos registration new' % warp.cli)
    warp.repair_failed = True
    return False


def attempt_reregister(warp, snap, delete_first=True):
    step("Step 2/3: re-register device (fixes an expired or missing registration)")

    # The service stops answering while it is grinding through a connect
    # attempt, and a registration command sent into that window can half-apply
    # - which is how a device ends up unregistered. Stop the loop first.
    if not warp.quiesce():
        log("WARP is still stuck in its connect loop; restarting the service to")
        log("get its attention before touching the registration.")
        restart_service()
        warp.quiesce()

    info = warp.registration_info()
    acct = info["account_type"] or "unknown"
    lic = info["license"]
    log("Current account type: %s" % acct)
    if lic and acct.lower() != "free":
        log("Saving paid license key to re-apply: %s" % lic)
    else:
        lic = None

    if delete_first:
        rc, out = warp.cmd_retry("registration", "delete")
        log("registration delete -> %s" % (out or rc))
        time.sleep(2)

    rc, out = register_new(warp)
    log("registration new    -> %s" % (out or rc))
    if warp.registration_present() is False:
        log("!! Registration failed. WARP's API may be unreachable from this network.")
        return False
    if lic:
        rc, out = warp.cmd_retry("registration", "license", lic, timeout=60)
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
    # A restart on a device whose registration went missing will just fail
    # again with "Registration Missing due to: Daemon Startup", so get one
    # back first.
    ensure_registration(warp)
    warp.cmd("connect")
    return warp.wait_connected()


def attempt_other_protocol(warp, snap):
    """Only ever runs with --try-protocols, and puts the user's choice back."""
    step("Extra step: try the other tunnel protocol (--try-protocols)")
    current = warp.tunnel_protocol()
    if not current:
        log("Cannot read the current tunnel protocol, so it will not be changed.")
        return False
    other = "WireGuard" if current.lower() == "masque" else "MASQUE"
    log("Some networks pass one protocol and block the other.")
    log("Switching %s -> %s. If it does not connect, %s goes straight back."
        % (current, other, current))

    warp.quiesce()
    ok, out = warp.set_tunnel_protocol(other)
    if not ok:
        log("Could not switch protocol: %s" % (out or "failed"))
        return False

    warp.cmd("connect")
    if warp.wait_connected():
        log("Connected on %s - leaving it there." % other)
        log("Change it back any time in Settings > Advanced > Connection options.")
        snap["protocol"] = other      # this one was asked for, so keep it
        return True

    log("%s did not connect either - restoring %s." % (other, current))
    warp.quiesce()
    warp.set_tunnel_protocol(current)
    return False


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

    registered = warp.registration_present()
    if registered is False:
        log("Registration: MISSING - this device is not registered with WARP.")
    elif registered:
        log("Registration: present")

    connected = warp.is_connected(st)
    if connected:
        log("Already connected - will just verify below.")
    else:
        if registered is False:
            # Nothing to delete, and deleting nothing errors - register fresh.
            connected = attempt_reregister(warp, snap, delete_first=False)
        elif expired is not False:
            # Expired or unreadable registration: go straight to re-registering.
            connected = attempt_reregister(warp, snap)
        else:
            connected = attempt_plain_connect(warp)
            if not connected:
                connected = attempt_reregister(warp, snap)
        if not connected:
            connected = attempt_service_restart(warp)
        if not connected and TRY_PROTOCOLS:
            connected = attempt_other_protocol(warp, snap)
        if not connected:
            warp.restore_settings(snap)
            # Whatever else failed, do not walk away from an unregistered device.
            ensure_registration(warp)

    if not connected:
        network_diagnosis(warp)
        log()
        if warp.registration_present() is False:
            log("RESULT: NOT FIXED - and this device has no WARP registration.")
            log("        See the 'Repair' section above before anything else.")
            return 4
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
