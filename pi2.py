"""圆周率计算的「递推版」——pi.py 的高性能替代。

pi.py 每一轮都重算 (6k)!、(3k)!、(k!)^3 这些巨型整数，位数一大就慢得离谱。
本文件改成由上一项直接推出下一项，每轮只做十几次小整数乘除。

Chudnovsky 级数（把 640320^(3/2) 抽出来当常数）：

    S = sum_k (-1)^k * (6k)! * (A + Bk) / ((3k)! * (k!)^3 * 640320^(3k))
    pi = 426880 * sqrt(10005) / S            其中 A = 13591409, B = 545140134

相邻两项之比：

    term_{k+1} / term_k =
        - [(6k+1)(6k+2)(6k+3)(6k+4)(6k+5)(6k+6)]
        / [(3k+1)(3k+2)(3k+3) * (k+1)^3 * 640320^3]
        * (A + B(k+1)) / (A + Bk)

初值 term_0 = A = 13591409。每项仍能带来约 14 位有效数字。

用法：
    python pi2.py            # 默认 20 位
    python pi2.py 1000       # 算到 1000 位
"""

import atexit
import os
import sys
import time
from decimal import Decimal, getcontext
import time
# ---- 输出编码与双击暂停的处理与 pi.py 保持一致（脚本保持自包含）----


def setup_stdout() -> bool:
    """让 stdout 以 UTF-8 输出；返回 True 表示可以安全打印中文。"""
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
        return False


def _parent_process_name() -> str:
    """返回父进程的可执行文件名（小写）；获取失败时返回空字符串。"""
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
    """只有「在资源管理器里双击 .py 启动」时才暂停等按键。"""
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


# ------------------------------------------------------------------
# 核心算法
# ------------------------------------------------------------------

A = 13591409
B = 545140134
C_CUBED = 640320 ** 3  # 262537412640768000


def compute_pi(digits: int) -> tuple:
    """递推版 Chudnovsky。返回 (圆周率, 累加项数)。"""
    if digits < 0:
        raise ValueError("digits 必须是非负整数")

    # 递推会累积舍入误差，余量比 pi.py 多留一些
    getcontext().prec = digits + 15

    iterations = digits // 14 + 2

    total = Decimal(0)
    term = Decimal(A)  # k = 0 项

    for k in range(iterations):
        total += term
        if k == iterations - 1:
            break

        # 分子：(6k+1)(6k+2)...(6k+6)
        num = 1
        for i in range(1, 7):
            num *= 6 * k + i

        # 分母：(3k+1)(3k+2)(3k+3) * (k+1)^3 * 640320^3
        den = (3 * k + 1) * (3 * k + 2) * (3 * k + 3) * (k + 1) ** 3 * C_CUBED

        term = -term * num / den * (A + B * (k + 1)) / (A + B * k)

    c = Decimal(426880) * Decimal(10005).sqrt()
    return c / total, iterations


def print_number(value: Decimal, width: int = 64) -> None:
    """整数部分单独一行，小数部分每行 width 位，长数字也好看。"""
    s = str(value)
    integer, _, frac = s.partition(".")
    if not frac or len(frac) <= width:
        print(s)
        return
    print(f"{integer}.")
    for i in range(0, len(frac), width):
        print("  " + frac[i : i + width])


def parse_digits(argv: list, zh: bool) -> int:
    """解析命令行参数：只接受一个非负整数位数。"""
    if argv and argv[0] in ("-h", "--help"):
        if zh:
            print("用法：python pi2.py [位数]")
            print("示例：python pi2.py        # 默认 20 位")
            print("      python pi2.py 1000   # 算到小数点后 1000 位")
        else:
            print("Usage: python pi2.py [digits]")
            print("Example: python pi2.py 1000")
        raise SystemExit(0)
    b=int(input('输入你要算到圆周率第几位：'))
    digits = b
    if argv:
        try:
            digits = int(argv[0])
        except ValueError:
            print("[ERROR] 位数必须是整数" if zh else "[ERROR] digits must be an integer")
            raise SystemExit(2)
        if digits < 0:
            print("[ERROR] 位数不能为负" if zh else "[ERROR] digits must be >= 0")
            raise SystemExit(2)
    return digits


def main() -> None:
    zh = setup_stdout()
    digits = parse_digits(sys.argv[1:], zh)

    start = time.perf_counter()
    pi, iterations = compute_pi(digits)
    elapsed = time.perf_counter() - start

    quantized = +pi.quantize(Decimal(1).scaleb(-digits))

    if zh:
        print(f"圆周率（小数点后 {digits} 位）：")
        print_number(quantized)
        print()
        print(f"累加 {iterations} 项 | 耗时 {elapsed:.3f} 秒")
    else:
        print(f"pi to {digits} decimal places:")
        print_number(quantized)
        print()
        print(f"{iterations} terms | {elapsed:.3f}s")

    pause_if_double_clicked(zh)


if __name__ == "__main__":
    main()
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