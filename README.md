# Cloudflare One Client Patches

**Repair tools for the Cloudflare WARP / Cloudflare One client on Windows.**
They fix the client without touching your settings — your tunnel protocol
(MASQUE or WireGuard), your mode and your WARP+ / Zero Trust subscription are
all left exactly as you had them.

Right now there is one tool:

| Tool | What it fixes |
|---|---|
| [`warp_fix.py`](warp_fix.py) | WARP gets stuck saying **"Connecting…"** and the circle stops around **26%** |

---

## 😕 Is this your problem?

You open Cloudflare WARP, you flip the switch on, and then… nothing.

It just says **Connecting** forever. Sometimes it shows **26%**. It never says
**Connected**.

If that's you, this fix is for you. 🎉

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
   allow one and block the other. In the WARP app go to **Settings →
   Advanced → Connection options** and switch between **MASQUE** and
   **WireGuard**. The tool tells you which one you're on but never changes it
   for you.

4. **Reinstall WARP.** Uninstall the 1.1.1.1 / WARP app, download it again from
   **https://1.1.1.1/**, install it, then run the tool again.

5. **Show someone the log.** The tool writes down everything it did in a file.
   Press <kbd>Windows</kbd> + <kbd>R</kbd>, type `%TEMP%\warp_fix.log`, press
   Enter. That file is very handy if you ask someone for help.

---

## ❓ Questions people ask

**Is this safe? Will it break my computer?**
It only touches Cloudflare WARP — it restarts WARP's background service and
asks Cloudflare for a new registration. It doesn't touch your files, your
games, or anything else. All of the code is right here in
[`warp_fix.py`](warp_fix.py) and [`RUN_ME.bat`](RUN_ME.bat) so anyone can read
it.

**Will it change my WARP settings?**
No. It reads your tunnel protocol (MASQUE / WireGuard) and your mode before it
starts, and if re-registering resets them it puts your own values straight
back. It will never move you from MASQUE to WireGuard, or the other way round.

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
| `RUN_ME.bat` | The download target. Self-elevates via UAC, bootstraps Python (winget, then the python.org installer), fetches `warp_fix.py` if it isn't alongside, then runs it with `--no-elevate --no-pause`. |
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
| 0 | Self-elevate via UAC, locate `warp-cli.exe`, make sure the `CloudflareWARP` service is running, read `valid_until` from `conf.json`, **snapshot the current tunnel protocol and mode** |
| 1 | `warp-cli connect` (skipped if the registration is already expired) |
| 2 | `registration delete` → `registration new` → re-apply saved licence → **restore the snapshotted protocol/mode if re-registration reset them** → `connect` |
| 3 | `sc stop` / `sc start CloudflareWARP`, then reconnect |
| ✔ | Verify against `https://www.cloudflare.com/cdn-cgi/trace` that `warp=on` |

**Settings are never changed on your behalf.** There is no
`tunnel protocol set`, no `tunnel protocol reset` and no `mode warp` in the
happy path — the only time the script writes a protocol or mode is to put back
the value it read from your machine before it started. Mode strings it doesn't
recognise are left untouched rather than guessed at.

If nothing connects, it runs a network diagnosis: TCP/443 reachability to the
WARP edge (`162.159.198.2`), `api.cloudflareclient.com` and `1.1.1.1`, the
current protocol/mode, and the final `warp-cli status` output. Switching
protocol is offered there as advice for you to act on, not as an action.

### Command line

```powershell
python warp_fix.py              # auto-prompts for admin via UAC
python warp_fix.py --no-pause   # don't wait for Enter at the end (for scripts)
python warp_fix.py --no-elevate # already elevated; don't try to re-launch
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Connected (fixed, or already fine) |
| `1` | Setup problem — not admin, no `warp-cli.exe`, service missing/won't start |
| `2` | Not fixed; diagnosis printed |
| `3` | WARP says connected but the trace check shows traffic isn't in the tunnel |
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
