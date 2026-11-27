# -*- coding: utf-8 -*-
"""CC 收尾清理：把我在会话中开过的/导致的进程全部杀干净（杀进程树）。

用法: python tools/cc_cleanup.py [--all]
  默认：僵尸 msedge（H5 测试残留）+ 疑似小游戏渲染进程提示
  --all：连微信开发者工具一起关（工程文件不受影响）

为什么存在：2026-11-27 声音事故三连——僵尸 Edge 打鼓 / 模拟器自动战斗 /
研究用小游戏窗口的渲染子进程在窗口被裸杀后继续放 BGM。教训：**杀任何
进程都用 taskkill /T /F，杀完必须复查进程列表确认归零**（坑 #28/#29）。
"""
import subprocess
import sys


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception:
        return None


def count(name):
    r = run(['tasklist', '/FI', 'IMAGENAME eq %s' % name])
    if not r or not r.stdout:
        return 0
    return r.stdout.upper().count(name.upper())


def tree_kill(name, label):
    n0 = count(name)
    if n0 == 0:
        print('[%s] 无进程' % label)
        return
    run(['taskkill', '/IM', name, '/T', '/F'])
    n1 = count(name)
    print('[%s] %d -> %d %s' % (label, n0, n1, 'OK' if n1 == 0 else '!!! 未清零'))


def main():
    # ① 僵尸 Edge：我的 H5 测试脚本会留（脚本已自带 taskkill，这里是兜底）
    tree_kill('msedge.exe', 'Edge')

    # ② 微信开发者工具（--all 时才关）：注意会连着模拟器一起关
    if '--all' in sys.argv:
        tree_kill('微信开发者工具.exe', '开发者工具')

    # ③ WeChatAppEx：微信自己的内嵌浏览器，不能全杀（会断张凯的微信内页面）。
    #    只报告：大内存 renderer 可能是残留的小游戏，人确认后手动杀
    r = run(['powershell', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process -Filter \"Name='WeChatAppEx.exe'\" | "
             "Where-Object { $_.CommandLine -match 'type=renderer' } | "
             "ForEach-Object { Write-Output ($_.ProcessId.ToString() + ' ' + "
             "[Math]::Round($_.WorkingSetSize/1MB).ToString() + 'MB ' + "
             "($_.CommandLine -replace '.*wmpf-render-type=(\\d+).*','rt=$1')) }"])
    print('[WeChatAppEx renderer] 存活（微信自用，勿全杀；大内存+rt≠7 可能是小游戏残留）:')
    if r and r.stdout:
        for line in r.stdout.strip().splitlines():
            print('   ', line)
    else:
        print('    (无)')
    print('清理完成。')


if __name__ == '__main__':
    main()
