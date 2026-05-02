"""gui.py - 产线优化工具图形界面"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, webbrowser, os
from optimizer import calculate_ct, tighten_ct, run_ga, compute_kpi, DEFAULT_TASK_TIMES
from report_gen import generate_html

FIELDS = [
    ("年产量（件/年）",       "qty",  "360000"),
    ("年工作天数",            "days", "280"),
    ("每天班次数",            "sh",   "3"),
    ("每班小时数",            "h",    "8"),
    ("设备OEE（0~1）",       "oee",  "0.87"),
    ("人力成本（万元/人/年）", "cw",  "12.0"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("弹性产线配置决策工具")
        self.resizable(False, False)
        self._build()

    def _build(self):
        frm = ttk.Frame(self, padding=24)
        frm.grid()

        ttk.Label(frm, text="弹性产线配置决策工具",
                  font=("Microsoft YaHei", 13, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 18))

        self.vars = {}
        for i, (label, key, default) in enumerate(FIELDS, 1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=5)
            v = tk.StringVar(value=default)
            ttk.Entry(frm, textvariable=v, width=18).grid(
                row=i, column=1, padx=(16, 0), pady=5)
            self.vars[key] = v

        self.btn = ttk.Button(frm, text="开始优化", command=self._run)
        self.btn.grid(row=len(FIELDS) + 1, column=0, columnspan=2,
                      pady=(20, 6), sticky="ew")

        self.status = ttk.Label(frm, text="", foreground="#888888")
        self.status.grid(row=len(FIELDS) + 2, column=0, columnspan=2)

    def _run(self):
        try:
            qty = int(self.vars['qty'].get())
            D   = int(self.vars['days'].get())
            SH  = int(self.vars['sh'].get())
            H   = int(self.vars['h'].get())
            OEE = float(self.vars['oee'].get())
            c_w = float(self.vars['cw'].get())
        except ValueError:
            messagebox.showerror("输入错误", "请检查所有字段均为有效数字")
            return

        self.btn.state(["disabled"])
        self.status.config(text="优化中，请稍候（约10~30秒）...", foreground="#e67e22")
        threading.Thread(target=self._optimize,
                         args=(qty, D, SH, H, OEE, c_w), daemon=True).start()

    def _optimize(self, qty, D, SH, H, OEE, c_w):
        try:
            formula_ct = calculate_ct(qty, D=D, SH=SH, H=H, OEE=OEE)
            tight_ct, _ = tighten_ct(formula_ct, DEFAULT_TASK_TIMES)
            result = run_ga(cycle_time=tight_ct, pop_size=300, max_gen=600, verbose=False)
            kpi    = compute_kpi(result, annual_output=qty, c_w=c_w, D=D)
            out    = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  f"report_{qty//10000}万件_CT{tight_ct:.0f}s.html")
            generate_html(kpi, out)
            self.after(0, self._done, out)
        except Exception as e:
            self.after(0, self._error, str(e))

    def _done(self, path):
        self.btn.state(["!disabled"])
        self.status.config(text="完成！正在打开报告...", foreground="#27ae60")
        webbrowser.open(f"file:///{path.replace(chr(92), '/')}")

    def _error(self, msg):
        self.btn.state(["!disabled"])
        self.status.config(text="出错了", foreground="#e74c3c")
        messagebox.showerror("错误", msg)


if __name__ == "__main__":
    App().mainloop()
