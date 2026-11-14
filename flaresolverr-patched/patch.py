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
    import signal as _signal
    try:
        my_uid = os.getuid()
        for _ in range(6):
            victims = []
            for name in os.listdir("/proc"):
                if not name.isdigit():
                    continue
                pid = int(name)
                if pid <= 1:
                    continue
                try:
                    with open("/proc/%d/stat" % pid) as f:
                        stat = f.read().split()
                    # stat[3] is ppid; comm may contain spaces but ppid is field 4
                    ppid = int(stat[3])
                    # verify it is a chromium process owned by us
                    with open("/proc/%d/cmdline" % pid, "rb") as f:
                        cmd = f.read().replace(b"\\x00", b" ").decode("utf-8", "ignore")
                except (FileNotFoundError, ProcessLookupError, ValueError, PermissionError):
                    continue
                if ppid != 1:
                    continue
                if "/usr/lib/chromium/chromium" not in cmd:
                    continue
                try:
                    if os.stat("/proc/%d" % pid).st_uid != my_uid:
                        continue
                except FileNotFoundError:
                    continue
                victims.append(pid)
            for pid in victims:
                try:
                    os.kill(pid, _signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            if not victims:
                break
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