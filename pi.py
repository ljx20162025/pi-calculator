"""计算圆周率到小数点后指定位数（默认 20 位）。

使用 Chudnovsky 算法 + decimal 高精度十进制运算：

    1/pi = 12 * sum_{k=0}^{inf} (-1)^k * (6k)! * (13591409 + 545140134k)
                                        / ((3k)! * (k!)^3 * 640320^(3k+3/2))

每一项约带来 14 位有效数字，收敛极快。
"""

import atexit
import os
import sys
from decimal import Decimal, getcontext
from math import factorial
import time

def setup_stdout() -> bool:
    """让 stdout 以 UTF-8 输出；返回 True 表示可以安全打印中文。

    Windows 的 cmd/PowerShell 默认代码页是 GBK(936)，直接打印 UTF-8 中文会乱码，
    因此先把控制台输出代码页切到 65001(UTF-8)，退出时再恢复原值，
    最后把 stdout 编码改成 utf-8（保证重定向到文件时也是 UTF-8）。
    """
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            original = kernel32.GetConsoleOutputCP()
            # 对 cmd / PowerShell / Windows Terminal 有效；管道或重定向时为 0，跳过
            if 0 < original != 65001:
                kernel32.SetConsoleOutputCP(65001)
                atexit.register(kernel32.SetConsoleOutputCP, original)
        except Exception:
            pass

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        return True
    except Exception:
        return False  # 很老的 Python 没有 reconfigure：退回纯 ASCII 提示


def _parent_process_name() -> str:
    """返回父进程的可执行文件名（小写）；获取失败时返回空字符串。

    用 os.getppid() 拿父进程 PID，再用 Toolhelp32 进程快照查它的 exe 名——
    不需要 OpenProcess 权限，比 NtQueryInformationProcess 稳得多。
    """
    if not hasattr(os, "getppid"):
        return ""

    try:
        import ctypes
        from ctypes import wintypes

        ppid = os.getppid()
        if ppid <= 0:
            return ""

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32")
        # 64 位 Python 上必须显式声明，否则 HANDLE 参数会被截断成 32 位
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32FirstW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESSENTRY32W),
        ]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESSENTRY32W),
        ]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        # TH32CS_SNAPPROCESS = 0x00000002
        snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            return ""
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                while True:
                    if entry.th32ProcessID == ppid:
                        return entry.szExeFile.lower()
                    if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass

    return ""


def pause_if_double_clicked(zh: bool) -> None:
    """只有「在资源管理器里双击 .py 启动」时才暂停等按键，防止窗口一闪而过。

    在 VS Code 集成终端、cmd/PowerShell 里手动执行、或输出被重定向时都不会暂停。
    """
    if os.name != "nt":
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return
    if _parent_process_name() != "explorer.exe":
        return

    print()
    print("（计算完毕，按任意键关闭窗口）" if zh else "(Done, press any key to close)")
    try:
        import msvcrt

        msvcrt.getwch()
    except Exception:
        try:
            input()
        except Exception:
            pass


def compute_pi(digits: int) -> Decimal:
    """返回圆周率，保证小数点后至少 digits 位正确。"""
    if digits < 0:
        raise ValueError("digits 必须是非负整数")

    # 多留 10 位作为计算过程中的舍入余量
    getcontext().prec = digits + 10

    # 需要的项数：每项约 14.18 位
    iterations = digits // 14 + 2

    total = Decimal(0)
    for k in range(iterations):
        numerator = factorial(6 * k) * (13591409 + 545140134 * k)
        denominator = factorial(3 * k) * (factorial(k) ** 3) * (640320 ** (3 * k))
        term = Decimal(numerator) / Decimal(denominator)
        if k % 2 == 1:
            term = -term
        total += term

    # 再乘上公式尾部常数 12 / 640320^(3/2) = 1 / (426880 * sqrt(10005))
    c = Decimal(426880) * Decimal(10005).sqrt()
    return c / total


def main(a) -> None:
    zh = setup_stdout()  # 先修好控制台编码，再打印任何中文

    digits = a
    pi = compute_pi(digits)

    # 按 digits 位量化输出（会自动四舍五入到该精度）
    quantized = +pi.quantize(Decimal(1).scaleb(-digits))

    if zh:
        print(f"圆周率（小数点后 {digits} 位）：")
        print(quantized)
        print()
        print(f"共 {digits} 位小数（不含整数部分与小数点）")
    else:
        print(f"pi to {digits} decimal places:")
        print(quantized)
        print()
        print(f"{digits} digits after the decimal point")

    pause_if_double_clicked(zh)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
    time.sleep(999)
if __name__ == "__main__":
    b=int(input('输入你要算到圆周率第几位'))
    main(b)
