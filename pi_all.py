"""圆周率计算器：递推版 + 阶乘版 二合一（带交互菜单）。

打开后自行选择算法：

    1 -> 递推版   Chudnovsky 逐项递推，不重算阶乘，位数大时快得多（推荐）
    2 -> 阶乘版   每轮重算 (6k)!、(3k)!、(k!)^3，直观体现公式本身
    3 -> 两者对比 两种算法各算一遍，校验结果是否一致并给出耗时 / 加速比

命令行用法（给参数就跳过菜单，方便脚本调用 / 重定向）：

    python pi_all.py            # 交互菜单
    python pi_all.py 1          # 递推版，默认 20 位
    python pi_all.py 1 1000     # 递推版，1000 位
    python pi_all.py 3 5000     # 对比，5000 位
    python pi_all.py -h

公式（Chudnovsky）：

    S   = sum_k (-1)^k (6k)! (A + Bk) / ((3k)! (k!)^3 640320^(3k))
    pi  = 426880 * sqrt(10005) / S        其中 A = 13591409, B = 545140134

递推版用的相邻项之比：

    term_{k+1} / term_k =
        - [(6k+1)(6k+2)(6k+3)(6k+4)(6k+5)(6k+6)]
        / [(3k+1)(3k+2)(3k+3) (k+1)^3 640320^3] * (A + B(k+1)) / (A + Bk)
"""

import atexit
import os
import sys
import time
from decimal import Decimal, getcontext
from math import factorial
from typing import Optional, Tuple

# ==================================================================
# 常量
# ==================================================================

A = 13591409
B = 545140134
C_CUBED = 640320 ** 3  # 262537412640768000

RECURSIVE = "1"
FACTORIAL = "2"
COMPARE = "3"

KEY_NAMES_ZH = {RECURSIVE: "递推版", FACTORIAL: "阶乘版", COMPARE: "两者对比"}
KEY_NAMES_EN = {RECURSIVE: "recursive", FACTORIAL: "factorial", COMPARE: "compare"}

DEFAULT_DIGITS = 20
# 阶乘版在这个规模以上明显变慢，对比模式会先提示
SLOW_THRESHOLD = 20000


# ==================================================================
# 控制台输出：UTF-8 编码 + 双击暂停（与 pi.py / pi2.py 保持一致）
# ==================================================================


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

    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    try:
        return sys.stdout.encoding.lower().replace("-", "") == "utf8"
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
    print("（按任意键关闭窗口）" if zh else "(Press any key to close)")
    try:
        import msvcrt

        msvcrt.getwch()
    except Exception:
        try:
            input()
        except Exception:
            pass


# ==================================================================
# 两种算法
# ==================================================================


def compute_pi_recursive(digits: int) -> Tuple[Decimal, int]:
    """递推版：由上一项推下一项，不重算阶乘。返回 (pi, 累加项数)。"""
    if digits < 0:
        raise ValueError("digits 必须是非负整数")

    getcontext().prec = digits + 15  # 递推会累积舍入误差，多留些余量
    iterations = digits // 14 + 2

    total = Decimal(0)
    term = Decimal(A)  # k = 0 项，term_0 = A

    for k in range(iterations):
        total += term
        if k == iterations - 1:
            break

        num = 1  # 分子：(6k+1)(6k+2)...(6k+6)
        for i in range(1, 7):
            num *= 6 * k + i

        # 分母：(3k+1)(3k+2)(3k+3) * (k+1)^3 * 640320^3
        den = (3 * k + 1) * (3 * k + 2) * (3 * k + 3) * (k + 1) ** 3 * C_CUBED

        term = -term * num / den * (A + B * (k + 1)) / (A + B * k)

    c = Decimal(426880) * Decimal(10005).sqrt()
    return c / total, iterations


def compute_pi_factorial(digits: int) -> Tuple[Decimal, int]:
    """阶乘版：每轮老老实实重算 (6k)!、(3k)!、(k!)^3。返回 (pi, 累加项数)。"""
    if digits < 0:
        raise ValueError("digits 必须是非负整数")

    getcontext().prec = digits + 10
    iterations = digits // 14 + 2

    total = Decimal(0)
    for k in range(iterations):
        numerator = factorial(6 * k) * (A + B * k)
        denominator = factorial(3 * k) * (factorial(k) ** 3) * (640320 ** (3 * k))
        term = Decimal(numerator) / Decimal(denominator)
        if k % 2 == 1:
            term = -term
        total += term

    c = Decimal(426880) * Decimal(10005).sqrt()
    return c / total, iterations


# ==================================================================
# 输出
# ==================================================================


def quantize(value: Decimal, digits: int) -> Decimal:
    """按 digits 位小数四舍五入。"""
    return +value.quantize(Decimal(1).scaleb(-digits))


def print_number(value: Decimal, width: int = 64) -> None:
    """整数部分单独一行，小数部分每行 width 位。"""
    s = str(value)
    integer, _, frac = s.partition(".")
    if not frac or len(frac) <= width:
        print(s)
        return
    print(f"{integer}.")
    for i in range(0, len(frac), width):
        print("  " + frac[i : i + width])


def run_once(key: str, digits: int, zh: bool) -> Tuple[str, float]:
    """跑一种算法，打印结果，返回 (结果字符串, 耗时秒)。"""
    name = KEY_NAMES_ZH[key] if zh else KEY_NAMES_EN[key]
    algo = compute_pi_recursive if key == RECURSIVE else compute_pi_factorial

    start = time.perf_counter()
    value, terms = algo(digits)
    elapsed = time.perf_counter() - start
    result = str(quantize(value, digits))

    print()
    if zh:
        print(f"【{name}】圆周率（小数点后 {digits} 位）：")
    else:
        print(f"[{name}] pi to {digits} decimal places:")
    print_number(result)
    print()
    if zh:
        print(f"累加 {terms} 项 | 耗时 {elapsed:.3f} 秒")
    else:
        print(f"{terms} terms | {elapsed:.3f}s")

    return result, elapsed


def run_compare(digits: int, zh: bool) -> None:
    """两种算法各跑一遍，校验一致性并给出性能对比。"""
    print()
    if zh:
        print(f"对比模式：两种算法各算到小数点后 {digits} 位")
    else:
        print(f"Compare mode: both algorithms to {digits} decimal places")

    r_result, r_time = run_once(RECURSIVE, digits, zh)
    f_result, f_time = run_once(FACTORIAL, digits, zh)

    same = r_result == f_result
    print()
    if zh:
        print("结果一致性：" + ("一致 ✓" if same else "不一致 ✗"))
    else:
        print("Results match: " + ("YES" if same else "NO"))

    if r_time > 0 and f_time > 0:
        ratio = f_time / r_time
        if zh:
            verdict = (
                f"递推版快 {ratio:.1f}x"
                if ratio >= 1
                else f"位数太小，阶乘版反而快 {1 / ratio:.1f}x"
            )
            print(f"耗时：递推版 {r_time:.3f}s | 阶乘版 {f_time:.3f}s | {verdict}")
        else:
            verdict = (
                f"recursive is {ratio:.1f}x faster"
                if ratio >= 1
                else f"too small, factorial is {1 / ratio:.1f}x faster"
            )
            print(f"Time: recursive {r_time:.3f}s | factorial {f_time:.3f}s | {verdict}")

    if not same:
        for i, (x, y) in enumerate(zip(r_result, f_result)):
            if x != y:
                pos = i - 2  # 减去 "3." 两个字符
                if zh:
                    print(f"首个差异在第 {pos} 位小数：递推版 {x} / 阶乘版 {y}")
                else:
                    print(f"first diff at decimal {pos}: {x} vs {y}")
                break


# ==================================================================
# 交互菜单
# ==================================================================


def print_menu(zh: bool) -> None:
    print()
    print("=" * 46)
    print("  圆周率计算器" if zh else "  Pi Calculator")
    print("=" * 46)
    if zh:
        print("  1 - 递推版（推荐，位数大时快很多）")
        print("  2 - 阶乘版（每轮重算阶乘，便于理解公式）")
        print("  3 - 两者对比（校验一致性 + 性能对比）")
        print("  q - 退出")
    else:
        print("  1 - recursive (fast, recommended)")
        print("  2 - factorial (recomputes factorials)")
        print("  3 - compare both")
        print("  q - quit")
    print("-" * 46)


def choose_mode(zh: bool) -> Optional[str]:
    """选择算法；返回 None 表示退出。"""
    while True:
        print_menu(zh)
        raw = input("请输入 1 / 2 / 3（回车退出）：" if zh else "Choose 1/2/3 (enter to quit): ").strip()
        if raw in ("", "q", "Q"):
            return None
        if raw in (RECURSIVE, FACTORIAL, COMPARE):
            return raw
        print("输入无效，请重新选择" if zh else "Invalid choice, try again")


def ask_digits(zh: bool) -> Optional[int]:
    """询问位数；直接回车用默认 20，返回 None 表示退出。"""
    while True:
        raw = input(f"位数（回车默认 {DEFAULT_DIGITS}）：" if zh else f"Digits (enter for {DEFAULT_DIGITS}): ").strip()
        if raw in ("", "q", "Q"):
            return None if raw else DEFAULT_DIGITS
        try:
            digits = int(raw)
        except ValueError:
            print("请输入整数" if zh else "Please enter an integer")
            continue
        if digits < 0:
            print("位数不能为负" if zh else "Digits must be >= 0")
            continue
        return digits


def ask_yes_no(prompt_zh: str, prompt_en: str, zh: bool, default_no: bool = True) -> bool:
    while True:
        raw = input(prompt_zh if zh else prompt_en).strip().lower()
        if raw == "":
            return not default_no
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("请输入 y 或 n" if zh else "Please enter y or n")


def print_usage(zh: bool) -> None:
    if zh:
        print("用法：python pi_all.py [算法] [位数]")
        print()
        print("  算法：1 = 递推版，2 = 阶乘版，3 = 两者对比（不给则进入交互菜单）")
        print("  位数：小数点后的位数，不给则默认 20")
        print()
        print("示例：")
        print("  python pi_all.py          # 交互菜单")
        print("  python pi_all.py 1 1000   # 递推版，1000 位")
        print("  python pi_all.py 3 5000   # 对比，5000 位")
    else:
        print("Usage: python pi_all.py [algorithm] [digits]")
        print()
        print("  algorithm: 1=recursive, 2=factorial, 3=compare (omit for menu)")
        print("  digits:    number of decimal places (omit for 20)")
        print()
        print("Examples:")
        print("  python pi_all.py 1 1000")
        print("  python pi_all.py 3 5000")


# ==================================================================
# 入口
# ==================================================================


def parse_cli(args: list, zh: bool) -> Tuple[Optional[str], int]:
    """解析命令行参数；返回 (算法或 None, 位数)。"""
    if not args:
        return None, DEFAULT_DIGITS

    if args[0] in ("-h", "--help"):
        print_usage(zh)
        raise SystemExit(0)

    key = args[0]
    if key not in (RECURSIVE, FACTORIAL, COMPARE):
        print("[ERROR] 算法只能是 1 / 2 / 3" if zh else "[ERROR] algorithm must be 1, 2 or 3")
        raise SystemExit(2)

    digits = DEFAULT_DIGITS
    if len(args) > 1:
        try:
            digits = int(args[1])
        except ValueError:
            print("[ERROR] 位数必须是整数" if zh else "[ERROR] digits must be an integer")
            raise SystemExit(2)
        if digits < 0:
            print("[ERROR] 位数不能为负" if zh else "[ERROR] digits must be >= 0")
            raise SystemExit(2)
    return key, digits


def main() -> None:
    zh = setup_stdout()
    args = sys.argv[1:]
    key, digits = parse_cli(args, zh)

    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if key is None and not interactive:
        # 没有参数、又不能交互（管道 / 重定向）：默认递推版 20 位
        key = RECURSIVE

    if key is not None:
        if key == COMPARE:
            run_compare(digits, zh)
        else:
            run_once(key, digits, zh)
    else:
        # 交互菜单
        while True:
            key = choose_mode(zh)
            if key is None:
                break
            digits = ask_digits(zh)
            if digits is None:
                break

            if key == COMPARE and digits > SLOW_THRESHOLD:
                ok = ask_yes_no(
                    f"阶乘版在 {digits} 位会比较慢，是否继续？(y/N)：",
                    f"Factorial will be slow at {digits} digits. Continue? (y/N): ",
                    zh,
                )
                if not ok:
                    continue

            if key == COMPARE:
                run_compare(digits, zh)
            else:
                run_once(key, digits, zh)

            if not ask_yes_no("继续计算？(y/N)：", "Calculate again? (y/N): ", zh):
                break

    pause_if_double_clicked(zh)


if __name__ == "__main__":
    main()
