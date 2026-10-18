"""圆周率计算器 —— 手机版（Kivy）入口，用于打包 Android APK。

用法：
    1) 下拉框选算法：1 递推版 / 2 阶乘版 / 3 两者对比
    2) 填位数（默认 20）
    3) 点「开始计算」

计算放在后台线程执行，位数很大时界面也不会卡死。
"""

import threading
import time
from decimal import Decimal, getcontext
from math import factorial
from os.path import exists

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

# ------------------------------------------------------------------
# Chudnovsky 常量
# ------------------------------------------------------------------

A = 13591409
B = 545140134
C_CUBED = 640320 ** 3  # 262537412640768000

RECURSIVE = "1"
FACTORIAL = "2"
COMPARE = "3"

DEFAULT_DIGITS = 20
WRAP_WIDTH = 48  # 手机屏幕窄，每行少放几位


# ------------------------------------------------------------------
# 两种算法
# ------------------------------------------------------------------


def compute_pi_recursive(digits: int):
    """递推版：由上一项推下一项，不重算阶乘。返回 (pi, 累加项数)。"""
    if digits < 0:
        raise ValueError("digits 必须是非负整数")

    getcontext().prec = digits + 15  # 递推会累积舍入误差，多留些余量
    iterations = digits // 14 + 2

    total = Decimal(0)
    term = Decimal(A)  # k = 0 项

    for k in range(iterations):
        total += term
        if k == iterations - 1:
            break

        num = 1  # (6k+1)(6k+2)...(6k+6)
        for i in range(1, 7):
            num *= 6 * k + i

        # (3k+1)(3k+2)(3k+3) * (k+1)^3 * 640320^3
        den = (3 * k + 1) * (3 * k + 2) * (3 * k + 3) * (k + 1) ** 3 * C_CUBED

        term = -term * num / den * (A + B * (k + 1)) / (A + B * k)

    c = Decimal(426880) * Decimal(10005).sqrt()
    return c / total, iterations


def compute_pi_factorial(digits: int):
    """阶乘版：每轮重算 (6k)!、(3k)!、(k!)^3。返回 (pi, 累加项数)。"""
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


ALGORITHMS = {
    RECURSIVE: ("递推版", compute_pi_recursive),
    FACTORIAL: ("阶乘版", compute_pi_factorial),
}


def format_result(value: Decimal, digits: int, width: int = WRAP_WIDTH) -> str:
    """按 digits 位四舍五入，长数字按 width 折行。"""
    s = str(+value.quantize(Decimal(1).scaleb(-digits)))
    integer, _, frac = s.partition(".")
    if not frac or len(frac) <= width:
        return s
    lines = [integer + "."]
    for i in range(0, len(frac), width):
        lines.append("  " + frac[i : i + width])
    return "\n".join(lines)


def compute(key: str, digits: int) -> str:
    """按选择执行计算，返回要显示的文本。"""
    if digits < 0:
        raise ValueError("位数不能为负")

    if key == COMPARE:
        parts = [f"对比模式：两种算法各算到小数点后 {digits} 位", ""]
        results, timings = {}, {}
        for k, (name, fn) in ALGORITHMS.items():
            start = time.perf_counter()
            value, terms = fn(digits)
            timings[k] = time.perf_counter() - start
            results[k] = str(+value.quantize(Decimal(1).scaleb(-digits)))

            parts.append(f"【{name}】")
            parts.append(format_result(value, digits))
            parts.append(f"累加 {terms} 项 | 耗时 {timings[k]:.3f} 秒")
            parts.append("")

        same = results[RECURSIVE] == results[FACTORIAL]
        parts.append("结果一致性：" + ("一致" if same else "不一致"))
        r, f = timings[RECURSIVE], timings[FACTORIAL]
        if r > 0 and f > 0:
            ratio = f / r
            verdict = (
                f"递推版快 {ratio:.1f}x"
                if ratio >= 1
                else f"位数太小，阶乘版反而快 {1 / ratio:.1f}x"
            )
            parts.append(f"耗时：递推版 {r:.3f}s | 阶乘版 {f:.3f}s | {verdict}")

        if not same:
            for i, (x, y) in enumerate(zip(results[RECURSIVE], results[FACTORIAL])):
                if x != y:
                    parts.append(f"首个差异在第 {i - 2} 位小数：{x} vs {y}")
                    break
        return "\n".join(parts)

    name, fn = ALGORITHMS[key]
    start = time.perf_counter()
    value, terms = fn(digits)
    elapsed = time.perf_counter() - start
    return "\n".join(
        [
            f"【{name}】圆周率（小数点后 {digits} 位）：",
            format_result(value, digits),
            "",
            f"累加 {terms} 项 | 耗时 {elapsed:.3f} 秒",
        ]
    )


# ------------------------------------------------------------------
# 界面
# ------------------------------------------------------------------


def setup_cjk_font():
    """Android 默认字体不含中文，注册一个系统自带的 CJK 字体，否则汉字会变方块。"""
    for path in (
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansSC-Regular.otf",
        "/system/fonts/SourceHanSansCN-Regular.otf",
        "/system/fonts/DroidSansFallback.ttf",
        "/system/fonts/Miui-Regular.ttf",
    ):
        if exists(path):
            try:
                LabelBase.register("Roboto", fn_regular=path)
                return path
            except Exception:
                continue
    return None


class PiRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(14), spacing=dp(10), **kwargs)

        self.add_widget(
            Label(text="圆周率计算器", font_size=dp(21), size_hint_y=None, height=dp(38))
        )

        self.algo = Spinner(
            text="1 - 递推版（推荐）",
            values=["1 - 递推版（推荐）", "2 - 阶乘版", "3 - 两者对比"],
            size_hint_y=None,
            height=dp(44),
            font_size=dp(15),
        )
        self.add_widget(self.algo)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        row.add_widget(Label(text="位数", size_hint_x=None, width=dp(52), font_size=dp(15)))
        self.digits_input = TextInput(
            text=str(DEFAULT_DIGITS),
            multiline=False,
            input_filter="int",
            font_size=dp(15),
            halign="center",
        )
        row.add_widget(self.digits_input)
        self.add_widget(row)

        self.btn = Button(text="开始计算", size_hint_y=None, height=dp(48), font_size=dp(16))
        self.btn.bind(on_release=self.on_calculate)
        self.add_widget(self.btn)

        self.out = Label(
            text="选择算法、填入位数，然后点击上方按钮",
            font_size=dp(13),
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        self.out.bind(texture_size=self._sync_height)
        self.bind(width=self._sync_text_size)
        self._sync_text_size(self, self.width)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll.add_widget(self.out)
        self.add_widget(scroll)

    # -- 让 Label 能正确换行并撑开高度，从而可滚动 --
    def _sync_text_size(self, instance, value):
        self.out.text_size = (max(value - dp(24), dp(10)), None)

    def _sync_height(self, instance, value):
        instance.height = max(value[1], dp(1))

    # -- 交互 --
    def on_calculate(self, *args):
        raw = (self.digits_input.text or "").strip()
        digits = int(raw) if raw.isdigit() else DEFAULT_DIGITS
        key = self.algo.text[:1]

        self.btn.disabled = True
        self.btn.text = "计算中…"
        self.out.text = "计算中，请稍候…"
        threading.Thread(target=self._worker, args=(key, digits), daemon=True).start()

    def _worker(self, key, digits):
        try:
            text = compute(key, digits)
        except Exception as exc:  # 不让它崩掉整个 App
            text = "计算出错：%r" % (exc,)
        Clock.schedule_once(lambda dt: self._done(text))

    def _done(self, text):
        self.out.text = text
        self.btn.text = "开始计算"
        self.btn.disabled = False


class PiApp(App):
    title = "圆周率计算器"

    def build(self):
        setup_cjk_font()
        return PiRoot()


if __name__ == "__main__":
    PiApp().run()
