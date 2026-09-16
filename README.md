# Cloudflare One Client Patches

**Repair tools for the Cloudflare WARP / Cloudflare One client on Windows.**
They fix the client without touching your settings — your tunnel protocol
(MASQUE or WireGuard), your mode and your WARP+ / Zero Trust subscription are
all left exactly as you had them, and a run that fails leaves your device no
worse off than it found it.

Anything that *does* change something else on your PC — switching tunnel
protocol, or clearing other VPN software out of the way — is asked first and
can be undone.

Right now there is one tool:

| Tool | What it fixes |
|---|---|
| [`warp_fix.py`](warp_fix.py) | WARP gets stuck saying **"Connecting…"** and the circle stops around **26%**, or reports **"Registration Missing"** |

When it *can't* fix something, it says so and tells you which side the problem
is on — this network, or this computer. See
[Read the UDP lines first](#-read-the-udp-lines-first).

---

## 😕 Is this your problem?

You open Cloudflare WARP, you flip the switch on, and then… nothing.

It just says **Connecting** forever. Sometimes it shows **26%**. It never says
**Connected**.

If that's you, this fix is for you. 🎉

It also covers two neighbours of that problem:

- WARP says **"Registration Missing"**, or the app suddenly asks you to set it
  up from scratch again, as if you had just installed it.
- You ran an older version of this tool, it said `NOT FIXED`, and afterwards
  WARP was in a *worse* state than before. Sorry about that — see
  [Registration Missing](#-help-warp-says-registration-missing) below.

---

## 🤔 Why does that happen?

Think of WARP like a bus pass. 🚌

Your computer gets a bus pass from Cloudflare so it's allowed on the secret bus
(the tunnel that keeps your internet private).

That bus pass has an **expiry date**. Normally WARP gets a fresh one all by
itself. But sometimes it forgets, the pass runs out, and the bus driver says
"nope". Your computer keeps knocking on the door forever — that's the stuck
"Connecting…".

**The fix:** throw the old pass away and ask for a brand new one. That's the
main thing this tool does. If that doesn't work, it restarts WARP's background
service and tries again.

**And it never walks off with your pass.** Asking for a new one has to be done
carefully: while WARP is busy knocking on that door it stops answering, and a
request sent at the wrong moment can throw the old pass away without getting a
new one. The tool makes WARP stop knocking *first*, retries anything that goes
unanswered, and if your computer still ends up with no pass at all it treats
getting one back as more important than anything else it was doing.

---

## 🚀 How to use it

You need **Windows**. That's it — you do **not** need to install Python
first, the tool does that for you.

### Step 1 — Download **one file: `RUN_ME.bat`**

👉 **[Click here to download `RUN_ME.bat`](https://raw.githubusercontent.com/Calyndrae/Cloudflare-One-Client-Patches/HEAD/RUN_ME.bat)** 👈

That link is the **only** file you need.

- If your browser starts the download straight away — great, it's in your
  **Downloads** folder.
- If your browser shows the text of the file instead of downloading it,
  press <kbd>Ctrl</kbd> + <kbd>S</kbd> to save it. Make sure the name stays
  **`RUN_ME.bat`** and *not* `RUN_ME.bat.txt`.
- Edge or Chrome may warn that the file "isn't commonly downloaded". Choose
  **Keep** → **Keep anyway**. (It's a small text file; you can open it in
  Notepad and read every line.)

> Prefer to grab everything? Click the green **Code** button at the top of this
> page → **Download ZIP** → right-click the ZIP → **Extract All…**. The file to
> run is still **`RUN_ME.bat`**.

### Step 2 — Double-click `RUN_ME.bat`

1. Windows pops up a blue-ish box asking
   **"Do you want to allow this app to make changes to your device?"**
   Click **Yes**. 👍
   (It has to ask, because fixing WARP means restarting a Windows service.)
2. A black window opens and starts typing things. **Just let it work.**

If Python isn't on your computer, the window will say *"Python is not
installed. Installing it now"* and do it for you. That part needs internet and
takes a couple of minutes. After that it runs the fix, which usually takes
less than a minute.

### Step 3 — Read the last line

When it's done, look near the bottom of the black window:

- ✅ **`RESULT: FIXED`** — yay! WARP works now. Open the app and check that it
  says **Connected**.
- ❌ **`RESULT: NOT FIXED`** — the tool couldn't do it. Don't worry, it printed
  a list of things to try. Have a look at
  [What if it didn't work?](#-what-if-it-didnt-work) below.

If it says `NOT FIXED`, it may then ask you one of two questions. Both change
something on your PC, which is exactly why they are questions — press Enter on
its own to say no, and nothing happens.

> `Clear them out of the way now? [y/N]`

You get this one when it found **other VPN or proxy software** holding the
tunnel open — Clash, v2ray, Radmin VPN and friends. Answering **`y`** stops
those programs, switches off their tunnel adapters and clears your system
proxy. See [Can I undo the cleanup?](#-can-i-undo-the-cleanup) — the short
answer is yes, completely.

> `Try the other tunnel protocol now? [y/N]`

WARP can tunnel two different ways (**MASQUE** and **WireGuard**) and some
networks allow one but block the other. Answering **`y`** tries the other one;
your own setting is put straight back if it doesn't connect either.

Then press **Enter** to close the window.

---

## 🧯 What if it didn't work?

Try these, in this order:

1. **Turn off other VPN apps.** Things like Clash, v2ray, Radmin VPN, Hamachi
   or another VPN can block WARP. Close them (or uninstall them), restart the
   computer, and run the tool again.

2. **Try a different internet connection.** Use your phone's hotspot 📱 instead
   of your normal Wi-Fi. If WARP works on the hotspot, your normal network
   (school Wi-Fi, some home routers) is blocking WARP, and nothing on your
   computer can fix that.

3. **Try the other tunnel protocol — your choice, not ours.** Some networks
   allow one and block the other. Answer **`y`** to the question the tool asks
   after a failed run, or switch by hand in the WARP app: **Settings →
   Advanced → Connection options**, between **MASQUE** and **WireGuard**. The
   tool never changes it unless you say yes.

4. **Reinstall WARP.** Uninstall the 1.1.1.1 / WARP app, download it again from
   **https://1.1.1.1/**, install it, then run the tool again.

5. **Show someone the log.** The tool writes down everything it did in a file.
   Press <kbd>Windows</kbd> + <kbd>R</kbd>, type `%TEMP%\warp_fix.log`, press
   Enter. That file is very handy if you ask someone for help.

### 🔎 Read the UDP lines first

Before that list, the tool prints something like this:

```
UDP reachability - this is the one that matters, WARP's tunnel is UDP:
  UDP 53   to 1.1.1.1         (any UDP at all?     ) : no reply
  UDP 443  to 162.159.198.2   (WARP edge, main port) : no reply
```

This is the single most useful thing in the whole report. WARP's tunnel only
travels over **UDP**, so `no reply` everywhere means you have found the
blocker — but *not yet* whose fault it is. Two completely different things
produce identical lines:

- the **network** is dropping UDP, or
- something on **this PC** is eating it before it ever reaches the wire.

**The one-minute test:** try WARP on your phone or another laptop on the same
Wi-Fi. If that works, the network is innocent and the problem is this
computer.

> TCP lines saying `OK` mean almost nothing here. WARP signs in over TCP but
> tunnels over UDP — and a TUN-mode proxy will happily carry the TCP while
> silently dropping the UDP, which is exactly how a local problem disguises
> itself as a network one.

### 🕵️ …then read the list above them

Just before the UDP block, the tool names what it found on this PC:

```
Things on this PC that can swallow the tunnel:
  !! VPN/proxy network adapter: Up  Clash  -  Wintun Userspace Tunnel
  !! VPN/proxy process running: Clash Verge.exe
  !! System-wide (WinHTTP) proxy is set: 127.0.0.1:7890
```

It checks, read-only and changing nothing: TUN/TAP adapters belonging to other
VPNs and proxies, whether WARP's own adapter is present and up, running
VPN/proxy processes, the Windows and WinHTTP proxy settings, and whether
Windows Firewall blocks outbound by default.

**Closing the window is not enough.** Clash, v2ray, Netch, Proxifier, Radmin
VPN and friends install a filter driver that keeps working after the app looks
shut. Exit from the tray or uninstall, **then reboot**, then try WARP again.

Antivirus with its own firewall (McAfee — often preinstalled on new laptops —
Norton, 360, 火绒) can do the same thing, and won't show up as an adapter.

### 🧹 Or let it clear them for you

Answer **`y`** to `Clear them out of the way now?`, or run
`RUN_ME.bat --clean-tun` yourself. It then:

- stops the proxy processes it found,
- switches off their tunnel adapters,
- clears the Windows and WinHTTP proxy settings,
- flushes the DNS cache,

and carries on with the repair on a clear machine.

**What it deliberately won't touch:** corporate VPN clients — AnyConnect,
FortiClient, EasyConnect, GlobalProtect, Sangfor. They're listed in the report
so you can see them, but switching one off can cut you out of your work
network, and that's not this tool's decision to make. Turn those off yourself
if you want them tested.

**It is not a *complete* clean, and it doesn't claim to be.** These programs
install a driver that sits below the network stack, and only uninstalling the
program removes it. Switching off the adapter stops it carrying your traffic —
which is what WARP needs — but for a truly clean machine, uninstall the app and
reboot.

### ↩️ Can I undo the cleanup?

Yes — all of it.

```powershell
RUN_ME.bat --restore-tun
```

Everything is written to `C:\ProgramData\warp_fix\clean_tun_undo.json`
*before* anything changes, so it can be put back even if the tool is killed
half way. Adapters are re-enabled and your proxy settings restored exactly as
they were.

Two things to know:

- **Programs it stopped are not restarted.** Launch them yourself.
- **If the cleanup takes your PC off the internet, it undoes itself on the
  spot** without waiting to be asked, and tells you it did.

---

## 🆘 Help, WARP says "Registration Missing"

Or: the app is showing its first-run screen again, asking you to choose between
two cards.

Your computer has lost its WARP registration. It cannot connect until it has a
new one. Nothing is broken and nothing is lost — a registration is free and
takes seconds to replace.

**In the app**, you'll be asked *"What do you want to use WARP for?"*:

| Card | Pick it when |
|---|---|
| **1.1.1.1 / Private browsing** (left) | **This is the one you want** unless you know otherwise. No account, no login — click *Accept terms and continue* and WARP registers itself. |
| **Cloudflare One Client** (right) | Only if your **workplace or school** gave you a Cloudflare One / Zero Trust **team name**. Without one you cannot get past this screen. |

Choosing the right-hand card by mistake just asks for a team name you don't
have — go back and pick the left one.

**Or from a terminal**, open Command Prompt **as administrator** and run:

```powershell
"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe" --accept-tos registration new
```

Then run `RUN_ME.bat` again. Recent versions detect this state at startup and
repair it for you; they also refuse to finish a run that would leave you
without a registration.

---

## ❓ Questions people ask

**Is this safe? Will it break my computer?**
It only touches Cloudflare WARP — it restarts WARP's background service and
asks Cloudflare for a new registration. It doesn't touch your files, your
games, or anything else. All of the code is right here in
[`warp_fix.py`](warp_fix.py) and [`RUN_ME.bat`](RUN_ME.bat) so anyone can read
it.

**Will it change my WARP settings?**
Not on its own. It reads your tunnel protocol (MASQUE / WireGuard) and your
mode before it starts, and if re-registering resets them it puts your own
values straight back. The **one** exception is the protocol question it asks
you after a failed run — and even then, if the other protocol doesn't connect,
yours is restored before the tool exits.

**Will `--clean-tun` break my proxy setup?**
It switches things off; it doesn't uninstall or delete anything. Your config
files, subscriptions and rules are untouched. `--restore-tun` re-enables the
adapters and restores the proxy settings; the programs themselves you just
launch again.

**The app is asking me to choose between "Private browsing" and "Cloudflare
One Client". Which one?**
The left one (**1.1.1.1 / Private browsing**), unless your workplace or school
gave you a Cloudflare One team name. See
[Registration Missing](#-help-warp-says-registration-missing).

**What does it install?**
Python, and only if you don't already have it. It's fetched with
[winget](https://learn.microsoft.com/windows/package-manager/) if your Windows
has it, otherwise straight from **python.org**. Nothing else is installed.

**Why does it ask for administrator permission?**
Because WARP runs as a Windows *service*, and only an administrator is allowed
to stop and start services. If you click **No**, the tool politely stops and
does nothing.

**Will I lose my WARP+ / Zero Trust subscription?**
No. Before it deletes the old registration, the tool copies your licence key
down, and it puts it back afterwards.

**Do I have to do this every time?**
No. It's a one-time repair. If it comes back weeks later, just run it again.

**I'm on a Mac / Linux.**
Sorry — this one is Windows-only. It will tell you so and stop.

---

## 🛠️ For the nerds

<details>
<summary>Click here for the technical details</summary>

### Files

| File | Purpose |
|---|---|
| `RUN_ME.bat` | The download target. Self-elevates via UAC (passing your arguments through), bootstraps Python (winget, then the python.org installer), fetches `warp_fix.py` if it isn't alongside, then runs it with `--no-elevate --no-pause`. On exit code `2` it offers one re-run with `--try-protocols`. |
| `warp_fix.py` | The fix itself. Runs standalone under any Python 3.8+ on Windows. |
| `build_exe.bat` | Optional. Installs Python + PyInstaller if needed and builds `dist\WarpFix.exe`. |

### What it actually does

The usual root cause is that the device registration in
`C:\ProgramData\Cloudflare\conf.json` has a `valid_until` timestamp in the
past, and the WARP service fails to renew it. Every connect attempt then cycles
through the fallback ports and never completes the handshake — the UI shows
"Connecting" and parks at ~26%.

The script runs this ladder and stops at the first thing that works:

| Step | Action |
|---|---|
| 0 | Self-elevate via UAC, locate `warp-cli.exe`, make sure the `CloudflareWARP` service is running, read `valid_until` from `conf.json`, check whether a registration exists at all, **snapshot the current tunnel protocol and mode** |
| 1 | `warp-cli connect` (skipped if the registration is expired or missing) |
| 2 | **quiesce the daemon**, then `registration delete` (skipped when there is nothing to delete) → `registration new` → re-apply saved licence → **restore the snapshotted protocol/mode if re-registration reset them** → `connect` |
| 3 | `sc stop` / `sc start CloudflareWARP`, re-register if the restart came up unregistered, then reconnect |
| ½ | **Only with `--clean-tun`:** scan for other VPN/proxy tunnels, write the undo journal, stop the processes, disable their adapters, clear the system proxy — self-restoring if the machine loses connectivity |
| 3½ | **Only with `--try-protocols`:** switch MASQUE ⇄ WireGuard, try to connect, and put the original back if it doesn't help |
| ✔ | Verify against `https://www.cloudflare.com/cdn-cgi/trace` that `warp=on` |
| ⛑ | Whatever happened above, if the device ends up with no registration, get one back before exiting |

#### Why the daemon gets quiesced first

`warp-cli` reaches the WARP service over a local IPC socket, and while the
service is grinding through a connect attempt it stops answering. Commands sent
into that window return:

```
Error communicating with daemon: The IPC call hit a timeout and could not be processed
```

That is *not* the same as "the command didn't happen" — `registration delete`
can land anyway and the reply never come back, which is how a machine ends up
with **no registration at all**, a worse state than the stuck connect it
started in. So: nothing touches registration until `disconnect` has been issued
and `warp-cli status` confirms the daemon actually left `Connecting`; IPC
timeouts are retried with backoff (and a service restart if that isn't enough);
success is judged by re-reading `registration show`, not by string-matching the
CLI's output; and `ensure_registration()` runs on every exit path.

**Settings are never changed on your behalf**, unless you pass
`--try-protocols` (or answer `y` to the launcher's prompt), which is restored
on failure anyway. Otherwise the only time the script writes a protocol or mode
is to put back the value it read from your machine before it started. Mode
strings it doesn't recognise are left untouched rather than guessed at.

#### Diagnosis

If nothing connects, the script reports:

- **TCP/443** to the WARP edge (`162.159.198.2`), `api.cloudflareclient.com`
  and `1.1.1.1` — the control plane only.
- **UDP**, which is what the tunnel actually needs, and the part the first
  version of this tool never tested. It sends a real DNS query to `1.1.1.1:53`,
  and QUIC packets carrying version `0x0a0a0a0a` to `1.1.1.1:443` and to the
  WARP edge on 443/500/1701/4500 — the exact port ladder a stuck client cycles
  through. No server implements that version, so [RFC 9000][rfc9000] obliges it
  to answer with a Version Negotiation packet; any reply proves UDP got there
  and back without the script having to speak the rest of QUIC.
- **A read-only scan of this machine**, because "the network drops UDP" and "a
  filter driver here drops UDP" are indistinguishable from the outside:
  TUN/TAP adapters belonging to other VPNs and proxies (`Get-NetAdapter`,
  falling back to `netsh interface show interface`), whether WARP's own adapter
  is present and up, running VPN/proxy processes (`tasklist`), the WinHTTP and
  WinINET proxy settings, and whether Windows Firewall blocks outbound by
  default. It names things; it never disables or removes any of them.
- A verdict drawn from those: `edge-ok` (network is fine, look at this PC),
  `edge-filtered` (UDP works, WARP specifically doesn't) or `udp-blocked` (no
  UDP at all — either end of the wire, which the local scan and a second device
  on the same Wi-Fi disambiguate).
- Current protocol, mode, whether a registration exists, and the final
  `warp-cli status`.

[rfc9000]: https://www.rfc-editor.org/rfc/rfc9000#section-6

### Command line

```powershell
python warp_fix.py                 # auto-prompts for admin via UAC
python warp_fix.py --no-pause      # don't wait for Enter at the end (for scripts)
python warp_fix.py --no-elevate    # already elevated; don't try to re-launch
python warp_fix.py --try-protocols # also try the other tunnel protocol, and
                                   # put yours back if it doesn't connect
python warp_fix.py --clean-tun     # stop other VPN/proxy tunnels first
python warp_fix.py --restore-tun   # undo the above and exit
```

`RUN_ME.bat` forwards its own arguments, so `RUN_ME.bat --clean-tun` and
`RUN_ME.bat --restore-tun` work too, and survive the UAC re-launch.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Connected (fixed, or already fine) |
| `1` | Setup problem — not admin, no `warp-cli.exe`, service missing/won't start |
| `2` | Not fixed; diagnosis printed. The device is still registered |
| `3` | WARP says connected but the trace check shows traffic isn't in the tunnel |
| `4` | Not fixed **and** the device has no registration that could be restored — Cloudflare's API was unreachable. See [Registration Missing](#-help-warp-says-registration-missing) |
| `5` | Not fixed, but other VPN / proxy software was found in the way — re-runnable with `--clean-tun`. `RUN_ME.bat` reads this code to decide what to offer |
| `130` | You pressed Ctrl+C |

### Build a standalone EXE

Double-click **`build_exe.bat`** — it installs Python and PyInstaller if they
are missing. Or by hand:

```powershell
pip install pyinstaller
pyinstaller --onefile --uac-admin --name WarpFix warp_fix.py
```

The result is `dist\WarpFix.exe`, which self-elevates and needs no Python on
the target machine.

### Log

Everything printed is also appended to `%TEMP%\warp_fix.log`.

</details>

---

## 📄 Licence

MIT — see [LICENSE](LICENSE). Use it, change it, share it.

*Not affiliated with Cloudflare. "Cloudflare" and "WARP" belong to Cloudflare, Inc.*
