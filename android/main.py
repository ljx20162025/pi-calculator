"""圆周率计算器 —— 手机版（Kivy）入口，用于打包 Android APK。

用法：
    1) 下拉框选算法：1 递推版 / 2 阶乘版 / 3 两者对比
    2) 填位数（默认 20）
    3) 点「开始计算」

计算放在后台线程执行，位数很大时界面也不会卡死。

显示为什么不用单个 Label：
    结果原先整体塞进一个 Label，Kivy 会为它生成一整张纹理。手机 GPU 的
    GL_MAX_TEXTURE_SIZE 通常是 16384，而按 48 位/行、约 48px 行高估算，
    纹理高度约等于位数本身 —— 于是超过约 16000 位时纹理超限，Kivy 静默
    放弃绘制（不报错，直接空白，看起来像"没算出来"）。
    这里改用 RecycleView：每一行是各自的小纹理，且只实例化屏幕上可见的
    那十几行，位数再大也不会超限。
"""

import threading
import time
from decimal import Decimal, getcontext
from math import factorial
from os.path import exists

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.text import Label as CoreLabel
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
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

# 手机内存有限，再大就很容易把 App 拖死。不是算法算不动，是设备扛不住。
MAX_DIGITS = 200000


def _font_size():
    return dp(13)


def _line_height():
    return dp(20)


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


def format_result(value: Decimal, digits: int) -> str:
    """按 digits 位四舍五入，返回单行字符串（折行交给界面处理）。"""
    return str(+value.quantize(Decimal(1).scaleb(-digits)))


def compute(key: str, digits: int) -> str:
    """按选择执行计算，返回要显示的文本。"""
    if digits < 0:
        raise ValueError("位数不能为负")
    if digits > MAX_DIGITS:
        raise ValueError("位数过大（上限 %d 位），手机内存扛不住" % MAX_DIGITS)

    if key == COMPARE:
        parts = [f"对比模式：两种算法各算到小数点后 {digits} 位", ""]
        results, timings = {}, {}
        for k, (name, fn) in ALGORITHMS.items():
            start = time.perf_counter()
            value, terms = fn(digits)
            timings[k] = time.perf_counter() - start
            results[k] = format_result(value, digits)

            parts.append(f"【{name}】")
            parts.append(results[k])
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


def hard_wrap(text: str, per_line: int):
    """把任意长文本切成不超过 per_line 的行，保留原有换行。"""
    if per_line < 1:
        per_line = 1
    out = []
    for para in text.split("\n"):
        if len(para) <= per_line:
            out.append(para)
        else:
            for i in range(0, len(para), per_line):
                out.append(para[i : i + per_line])
    return out


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


class LineLabel(Label):
    """结果区里的一行。

    每一行都是独立的小纹理，这是整个方案的关键：单个 Label 装下几万位
    数字会需要一张上万像素高的纹理，超过 GPU 纹理上限后 Kivy 不报错、
    直接不绘制。拆成逐行纹理后就没有这个天花板了。
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = _font_size()
        self.halign = "left"
        self.valign = "center"
        self.shorten = False
        self.markup = False
        self.size_hint_y = None
        self.height = _line_height()
        self.bind(width=self._update_text_size)
        self._update_text_size(self, self.width)

    def _update_text_size(self, *_):
        self.text_size = (max(self.width - dp(10), dp(10)), None)


class ResultView(RecycleView):
    """只实例化可见行的滚动结果区。"""

    def __init__(self, **kwargs):
        super().__init__(do_scroll_x=False, **kwargs)

        self._layout = RecycleBoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            default_size=(None, _line_height()),
            default_size_hint=(1, None),
            padding=(dp(6), dp(4)),
        )
        self._layout.bind(minimum_height=self._layout.setter("height"))
        # 顺序很重要：RecycleView.viewclass 是代理到 layout_manager 的
        # AliasProperty（见 kivy/uix/recycleview/__init__.py 的 _get_viewclass）。
        # 在 add_widget 之前赋值时 layout_manager 还是 None，赋值会被静默丢掉，
        # 结果整片空白且不报错。必须先挂上布局，再设 viewclass。
        self.add_widget(self._layout)
        self.viewclass = "LineLabel"

        self._raw = ""
        self.data = [{"text": "选择算法、填入位数，然后点击上方按钮"}]
        self.bind(width=self._rewrap)

    # -- 按当前宽度估算一行能放几个字符 --
    def _chars_per_line(self):
        size = _font_size()
        try:
            probe = CoreLabel(text="0" * 64, font_size=size)
            probe.refresh()
            char_w = probe.texture.size[0] / 64.0
        except Exception:
            char_w = size * 0.6
        usable = max(self.width - dp(24), dp(40))
        return max(8, int(usable / max(char_w, 0.5)))

    def set_text(self, text: str):
        self._raw = text
        self._rewrap(self, self.width)
        # 滚动边界要到下一帧布局算完才更新，现在就设 scroll_y 会被旧边界夹紧，
        # 结果开头几行被卷到视野外面。推迟一帧再回到顶部。
        Clock.schedule_once(lambda dt: setattr(self, "scroll_y", 1.0), 0)

    def _rewrap(self, *_):
        if not self._raw:
            return
        per_line = self._chars_per_line()
        self.data = [{"text": chunk} for chunk in hard_wrap(self._raw, per_line)]


class PiRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(14), spacing=dp(8), **kwargs)

        self.add_widget(
            Label(text="圆周率计算器", font_size=dp(21), size_hint_y=None, height=dp(34))
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

        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.btn = Button(text="开始计算", font_size=dp(16))
        self.btn.bind(on_release=self.on_calculate)
        btn_row.add_widget(self.btn)

        self.copy_btn = Button(
            text="复制", size_hint_x=None, width=dp(70), font_size=dp(14), disabled=True
        )
        self.copy_btn.bind(on_release=self.on_copy)
        btn_row.add_widget(self.copy_btn)
        self.add_widget(btn_row)

        self.status = Label(
            text="", size_hint_y=None, height=dp(20), font_size=dp(12), halign="left"
        )
        self.add_widget(self.status)

        self.out = ResultView(size_hint=(1, 1))
        self.add_widget(self.out)

    # -- 交互 --
    def on_copy(self, *args):
        text = self.out._raw
        if not text:
            return
        try:
            Clipboard.copy(text)
            self.status.text = "已复制完整结果（%d 个字符）" % len(text)
        except Exception as exc:
            self.status.text = "复制失败：%r" % (exc,)

    def on_calculate(self, *args):
        raw = (self.digits_input.text or "").strip()
        digits = int(raw) if raw.isdigit() else DEFAULT_DIGITS
        key = self.algo.text[:1]

        self.btn.disabled = True
        self.btn.text = "计算中…"
        self.copy_btn.disabled = True
        self.status.text = ""
        self.out.data = [{"text": "计算中，请稍候…"}]
        self.out._raw = ""
        threading.Thread(target=self._worker, args=(key, digits), daemon=True).start()

    def _worker(self, key, digits):
        try:
            text = compute(key, digits)
        except Exception as exc:  # 不让它崩掉整个 App
            text = "计算出错：%r" % (exc,)
        Clock.schedule_once(lambda dt: self._done(text))

    def _done(self, text):
        self.out.set_text(text)
        self.btn.text = "开始计算"
        self.btn.disabled = False
        self.copy_btn.disabled = False


class PiApp(App):
    title = "圆周率计算器"

    def build(self):
        setup_cjk_font()
        return PiRoot()


if __name__ == "__main__":
    PiApp().run()
