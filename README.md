# Wispr Flow dictation in the VS Code terminal (Windows)

How to make [Wispr Flow](https://wisprflow.ai) dictation land in the **VS Code integrated terminal** on Windows when a terminal app such as Claude Code is running in it.

> Unofficial community notes. Not affiliated with or endorsed by Wispr or Anthropic.

## The problem

On Windows, Wispr Flow dictates fine into most apps, but when Claude Code is running in the VS Code integrated terminal:

- the dictated text never appears in the prompt, and
- Flow shows a popup: **"Select a textbox first, then dictate"**.

## Fix: one VS Code keybinding (try this first)

Add this entry to your VS Code `keybindings.json` (`Ctrl+Shift+P` → **Preferences: Open Keyboard Shortcuts (JSON)**):

```json
{
    "key": "shift+insert",
    "command": "workbench.action.terminal.paste",
    "when": "terminalFocus"
}
```

It takes effect immediately, with no restart. Dictate into the terminal again: the text should appear and Flow's popup should no longer show.

Confirmed on Windows 11, VS Code 1.147, Wispr Flow 1.6.1537 and Claude Code 2.1.329.

### Why it works

- When VS Code is in front, Flow pastes with `Shift+Insert`, not `Ctrl+V` ([Wispr docs](https://docs.wisprflow.ai/articles/6434410694-use-flow-with-cursor-vs-code-and-other-ides)).
- VS Code's terminal passes that key through to the program running in it. A plain PowerShell or bash prompt treats it as paste, but Claude Code drops it, so nothing is inserted and Flow reports that it found no text box.
- The keybinding makes VS Code itself handle `Shift+Insert` as "paste into terminal", so the text arrives as a normal paste regardless of what is running.

The fix and the root cause come from the discussion in [anthropics/claude-code#93782](https://github.com/anthropics/claude-code/issues/93782). People on remote setups (Remote-SSH, WSL) there also report success with `"terminal.integrated.enableKittyKeyboardProtocol": false` in the remote machine settings.

## Fallback: the bridge script

If the keybinding does not work for your setup, `flow_terminal_bridge.py` is a heavier workaround. **Do not use both** — with the keybinding active, the bridge would paste every dictation twice.

The script runs in the background and:

1. Watches Flow's local history database (**read-only**) for new transcripts made in VS Code.
2. Checks that the VS Code terminal currently has keyboard focus.
3. Copies the transcript to the Windows clipboard and sends `Ctrl+V`.
4. Presses the dismiss button on Flow's "Select a textbox first" popup, so it only flashes briefly.

It only acts when the VS Code terminal is focused, so Flow's own paste in other apps is never doubled.

### Requirements

- Windows 10 or 11, Wispr Flow for Windows, VS Code
- Python 3.9 or newer

### Install

```powershell
git clone https://github.com/himalkarki2074-stack/wispr-flow-vscode-terminal-bridge.git
cd wispr-flow-vscode-terminal-bridge
pip install -r requirements.txt
.\install_startup.ps1
```

`install_startup.ps1` adds a shortcut to your Windows Startup folder so the bridge launches hidden at every login, and starts it immediately. If PowerShell blocks the script, run it with `powershell -ExecutionPolicy Bypass -File .\install_startup.ps1`.

To run it manually instead:

```powershell
pythonw flow_terminal_bridge.py            # hidden, runs until you log off
python flow_terminal_bridge.py --dry-run   # logs what it would do, never pastes
```

### Troubleshooting

Every dictation is recorded in `bridge.log` next to the script, with the reason it was pasted or skipped. Transcript text is not logged, only its length.

| Log line | Meaning |
| --- | --- |
| `pasted … (N chars)` | The transcript was pasted. |
| `skip …: focus is … not the VS Code terminal` | Focus was somewhere other than the terminal, so nothing was pasted. |
| `skip …: modifier keys still held` | Your dictation hotkey was still held down; release it sooner. |
| `database read failed, will retry` | Flow is not running yet, or its database is busy. The bridge keeps retrying. |
| `Flow's textbox warning did not appear` | The popup was not found, so there was nothing to dismiss. |

If nothing pastes and the log shows `focus is code.exe / ''`, set `"editor.accessibilitySupport": "on"` in VS Code settings and restart VS Code. The bridge was only tested with this setting on.

### Configuration

The constants at the top of `flow_terminal_bridge.py` can be adjusted:

| Constant | Default | Purpose |
| --- | --- | --- |
| `FLOW_APP_NAME` | `code` | App name Flow records for the editor. Change for VS Code forks. |
| `TARGET_PROCESS` | `code.exe` | Process that must own the focused terminal. Change for VS Code forks. |
| `SETTLE_SECONDS` | `0.4` | Delay before pasting, to let Flow finish its own attempt. |
| `POLL_SECONDS` | `0.3` | How often Flow's database is checked. |
| `FLOW_WARNING_TEXT` / `FLOW_DISMISS_BUTTON` | English strings | Text used to find and close Flow's popup. Change if Flow's UI is in another language. |

### Limitations

- **Depends on Flow internals.** It reads Flow's undocumented local database and the wording of its popup. A Flow update can break it.
- **Windows only**, tested on one machine (Windows 11, Wispr Flow 1.6.1537, VS Code 1.147, Python 3.13).
- **The popup still flashes.** It cannot be prevented, only dismissed quickly.
- **Uses the clipboard.** Whatever was on your clipboard is replaced by the transcript.
- **VS Code forks** (Cursor, Windsurf, VSCodium) are untested.

### Privacy

The script runs entirely on your machine. It opens Flow's database read-only, sends nothing over the network, and does not write transcript text to its log.

### Uninstall

1. Press `Win+R`, enter `shell:startup`, and delete the **Wispr Flow Terminal Bridge** shortcut.
2. End `pythonw.exe` in Task Manager (or log off).
3. Delete this folder.

## License

MIT — see [LICENSE](LICENSE).
