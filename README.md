# Cloudflare One Client Patches

Little fix-it tools for the **Cloudflare WARP** app (the 1.1.1.1 app) on Windows.

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
main thing this tool does. If that doesn't work, it tries a few other tricks
too.

---

## 🚀 How to use it — the easy way

You need **Windows**. That's it.

### Step 1 — Get Python

Python is the thing that runs the tool. Ask a grown-up if you're not sure.

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button.
3. Open the file you just downloaded.
4. ⚠️ **Very important:** tick the little box that says
   **"Add python.exe to PATH"** at the bottom of the window *before* you click
   Install. If you miss it, the tool won't be able to find Python.
5. Click **Install Now** and wait.

*Already have Python? Skip this step.*

### Step 2 — Get the files

1. At the top of this page, click the green **Code** button.
2. Click **Download ZIP**.
3. Find the ZIP in your **Downloads** folder, right-click it, choose
   **Extract All…**, then click **Extract**.

### Step 3 — Run it

1. Open the folder you just unzipped.
2. Double-click **`RUN_ME.bat`**.
3. Windows will pop up a blue-ish box asking
   **"Do you want to allow this app to make changes to your device?"**
   Click **Yes**. 👍
   (It has to ask, because fixing WARP means changing computer settings.)
4. A black window opens and starts typing things. **Just let it work.**
   It usually takes less than a minute.

### Step 4 — Read the last line

When it's done, look at the very bottom of the black window:

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

3. **Reinstall WARP.** Uninstall the 1.1.1.1 / WARP app, download it again from
   **https://1.1.1.1/**, install it, then run the tool again.

4. **Show someone the log.** The tool writes down everything it did in a file.
   Press <kbd>Windows</kbd> + <kbd>R</kbd>, type `%TEMP%\warp_fix.log`, press
   Enter. That file is very handy if you ask someone for help.

---

## ❓ Questions people ask

**Is this safe? Will it break my computer?**
It only touches Cloudflare WARP — it restarts WARP's background service and
asks Cloudflare for a new registration. It doesn't touch your files, your
games, or anything else. All of the code is right here in
[`warp_fix.py`](warp_fix.py) so anyone can read it.

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

### What it actually does

The usual root cause is that the device registration in
`C:\ProgramData\Cloudflare\conf.json` has a `valid_until` timestamp in the
past, and the WARP service fails to renew it. Every connect attempt then cycles
through the fallback ports and never completes the handshake — the UI shows
"Connecting" and parks at ~26%.

The script runs this ladder and stops at the first thing that works:

| Step | Action |
|---|---|
| 0 | Self-elevate via UAC, locate `warp-cli.exe`, make sure the `CloudflareWARP` service is running, read `valid_until` from `conf.json` |
| 1 | `warp-cli connect` (skipped if the registration is already expired) |
| 2 | `registration delete` → `registration new` → re-apply saved licence → `tunnel protocol reset` → `mode warp` → `connect` |
| 3 | `sc stop` / `sc start CloudflareWARP`, then reconnect |
| 4 | `tunnel protocol set WireGuard` instead of MASQUE, then reconnect |
| ✔ | Verify against `https://www.cloudflare.com/cdn-cgi/trace` that `warp=on` |

If nothing connects, it runs a network diagnosis: TCP/443 reachability to the
WARP edge (`162.159.198.2`), `api.cloudflareclient.com` and `1.1.1.1`, plus the
final `warp-cli status` output.

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

On a machine with Python, double-click **`build_exe.bat`**, or run:

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
