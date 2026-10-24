# BepInEx.Android.Patch.RainWorld

**English** | [中文](README.md)

A BepInEx APK injection patch tool specifically for the Rain World 1.9 port

## Changes from upstream

- `libmain.so`: encodes `unityVersion=2020.3.38`
- Bundled `RainWorldCwdFix` plugin: fixes the game's relative path resolution (process CWD is pinned to `/`) and cleans up `clr-debug-pipe-*` junk files
- `BepInEx.cfg`: `UnityLogListening = false`
- `unity-libs`: pinned to 2020.3.38
- `Il2CppInterop.Runtime.dll`: removed the GenericMethod hook

## License

GNU General Public License v3.0 (see [LICENSE](LICENSE))

The injection chain is inherited from [BepInEx.Android.Launcher](https://github.com/NextBep/BepInEx.Android.Launcher) (GPL-3.0) and [BepInEx.Android](https://github.com/NextBep/BepInEx.Android) (LGPL-2.1)
