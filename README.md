# Wispr Flow → VS Code Terminal Bridge

Makes [Wispr Flow](https://wisprflow.ai) dictation work in the **VS Code integrated terminal** on Windows — for example when typing prompts into Claude Code or any other CLI running inside VS Code.

> Unofficial community workaround. Not affiliated with or endorsed by Wispr.

## The problem

On Windows, Wispr Flow dictates fine into most apps (and into Windows Terminal), but in the VS Code integrated terminal:

- the dictated text never appears, and
- Flow shows a popup: **"Select a textbox first, then dictate"**.

VS Code's terminal is drawn by xterm.js rather than built from a normal text field, and Flow does not deliver text to it. Flow still transcribes the dictation and saves it to its local history — it just never reaches the terminal.

## What this does

A small background Python script that:

1. Watches Flow's local history database (**read-only**) for new transcripts made in VS Code.
2. Checks that the VS Code terminal currently has keyboard focus.
3. Copies the transcript to the Windows clipboard and sends `Ctrl+V`.
4. Presses the dismiss button on Flow's "Select a textbox first" popup, so it only flashes briefly.

It only acts when the VS Code terminal is focused. In the editor, browsers, Outlook, Windows Terminal and so on it does nothing, so Flow's own paste is never doubled.

The transcript stays on the clipboard after pasting.

## Requirements

- Windows 10 or 11
- [Wispr Flow](https://wisprflow.ai) for Windows, running and signed in
- VS Code
- Python 3.9 or newer

Tested with Windows 11, Wispr Flow 1.6.1537, VS Code 1.147 and Python 3.13.

## Install

```powershell
git clone https://github.com/himalkarki2074-stack/wispr-flow-vscode-terminal-bridge.git
cd wispr-flow-vscode-terminal-bridge
pip install -r requirements.txt
.\install_startup.ps1
```

`install_startup.ps1` adds a shortcut to your Windows Startup folder so the bridge launches hidden at every login, and starts it immediately.

If PowerShell blocks the script, run it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_startup.ps1
```

### Run it manually instead

```powershell
pythonw flow_terminal_bridge.py            # hidden, runs until you log off
python flow_terminal_bridge.py --dry-run   # logs what it would do, never pastes
```

## Usage

Click into the VS Code terminal and dictate with Flow as usual. The text appears about half a second after Flow finishes. Flow's popup may flash briefly before it is dismissed.

## Troubleshooting

Every dictation is recorded in `bridge.log` next to the script, with the reason it was pasted or skipped. Transcript text is not logged, only its length.

| Log line | Meaning |
| --- | --- |
| `pasted … (N chars)` | The transcript was pasted. |
| `skip …: focus is … not the VS Code terminal` | Focus was somewhere other than the terminal, so nothing was pasted. |
| `skip …: modifier keys still held` | Your dictation hotkey was still held down; release it sooner. |
| `database read failed, will retry` | Flow is not running yet, or its database is busy. The bridge keeps retrying. |
| `Flow's textbox warning did not appear` | The popup was not found, so there was nothing to dismiss. |

**Nothing pastes and the log shows `focus is code.exe / ''`:** VS Code is not exposing its terminal to accessibility tools. Set `"editor.accessibilitySupport": "on"` in VS Code settings and restart VS Code. The bridge was developed and tested with this setting on; other values are untested.

**Nothing is logged at all when you dictate:** check that Flow's database exists at `%APPDATA%\Wispr Flow\flow.sqlite` and that the dictation shows up in Flow's own history.

## Configuration

The constants at the top of `flow_terminal_bridge.py` can be adjusted:

| Constant | Default | Purpose |
| --- | --- | --- |
| `FLOW_APP_NAME` | `code` | App name Flow records for the editor. Change for VS Code forks. |
| `TARGET_PROCESS` | `code.exe` | Process that must own the focused terminal. Change for VS Code forks. |
| `SETTLE_SECONDS` | `0.4` | Delay before pasting, to let Flow finish its own attempt. |
| `POLL_SECONDS` | `0.3` | How often Flow's database is checked. |
| `FLOW_WARNING_TEXT` / `FLOW_DISMISS_BUTTON` | English strings | Text used to find and close Flow's popup. Change if Flow's UI is in another language. |

## Limitations

- **Depends on Flow internals.** It reads Flow's undocumented local database and the wording of its popup. A Flow update can break it.
- **Windows only.**
- **The popup still flashes.** It cannot be prevented, only dismissed quickly.
- **Uses the clipboard.** Whatever was on your clipboard is replaced by the transcript.
- **English Flow UI assumed** for dismissing the popup. Pasting still works in other languages.
- **VS Code forks** (Cursor, Windsurf, VSCodium) are untested; see Configuration.

## Privacy

The script runs entirely on your machine. It opens Flow's database read-only, sends nothing over the network, and does not write transcript text to its log.

## Uninstall

1. Press `Win+R`, enter `shell:startup`, and delete the **Wispr Flow Terminal Bridge** shortcut.
2. End `pythonw.exe` in Task Manager (or log off).
3. Delete this folder.

## License

MIT — see [LICENSE](LICENSE).
