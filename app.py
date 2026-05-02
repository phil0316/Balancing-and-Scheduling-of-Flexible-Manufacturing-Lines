"""app.py - Flask 网页入口"""
from flask import Flask, request, send_file
import os
from optimizer import calculate_ct, tighten_ct, run_ga, compute_kpi, DEFAULT_TASK_TIMES
from report_gen import generate_html

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/run', methods=['POST'])
def run_opt():
    p      = request.json
    qty    = int(p['qty'])
    D      = int(p.get('days', 280))
    SH     = int(p.get('sh', 3))
    H      = int(p.get('h', 8))
    OEE    = float(p.get('oee', 0.87))
    c_w    = float(p.get('cw', 12.0))

    formula_ct = calculate_ct(qty, D=D, SH=SH, H=H, OEE=OEE)
    tight_ct, _ = tighten_ct(formula_ct, DEFAULT_TASK_TIMES)
    result = run_ga(cycle_time=tight_ct, pop_size=300, max_gen=600, verbose=False)
    kpi    = compute_kpi(result, annual_output=qty, c_w=c_w, D=D)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       f"report_{qty//10000}万件_CT{tight_ct:.0f}s.html")
    generate_html(kpi, out)
    with open(out, encoding='utf-8') as f:
        return f.read()

if __name__ == '__main__':
    print("  请在浏览器打开: http://localhost:5000")
    app.run(port=5000)
