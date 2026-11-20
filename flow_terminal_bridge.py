"""Pastes Wispr Flow dictations into the VS Code integrated terminal.

Flow transcribes dictations made in VS Code and saves them to its local
history database, but does not deliver the text to the terminal. This script
watches that database (read-only) and, when a new transcript appears while the
VS Code terminal has keyboard focus, copies it to the clipboard and sends Ctrl+V.

Run with:  pythonw flow_terminal_bridge.py
Dry run:   python flow_terminal_bridge.py --dry-run   (logs only, never pastes)
"""

import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

import comtypes.client
import psutil
import win32api
import win32clipboard
import win32con
import win32event
import win32gui
import winerror

DB_PATH = os.path.expandvars(r"%APPDATA%\Wispr Flow\flow.sqlite")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.log")
FLOW_APP_NAME = "code"                      # History.app value Flow records for VS Code
TARGET_PROCESS = "code.exe"
TERMINAL_CLASS = "xterm-helper-textarea"    # focused element class inside the VS Code terminal
POLL_SECONDS = 0.3
SETTLE_SECONDS = 0.4                        # let Flow finish its own paste attempt first
FLOW_OVERLAY_TITLE = "Status"               # Flow's always-on-top overlay window
FLOW_WARNING_TEXT = "Select a textbox first"
FLOW_DISMISS_BUTTON = "Dismiss notification"
TREE_SCOPE_DESCENDANTS = 4
UIA_INVOKE_PATTERN_ID = 10000
MODIFIER_KEYS = (win32con.VK_CONTROL, win32con.VK_MENU, win32con.VK_SHIFT,
                 win32con.VK_LWIN, win32con.VK_RWIN)

comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen.UIAutomationClient import IUIAutomationInvokePattern  # noqa: E402

logger = logging.getLogger("flow_terminal_bridge")


def setup_logging():
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def utc_stamp():
    # Matches Flow's History.timestamp text format, so string comparison orders correctly.
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " +00:00"


def connect():
    uri = "file:" + DB_PATH.replace("\\", "/").replace(" ", "%20") + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=2)


def focused_element(uia):
    element = uia.GetFocusedElement()
    process = psutil.Process(element.CurrentProcessId).name().lower()
    return process, element.CurrentClassName or ""


def wait_for_modifiers_released(timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(win32api.GetAsyncKeyState(key) & 0x8000 for key in MODIFIER_KEYS):
            return True
        time.sleep(0.05)
    return False


def set_clipboard(text):
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
        except win32clipboard.error:
            time.sleep(0.05)
            continue
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            return True
        finally:
            win32clipboard.CloseClipboard()
    return False


def send_ctrl_v():
    key_v = ord("V")
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(key_v, 0, 0, 0)
    win32api.keybd_event(key_v, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def dismiss_flow_warning(uia, timeout=4.0):
    """Presses the close button on Flow's 'select a textbox' popup once it appears."""
    hwnd = win32gui.FindWindow("Chrome_WidgetWin_1", FLOW_OVERLAY_TITLE)
    if not hwnd:
        logger.warning("Flow overlay window not found; cannot dismiss its popup")
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = uia.ElementFromHandle(hwnd).FindAll(TREE_SCOPE_DESCENDANTS, uia.CreateTrueCondition())
        dismiss_button = None
        for i in range(found.Length):
            element = found.GetElement(i)
            name = element.CurrentName or ""
            if name == FLOW_DISMISS_BUTTON:
                dismiss_button = element
            elif name.startswith(FLOW_WARNING_TEXT) and dismiss_button is not None:
                pattern = dismiss_button.GetCurrentPattern(UIA_INVOKE_PATTERN_ID)
                pattern.QueryInterface(IUIAutomationInvokePattern).Invoke()
                logger.info("dismissed Flow's textbox warning")
                return
        time.sleep(0.1)
    logger.info("Flow's textbox warning did not appear within %.0fs", timeout)


def deliver(uia, entity_id, text, dry_run):
    time.sleep(SETTLE_SECONDS)
    process, class_name = focused_element(uia)
    if process != TARGET_PROCESS or class_name != TERMINAL_CLASS:
        logger.info("skip %s: focus is %s / '%s', not the VS Code terminal",
                    entity_id, process, class_name)
        return
    if dry_run:
        logger.info("dry run: would paste %s (%d chars)", entity_id, len(text))
        return
    if not wait_for_modifiers_released():
        logger.warning("skip %s: modifier keys still held after timeout", entity_id)
        return
    if not set_clipboard(text):
        logger.error("skip %s: could not open the clipboard", entity_id)
        return
    send_ctrl_v()
    logger.info("pasted %s (%d chars)", entity_id, len(text))
    dismiss_flow_warning(uia)


def main():
    setup_logging()
    dry_run = "--dry-run" in sys.argv

    mutex = win32event.CreateMutex(None, False, "WisprFlowTerminalBridge")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        logger.info("another instance is already running; exiting")
        return

    from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
    uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)

    started = utc_stamp()
    seen = set()
    db = None
    logger.info("started (dry_run=%s), watching %s", dry_run, DB_PATH)

    while True:
        try:
            if db is None:
                db = connect()
            rows = db.execute(
                "select transcriptEntityId, app, formattedText from History "
                "where timestamp >= ? and status = 'formatted'", (started,)).fetchall()
        except sqlite3.Error as err:
            logger.warning("database read failed, will retry: %s", err)
            if db is not None:
                db.close()
                db = None
            time.sleep(2)
            continue

        for entity_id, app, text in rows:
            if entity_id in seen:
                continue
            seen.add(entity_id)
            if (app or "").lower() != FLOW_APP_NAME or not text:
                continue
            try:
                deliver(uia, entity_id, text, dry_run)
            except Exception:
                logger.exception("failed to deliver %s", entity_id)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
