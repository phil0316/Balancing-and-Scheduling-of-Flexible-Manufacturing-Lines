"""
main.py - 命令行入口
使用方式：
  python main.py                   # 交互式引导
  python main.py --output 360K     # 指定文件名前缀
"""

import argparse
import os
import webbrowser
from optimizer import calculate_ct, tighten_ct, run_ga, compute_kpi, DEFAULT_TASK_TIMES
from report_gen import generate_html


BANNER = """
╔══════════════════════════════════════════════════════════╗
║         弹性产线配置决策工具  v1.0                        ║
║         基于双种群遗传算法 (DPGA) 的装配线平衡求解        ║
╚══════════════════════════════════════════════════════════╝
"""

# ── 默认参数（SPS报告基准） ──
DEFAULTS = {
    'annual_output': 260000,   # 年产量（件）
    'D': 280,                  # 年工作天数
    'SH': 3,                   # 每天班次
    'H': 8,                    # 每班小时数
    'OEE': 0.87,               # 设备综合效率
    'c_w': 12.0,               # 人力成本（万元/人/年）
    'pop_size': 300,
    'max_gen': 600,
}


def ask(prompt, default, cast=float):
    """带默认值的命令行输入"""
    raw = input(f"  {prompt} [{default}]: ").strip()
    if raw == "":
        return cast(default)
    return cast(raw)


def interactive_input():
    """交互式引导输入参数"""
    print("\n── 请输入生产参数（直接回车使用默认值） ──\n")
    annual_output = ask("年产量（件/年，如 360000）", DEFAULTS['annual_output'], int)
    D   = ask("年工作天数", DEFAULTS['D'], int)
    SH  = ask("每天班次数", DEFAULTS['SH'], int)
    H   = ask("每班工作小时数", DEFAULTS['H'], int)
    OEE = ask("设备综合效率 OEE（0~1）", DEFAULTS['OEE'], float)
    c_w = ask("人力成本（万元/人/年）", DEFAULTS['c_w'], float)
    return {
        'annual_output': annual_output,
        'D': D, 'SH': SH, 'H': H, 'OEE': OEE, 'c_w': c_w,
    }


def run(params, output_prefix="report", open_browser=True, interactive=True):
    """执行完整流程：计算节拍 → 遗传算法 → 生成HTML"""

    annual_output = params['annual_output']
    D   = params.get('D', DEFAULTS['D'])
    SH  = params.get('SH', DEFAULTS['SH'])
    H   = params.get('H', DEFAULTS['H'])
    OEE = params.get('OEE', DEFAULTS['OEE'])
    c_w = params.get('c_w', DEFAULTS['c_w'])

    # Step 1: 计算节拍
    formula_ct = calculate_ct(annual_output, D=D, SH=SH, H=H, OEE=OEE)
    tight_ct, m_lb = tighten_ct(formula_ct, DEFAULT_TASK_TIMES)
    print(f"\n  ── Step 1 节拍计算 ──")
    print(f"  公式节拍  = {formula_ct}s  （可用时间 / 年产量）")
    print(f"  理论最少工站 m_lb = {m_lb}")
    print(f"  收紧节拍  = max(最长工序{max(DEFAULT_TASK_TIMES):.1f}s, 总工时/m_lb) = {tight_ct}s")
    ct = tight_ct

    # SPS报告对比提示
    sps_ref = {360000: 54, 260000: 75, 180000: 108}
    if annual_output in sps_ref:
        print(f"  (SPS报告参考节拍: {sps_ref[annual_output]}s，本次收紧节拍: {ct}s)")

    # Step 2: 遗传算法求解
    print(f"\n  ── Step 2 遗传算法求解（耗时约10-30秒） ──")
    ga_result = run_ga(
        cycle_time=ct,
        pop_size=DEFAULTS['pop_size'],
        max_gen=DEFAULTS['max_gen'],
        verbose=True,
    )

    # Step 3: 计算KPI
    kpi = compute_kpi(ga_result, annual_output=annual_output, c_w=c_w, D=D)

    # Step 4: 打印结果摘要
    print(f"\n  ── Step 3 优化结果 ──")
    print(f"  年产量：{annual_output:,} 件/年")
    print(f"  需求节拍（收紧）：{kpi['req_ct']:.2f}s")
    print(f"  实际节拍（瓶颈）：{kpi['ct']:.2f}s  ← 瓶颈工站100%")
    print(f"  工站数：{kpi['m']} 个")
    print(f"  工人数：{kpi['hc']} 人")
    print(f"  线平衡率：{kpi['lbr']:.2f}%")
    print(f"  平滑指数：{kpi['si']:.4f}")
    print(f"  年人力成本：{kpi['annual_cost_wan']:.0f} 万元")

    sps_hc = {360000: 19, 260000: 13, 180000: 10}
    if annual_output in sps_hc:
        ref_hc = sps_hc[annual_output]
        diff = kpi['hc'] - ref_hc
        sign = "+" if diff >= 0 else ""
        print(f"  (SPS报告参考人数: {ref_hc}人，算法输出: {kpi['hc']}人，差异: {sign}{diff}人)")

    # Step 5: 生成HTML
    print(f"\n  ── Step 4 生成HTML报告 ──")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = f"{output_prefix}_{annual_output // 10000}万件_CT{ct:.0f}s.html"
    out_path = os.path.join(script_dir, filename)
    generate_html(kpi, out_path)

    if open_browser:
        print(f"  正在打开浏览器...")
        webbrowser.open(f"file:///{out_path.replace(chr(92), '/')}")

    return kpi, out_path


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description="产线调度HTML报告生成工具")
    parser.add_argument("--output", default="report", help="输出文件名前缀")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    # 快捷参数（可跳过交互）
    parser.add_argument("--qty",  type=int,   help="年产量（件），如 360000")
    parser.add_argument("--oee",  type=float, help="OEE（0~1），默认 0.87")
    parser.add_argument("--days", type=int,   help="年工作天数，默认 280")
    args = parser.parse_args()

    if args.qty:
        # 快捷模式：命令行直接传参，不进行交互确认
        params = {
            'annual_output': args.qty,
            'OEE': args.oee if args.oee else DEFAULTS['OEE'],
            'D': args.days if args.days else DEFAULTS['D'],
            'SH': DEFAULTS['SH'],
            'H': DEFAULTS['H'],
            'c_w': DEFAULTS['c_w'],
        }
        print(f"  使用命令行参数：年产量={args.qty:,}件，OEE={params['OEE']}")
        print()
        run(params, output_prefix=args.output, open_browser=not args.no_browser, interactive=False)
    else:
        # 交互式输入
        params = interactive_input()
        print()
        run(params, output_prefix=args.output, open_browser=not args.no_browser, interactive=True)

    print("\n  完成！")


if __name__ == "__main__":
    main()
