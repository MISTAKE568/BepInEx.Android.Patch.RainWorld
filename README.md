# BepInEx.Android.Patch.RainWorld

对雨世界1.9移植版专用的 BepInEx 注入 APK patch 工具

## 对上游的修改

- `libmain.so`：编码 `unityVersion=2020.3.38`
- 内置 `RainWorldCwdFix` 插件：修复游戏相对路径解析（进程 CWD 固定为 `/`），并清理 `clr-debug-pipe-*` 垃圾文件
- `BepInEx.cfg`：`UnityLogListening = false`
- `unity-libs`：固定 2020.3.38

## 许可证

GNU General Public License v3.0（见 [LICENSE](LICENSE)）

注入链继承自 [BepInEx.Android.Launcher](https://github.com/NextBep/BepInEx.Android.Launcher)（GPL-3.0）与 [BepInEx.Android](https://github.com/NextBep/BepInEx.Android)（LGPL-2.1）
