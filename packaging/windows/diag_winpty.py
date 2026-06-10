"""Diagnostyka pywinpty (ConPTY) na czystym Windows — używane przez workflow
diagnose-windows.yml. Sprawdza, czy PTY w ogóle wstaje i odpowiada, ZANIM
zaczniemy podejrzewać pakowanie PyInstallerem.

Uruchom (Windows): python packaging\\windows\\diag_winpty.py
Wynik: kod 0 = PTY działa (echo wróciło), kod 1 = nie działa.
"""
import os
import sys
import time

print("python:", sys.version)
print("COMSPEC:", os.environ.get("COMSPEC"))

try:
    import winpty
    print("winpty zaimportowany:", getattr(winpty, "__version__", "?"),
          "z", getattr(winpty, "__file__", "?"))
except Exception as e:
    print("BLAD importu winpty:", repr(e))
    sys.exit(1)

shell = os.environ.get("COMSPEC") or "cmd.exe"
print("spawn:", shell)
try:
    proc = winpty.PtyProcess.spawn(shell, dimensions=(24, 80))
except Exception as e:
    print("BLAD spawn:", repr(e))
    sys.exit(1)

collected = ""
try:
    proc.write("echo PTY-ECHO-OK\r\n")
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            chunk = proc.read(65536)
        except Exception as e:
            print("read przerwany:", repr(e))
            break
        if chunk:
            collected += chunk
        if "PTY-ECHO-OK" in collected:
            break
        time.sleep(0.2)
finally:
    try:
        proc.terminate()
    except Exception:
        pass

print("zebrane bajty:", len(collected))
print("probka:", repr(collected[-400:]))
ok = "PTY-ECHO-OK" in collected
print("WYNIK:", "OK — ConPTY dziala" if ok else "FAIL — echo nie wrocilo")
sys.exit(0 if ok else 1)
