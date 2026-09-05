using System;
using System.IO;
using System.Threading;
using BepInEx;
using BepInEx.Unity.IL2CPP;

namespace RainWorldCwdFix;

[BepInPlugin("rw.cwdfix", "Rain World CWD Fix", "1.1.0")]
public class CwdFixPlugin : BasePlugin
{
    // Candidate roots where CoreCLR's diagnostics server may drop
    // clr-debug-pipe-<pid>-<rand>-in / -out FIFOs. Cover internal+external.
    private static readonly string[] ScanRoots =
    {
        "/data/data/com.Videocult.RainWorld/files",
        "/data/user/0/com.Videocult.RainWorld/files",
        "/storage/emulated/0/Android/data/com.Videocult.RainWorld/files",
        "/storage/emulated/0/Rain World",
        Environment.CurrentDirectory,
    };

    public override void Load()
    {
        // 1) CWD: game resolves RELATIVE streaming-assets paths against the
        //    process working directory. BepInEx chdir()s during bootstrap,
        //    so restore CWD to filesystem root here and keep it fixed.
        FixCwd();
        CleanPipes();

        var t = new Thread(() =>
        {
            try
            {
                for (; ; )
                {
                    Thread.Sleep(3000);
                    FixCwd();
                    CleanPipes();
                }
            }
            catch { }
        });
        t.IsBackground = true;
        t.Start();
    }

    private static void FixCwd()
    {
        try
        {
            if (Environment.CurrentDirectory != "/")
                Environment.CurrentDirectory = "/";
        }
        catch { }
    }

    private static void CleanPipes()
    {
        foreach (var root in ScanRoots)
        {
            try
            {
                if (string.IsNullOrEmpty(root) || !Directory.Exists(root))
                    continue;

                // Only files directly inside each root; CoreCLR drops them at CWD.
                foreach (var f in Directory.GetFiles(root, "clr-debug-pipe-*"))
                {
                    try { File.Delete(f); } catch { }
                }
            }
            catch { }
        }
    }
}