"""Patch flaresolverr to clean up orphaned chromium processes (upstream #1815).

After a successful solve, selenium's service.stop() calls os.kill(chromedriver_pid,
SIGTERM), but chromedriver has already exited (zombie) and its PID has been
recycled to a root-owned process, so the call raises PermissionError and the
chromium process tree is orphaned (re-parented to PID 1). Over time these
orphans accumulate and OOM the pod. This patch kills orphaned chromium
processes after every request.
"""
import pathlib

# --- utils.py ---
utils = pathlib.Path("/app/utils.py")
u = utils.read_text()
assert "import subprocess" not in u.split("\n", 20), "already patched"
# add subprocess import after `import shutil`
u = u.replace("import shutil\n", "import shutil\nimport subprocess\n", 1)
# append cleanup helper before the last line (file ends with no newline guarantee)
func = '''
def cleanup_orphaned_browsers() -> None:
    """Kill chromium processes orphaned to PID 1 (see upstream issue #1815).

    When selenium fails to terminate chromedriver, the chromium tree is
    re-parented to PID 1 and keeps running. Kill top-down in a few passes:
    each pass removes the current top level, re-parenting the next level to
    PID 1 so the next pass can reach it. Active browsers (parent != 1) are
    left untouched.
    """
    try:
        for _ in range(6):
            subprocess.run(
                "for p in $(pgrep -u $(id -u) -f '/usr/lib/chromium/chromium' 2>/dev/null); do "
                "[ \"$(awk '{print $4}' /proc/$p/stat 2>/dev/null)\" = 1 ] && kill -9 $p 2>/dev/null; "
                "done",
                shell=True, executable="/bin/sh", stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
    except Exception:
        pass
'''
u = u.rstrip() + "\n" + func
utils.write_text(u)

# --- flaresolverr_service.py ---
svc = pathlib.Path("/app/flaresolverr_service.py")
s = svc.read_text()
old = """            driver.quit()
            logging.debug('A used instance of webdriver has been destroyed')"""
new = """            driver.quit()
            utils.cleanup_orphaned_browsers()
            logging.debug('A used instance of webdriver has been destroyed')"""
assert s.count(old) == 1, f"expected 1 occurrence, found {s.count(old)}"
svc.write_text(s.replace(old, new, 1))
print("patched")