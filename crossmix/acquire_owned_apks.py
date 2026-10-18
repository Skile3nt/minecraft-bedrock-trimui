#!/usr/bin/env python3
"""Temporary, private Google login and exact owned-APK acquisition.

Run with the already verified local bundle, never in a terminal that logs raw
authentication output. Status contains only fixed stages, percentages and file
names. Account handling is delegated to the reviewed upstream helper.
"""
from __future__ import annotations

import datetime
import gc
import json
import logging
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "recovery/play-acquisition"
PRIVATE = WORK / "private-session"
STATUS = WORK / "acquisition-status.json"
VERSION_CODE = 971622101


def ask_address_gtk(pre_login: bool = False) -> str:
    """Use the already available GTK; host Tk may need an absent libtk8.6."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    status("awaiting_account_address" if pre_login else "awaiting_account_confirmation")
    dialog = Gtk.Dialog(title="Minecraft — confirmar conta Google")
    dialog.set_default_size(480, 180)
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Continuar", Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)
    content = dialog.get_content_area()
    content.set_border_width(18)
    introduction = "Informe a conta que será usada na janela do Google." if pre_login else "O Google concluiu a entrada, mas não informou o endereço."
    label = Gtk.Label(label=introduction + "\n"
                           "Confirme o e-mail da conta que comprou Minecraft Android.\n"
                           "Não digite sua senha nesta janela.")
    label.set_line_wrap(True)
    content.pack_start(label, True, True, 8)
    entry = Gtk.Entry()
    entry.set_activates_default(True)
    content.pack_start(entry, True, True, 8)
    dialog.show_all()
    dialog.present()
    entry.grab_focus()
    address = ""
    while True:
        response = dialog.run()
        if response != Gtk.ResponseType.OK:
            break
        proposed = entry.get_text().strip()
        if proposed.count("@") == 1 and all(proposed.split("@")) and not any(c.isspace() for c in proposed):
            address = proposed
            break
        label.set_text("Informe o e-mail completo, incluindo @ e domínio.\n"
                       "A sessão ficará aguardando nesta janela. Não digite sua senha.")
        entry.grab_focus()
    dialog.destroy()
    return address


def status(stage: str, **fields) -> None:
    payload = {"stage": stage, "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), **fields}
    temporary = STATUS.with_suffix(".new")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(STATUS)


def main() -> int:
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Native browser/C++ diagnostics can contain entire server responses or URLs.
    # Discard them at the descriptor level before any credentials can exist.
    with open(os.devnull, "r+b", buffering=0) as sink:
        for descriptor in (0, 1, 2):
            os.dup2(sink.fileno(), descriptor)
    logging.disable(logging.CRITICAL)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PRIVATE.chmod(0o700)
    if PRIVATE.stat().st_uid != os.getuid():
        raise RuntimeError("Private directory ownership mismatch")
    os.environ.update(MCBEDROCK_DATA_DIR=str(PRIVATE), MCBEDROCK_PREFIX=str(PRIVATE),
                      XDG_CACHE_HOME=str(PRIVATE / "cache"), PYWEBVIEW_GUI="gtk")
    for key in tuple(os.environ):
        if key.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
            os.environ.pop(key)
    bundle = WORK / "tools/squashfs-root/opt/python3.11/lib/python3.11/site-packages"
    sys.path.insert(0, str(bundle))
    sys.path.insert(0, str(ROOT / "tools/mcbedrock-get"))
    import signin
    import linux_backend as backend
    import mcbedrock_get as helper
    import requests
    helper.ask_for_address = ask_address_gtk

    # gpsoauth only needs this exact HTTPS endpoint; redirects cannot carry
    # credentials elsewhere. This does not change account or licensing checks.
    original_request = requests.sessions.Session.request

    def auth_request(session, method, url, *args, **kwargs):
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.hostname, parsed.path) != (
                "https", "android.clients.google.com", "/auth"):
            raise RuntimeError("Unexpected authentication destination")
        kwargs["allow_redirects"] = False
        kwargs["timeout"] = 45
        kwargs["verify"] = True
        session.trust_env = False
        return original_request(session, method, url, *args, **kwargs)

    requests.sessions.Session.request = auth_request
    credentials = None
    outcome = {"result": "not_started", "apks": []}

    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    stage = "account_confirmation"
    try:
        # Collect this before starting WebKit, so a completed Google session
        # never depends on reopening GTK after the browser application exits.
        address = ask_address_gtk(pre_login=True)
        if not address:
            raise signin.SignInError("No account address was given, so nothing was saved.")
        stage = "login"
        status("awaiting_google_login")
        credentials = helper.interactive_login(address)
        address = ""
        status("google_login_completed")
        stage = "play_session"
        backend.ensure_device_profile("arm64")
        backend.sign_in(credentials.email, credentials.master_token)
        for name in ("account.json", "playdl.conf", "token_cache.conf"):
            path = PRIVATE / name
            if path.exists():
                path.chmod(0o600)
        stage = "download"
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = Path.home() / "Downloads" / ("Minecraft-1.16.221.01-ARM64-original-" + stamp)
        output.mkdir(mode=0o700, exist_ok=False)
        status("downloading_exact_build", version_code=VERSION_CODE, abi="arm64-v8a")

        def progress(line):
            # Never persist arbitrary downloader messages or exception text.
            import re
            found = re.search(r"Downloaded (\d+)%", line)
            if found:
                status("downloading_exact_build", percent=int(found[1]), version_code=VERSION_CODE)

        apks = backend.download(VERSION_CODE, output, on_line=progress, timeout=900, abi="arm64")
        outcome = {"result": "downloaded_pending_signature_validation", "apks": [str(p) for p in apks]}
    except BaseException as error:
        # Exception messages may contain signed download URLs or server tokens.
        outcome = {"result": "stopped", "failed_stage": stage, "error_type": type(error).__name__, "apks": []}
        message = str(error)
        if message.startswith("Sign-in did not complete."):
            outcome["reason"] = "google_window_closed_without_completed_session"
        elif message.startswith("Google did not return an account token:"):
            outcome["reason"] = "google_token_exchange_refused"
            for code in ("BadAuthentication", "NeedsBrowser", "CaptchaRequired", "DeviceManagementRequired", "ServiceDisabled"):
                if message.endswith(code):
                    outcome["google_error_code"] = code
        elif message.startswith("No account address was given"):
            outcome["reason"] = "account_address_not_available"
        del message
    finally:
        status("removing_local_session")
        removed = backend.sign_out()
        signin.forget()
        for name in ("account.json.new", "playdl.new", "playdl.conf.new"):
            (PRIVATE / name).unlink(missing_ok=True)
        # Google-Play-API also persists check-in/security/API state beside the
        # device profile. Upstream sign_out omits this credential-bearing file.
        for path in PRIVATE.glob("device-*.conf.state"):
            path.unlink()
        shutil.rmtree(PRIVATE / "cache", ignore_errors=True)
        credentials = None
        gc.collect()
        absent = (all(not (PRIVATE / name).exists() for name in (
            "account.json", "account.json.new", "playdl.conf", "playdl.new", "playdl.conf.new", "token_cache.conf"))
            and not any(PRIVATE.glob("device-*.conf.state")))
        status("finished", **outcome, credentials_removed=bool(removed and absent))
    return 0 if outcome["result"].startswith("downloaded") else 1


if __name__ == "__main__":
    raise SystemExit(main())
