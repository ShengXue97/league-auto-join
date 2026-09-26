"""
Build League Remote for Windows:
  dist/LeagueRemote/LeagueRemote.exe        the app (PyInstaller, no Python needed)
  dist/LeagueRemote-Setup-<version>.exe     the installer (Inno Setup)

Run: python build.py            (needs: pip install pyinstaller pystray pillow segno, and Inno Setup 6)
     python build.py --no-installer
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
ISCC_PATHS = [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
              r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe"]


def version():
    with open(os.path.join(ROOT, "league_remote.py"), encoding="utf-8") as f:
        return re.search(r'__version__ = "([^"]+)"', f.read()).group(1)


def version_file(v):
    """Windows file properties (Details tab) for LeagueRemote.exe."""
    nums = (tuple(int(x) for x in v.split(".")) + (0, 0, 0, 0))[:4]
    path = os.path.join(BUILD, "version_info.txt")
    os.makedirs(BUILD, exist_ok=True)
    fields = {"CompanyName": "League Remote (fan project)", "FileDescription": "League Remote",
              "FileVersion": v, "InternalName": "LeagueRemote", "OriginalFilename": "LeagueRemote.exe",
              "ProductName": "League Remote", "ProductVersion": v,
              "LegalCopyright": "Fan project, not endorsed by Riot Games"}
    strings = ",\n".join(f"StringStruct('{k}', '{val}')" for k, val in fields.items())
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [{strings}])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""")
    return path


def run(cmd):
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    v = version()
    print(f"Building League Remote v{v}")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_icon.py")], check=True)
    shutil.rmtree(os.path.join(DIST, "LeagueRemote"), ignore_errors=True)
    sep = os.pathsep
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
         "--name", "LeagueRemote",
         "--icon", os.path.join(ROOT, "assets", "icon.ico"),
         "--version-file", version_file(v),
         "--add-data", f"{os.path.join(ROOT, 'phone.html')}{sep}.",
         "--add-data", f"{os.path.join(ROOT, 'assets')}{sep}assets",
         "--hidden-import", "pystray._win32",
         # not used by League Remote; would otherwise be bundled from the build PC
         *[a for m in ("numpy", "setuptools", "pkg_resources", "tkinter", "unittest", "pydoc", "PIL.ImageQt",
                       "PIL._avif", "PIL._webp", "PIL.ImageTk") for a in ("--exclude-module", m)],
         "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyinstaller"), "--specpath", BUILD,
         os.path.join(ROOT, "league_remote.py")])
    exe = os.path.join(DIST, "LeagueRemote", "LeagueRemote.exe")
    print(f"App: {exe}")

    if "--no-installer" in sys.argv:
        return
    iscc = next((p for p in ISCC_PATHS if os.path.exists(p)), None)
    if not iscc:
        sys.exit("Inno Setup 6 not found - install it or run with --no-installer")
    run([iscc, f"/DAppVersion={v}", os.path.join(ROOT, "packaging", "installer.iss")])
    print(f"Installer: {os.path.join(DIST, f'LeagueRemote-Setup-{v}.exe')}")


if __name__ == "__main__":
    main()
