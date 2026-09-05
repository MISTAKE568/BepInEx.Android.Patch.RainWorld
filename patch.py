#!/usr/bin/env python3
"""BepInEx.Android APK patcher (cross-platform).

Rewrites an APK to inject the BepInEx Android injection chain:
  1. replace lib/arm64-v8a/libmain.so with our custom libmain.so
  2. add libfusion.so + dotnet/coreclr runtime .so files
  3. embed assets/ (BepInEx core + dotnet managed + unity-libs)
  4. re-sign with apksigner (optional)

Usage:
  python3 patch.py <in.apk> <out.apk> [--resources DIR] [--sign] [--keystore PATH]
                   [--unity-libs URL]

Resources layout (default: ./resources next to this script):
  resources/so/            libmain.so, libfusion.so, libdobby.so, libcoreclr.so, ...
  resources/dotnet/        managed runtime dlls
  resources/BepInEx/       core/ plugins/ config/ unity-libs/
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

SO_FILES = [
    "libmain.so", "libfusion.so", "libdobby.so", "libcoreclr.so", "libclrjit.so",
    "libc++_shared.so",
    "libSystem.Native.so", "libSystem.Globalization.Native.so",
    "libSystem.IO.Compression.Native.so", "libcrypto.so", "libssl.so",
    "libSystem.Security.Cryptography.Native.OpenSsl.so",
    "libmscordaccore.so", "libmscordbi.so",
]

SKIP_EXACT = {
    "lib/arm64-v8a/libmain.so",
    "lib/arm64-v8a/libfusion.so",
    "META-INF/CERT.RSA", "META-INF/CERT.SF", "META-INF/MANIFEST.MF",
}


def read_zip_string(zf, name):
    info = zf.getinfo(name)
    return zf.read(name).decode("utf-8", errors="replace")


def detect_unity_version(in_apk):
    """Best-effort Unity version from globalgamemanagers (or the engine string)."""
    with zipfile.ZipFile(in_apk) as zf:
        for cand in ("assets/bin/Data/globalgamemanagers", "assets/bin/Data/globalgamemanagers.assets"):
            if cand in zf.namelist():
                data = zf.read(cand)
                for i in range(min(len(data), 1 << 20)):
                    # scan for ascii like 2020.3.45f1c1
                    if data[i] >= 0x30 and data[i] <= 0x39:
                        s = data[i:i + 40].split(b"\x00")[0]
                        try:
                            t = s.decode("ascii")
                        except Exception:
                            continue
                        if t[0:4].isdigit() and len(t) >= 6 and t[4] == ".":
                            return t.strip()
    return None


def add_dir(zf, dst, src_root, existing, prefix="assets", exclude=None):
    exclude = exclude or set()
    for root, dirs, files in os.walk(src_root):
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), src_root).replace(os.sep, "/")
            entry = f"{prefix}/{rel}/"
            if entry not in existing:
                zi = zipfile.ZipInfo(entry)
                zf.writestr(zi, b"")
                existing.add(entry)
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), src_root).replace(os.sep, "/")
            entry = f"{prefix}/{rel}"
            if rel in exclude:
                print(f"[skip] {entry}")
                continue
            if entry in existing:
                continue
            zf.write(os.path.join(root, f), entry, compress_type=zipfile.ZIP_STORED)
            existing.add(entry)


def patch(in_apk, out_apk, resources, unity_libs_url=None, libunity=None):
    so_dir = os.path.join(resources, "so")
    dotnet_dir = os.path.join(resources, "dotnet")
    bepinex_dir = os.path.join(resources, "BepInEx")

    for p in (so_dir, dotnet_dir, bepinex_dir):
        if not os.path.isdir(p):
            raise SystemExit(f"Missing resources dir: {p}")

    version = detect_unity_version(in_apk)
    if version:
        print(f"[info] detected Unity version: {version}")

    # ensure unity-libs zip
    ul = os.path.join(bepinex_dir, "unity-libs")
    os.makedirs(ul, exist_ok=True)
    chosen_zip = None
    zips = sorted(f for f in os.listdir(ul) if f.endswith(".zip"))
    if not zips and unity_libs_url:
        import urllib.request
        resolved = unity_libs_url.format(version=version or "0.0.0")
        target = os.path.join(ul, f"{version}.zip" if version else "unity-libs.zip")
        print(f"[info] downloading unity-libs: {resolved}")
        urllib.request.urlretrieve(resolved, target)
        zips = [os.path.basename(target)]
    if zips:
        # pick by exact version prefix first, else fall back to first available
        if version:
            base = version.split("f")[0]  # 2020.3.38f1 -> 2020.3.38
            chosen_zip = next((z for z in zips if z.startswith(base)), None)
        chosen_zip = chosen_zip or zips[0]
        print(f"[info] using unity-libs: {chosen_zip}")
    # exclude any unity-libs zips that are NOT chosen (only embed the matching one)
    excluded = {f"unity-libs/{z}" for z in zips if z != chosen_zip}

    tmp = out_apk + ".tmp"
    existing = set()
    skip = set(SKIP_EXACT)
    if libunity:
        skip.add("lib/arm64-v8a/libunity.so")
        print(f"[info] will replace lib/arm64-v8a/libunity.so with: {libunity}")
    with zipfile.ZipFile(in_apk) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        # 1. copy all entries except the ones we replace
        for info in src.infolist():
            if info.filename in skip:
                continue
            dst.writestr(info, src.read(info.filename))
            existing.add(info.filename)

        # 2. inject so files (stored / uncompressed)
        for so in SO_FILES:
            entry = f"lib/arm64-v8a/{so}"
            if entry in existing:
                print(f"[skip] {entry}")
                continue
            path = os.path.join(so_dir, so)
            if not os.path.isfile(path):
                print(f"[warn] missing so: {path}")
                continue
            dst.write(path, entry, compress_type=zipfile.ZIP_STORED)
            existing.add(entry)
            print(f"[add] {entry}")

        # 2b. replace libunity.so with custom unstripped version
        if libunity:
            entry = "lib/arm64-v8a/libunity.so"
            dst.write(libunity, entry, compress_type=zipfile.ZIP_STORED)
            existing.add(entry)
            print(f"[add] {entry} (custom)")

        # 3. embed assets: dotnet + BepInEx
        add_dir(dst, "", dotnet_dir, existing, prefix="assets/dotnet")
        add_dir(dst, "", bepinex_dir, existing, prefix="assets/BepInEx",
                exclude=excluded)

    shutil.move(tmp, out_apk)
    print(f"[done] patched -> {out_apk}")


def sign(apk, keystore, keystore_pass="android", alias="androiddebugkey",
         build_tools=None, min_sdk=24):
    apksigner = shutil.which("apksigner") or (build_tools and os.path.join(
        build_tools, "apksigner.bat"))
    zipalign = shutil.which("zipalign") or (build_tools and os.path.join(
        build_tools, "zipalign.exe"))
    if not apksigner or not zipalign:
        raise SystemExit("apksigner/zipalign not found; install Android build-tools or pass --build-tools")

    aligned = apk + ".aligned"
    subprocess.run([zipalign, "-f", "-p", "4", apk, aligned], check=True)
    os.replace(aligned, apk)

    cmd = [apksigner, "sign", "--ks", keystore, f"--ks-pass=pass:{keystore_pass}",
           f"--ks-key-alias={alias}", f"--min-sdk-version={min_sdk}",
           f"--out={apk}.signed", apk]
    subprocess.run(cmd, check=True)
    os.replace(apk + ".signed", apk)
    subprocess.run([apksigner, "verify", apk], check=True)
    print(f"[done] signed -> {apk}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_apk")
    ap.add_argument("out_apk")
    ap.add_argument("--resources", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources"))
    ap.add_argument("--unity-libs-url", default="https://unity.bepinex.dev/libraries/{version}.zip")
    ap.add_argument("--sign", action="store_true")
    ap.add_argument("--keystore", default=os.path.expanduser("~/.android/debug.keystore"))
    ap.add_argument("--build-tools", default=None)
    ap.add_argument("--libunity", default=None,
                    help="Path to a custom (unstripped) libunity.so to replace the game's one")
    args = ap.parse_args()

    url = args.unity_libs_url
    patch(args.in_apk, args.out_apk, args.resources, unity_libs_url=url, libunity=args.libunity)
    if args.sign:
        sign(args.out_apk, args.keystore, build_tools=args.build_tools)


if __name__ == "__main__":
    main()
