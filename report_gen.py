"""report_gen.py - HTML报告生成器（甘特图用纯SVG）"""

import json, math
from datetime import datetime

_COLORS = [
    "#4E79A7","#F28E2B","#E15759","#76B7B2","#59A14F","#EDC948",
    "#B07AA1","#FF9DA7","#9C755F","#BAB0AC","#7fc97f","#beaed4",
    "#fdc086","#386cb0","#f0027f","#bf5b17","#1b9e77","#d95f02",
    "#7570b3","#e7298a","#66c2a5","#fc8d62",
]


def _svg_gantt(kpi):
    """生成甘特图 SVG 字符串（Python端直接计算坐标，无JS依赖）"""
    stations = kpi['stations']
    times    = kpi['task_times']
    ct       = kpi['ct']
    m        = len(stations)

    ROW_H   = 44      # 每行高度
    PAD_L   = 72      # 左边距（工站标签）
    PAD_R   = 60      # 右边距
    PAD_T   = 20      # 上边距
    PAD_B   = 36      # 下边距（X轴标签）
    W_PLOT  = 820     # 绘图区宽度
    SVG_W   = PAD_L + W_PLOT + PAD_R
    SVG_H   = PAD_T + m * ROW_H + PAD_B

    # X轴比例：最大显示到 ct * 1.1
    x_max = ct * 1.1
    def tx(t): return PAD_L + t / x_max * W_PLOT

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
        f'style="font-family:Microsoft YaHei,sans-serif;font-size:12px">'
    ]

    # 背景斑马纹
    for i in range(m):
        y = PAD_T + i * ROW_H
        fill = "#f8f9fa" if i % 2 == 0 else "#ffffff"
        lines.append(f'<rect x="{PAD_L}" y="{y}" width="{W_PLOT}" height="{ROW_H}" fill="{fill}"/>')

    # 工站标签（Y轴）
    for i in range(m):
        y = PAD_T + i * ROW_H + ROW_H // 2
        lines.append(f'<text x="{PAD_L - 6}" y="{y+4}" text-anchor="end" fill="#555">工站{i+1}</text>')

    # 工序矩形
    for s_idx, station in enumerate(stations):
        y = PAD_T + s_idx * ROW_H
        x_cur = 0.0
        for task in station:
            dur = float(times[task - 1])
            x1  = tx(x_cur)
            w   = tx(x_cur + dur) - x1
            color = _COLORS[(task - 1) % len(_COLORS)]
            bar_y = y + 4
            bar_h = ROW_H - 8
            # 矩形
            lines.append(
                f'<rect x="{x1:.1f}" y="{bar_y}" width="{max(w-1,1):.1f}" height="{bar_h}" '
                f'rx="3" fill="{color}" stroke="white" stroke-width="1">'
                f'<title>工序{task}  {dur:.1f}s  ({x_cur:.1f}→{x_cur+dur:.1f}s)</title></rect>'
            )
            # 工序编号（宽度足够时才显示）
            if w >= 18:
                tx_mid = x1 + w / 2
                ty_mid = bar_y + bar_h / 2 + 4
                lines.append(
                    f'<text x="{tx_mid:.1f}" y="{ty_mid:.1f}" text-anchor="middle" '
                    f'fill="white" font-size="11" font-weight="bold">{task}</text>'
                )
            x_cur += dur

        # 工站负荷标注（右侧）
        load = sum(float(times[t-1]) for t in station)
        util = load / ct * 100
        label_color = "#e74c3c" if util > 98 else "#2c3e50"
        lines.append(
            f'<text x="{tx(x_cur)+4:.1f}" y="{y + ROW_H//2 + 4}" '
            f'fill="{label_color}" font-size="11">{load:.1f}s</text>'
        )

    # CT 红色虚线
    x_ct = tx(ct)
    lines.append(
        f'<line x1="{x_ct:.1f}" y1="{PAD_T}" x2="{x_ct:.1f}" y2="{PAD_T + m*ROW_H}" '
        f'stroke="#e74c3c" stroke-width="2" stroke-dasharray="6,4"/>'
    )
    lines.append(
        f'<text x="{x_ct+4:.1f}" y="{PAD_T + 14}" fill="#e74c3c" font-weight="bold" font-size="12">'
        f'CT={ct:.1f}s</text>'
    )

    # X轴刻度
    tick_step = _nice_step(ct / 5)
    t_val = 0.0
    while t_val <= x_max + 1e-6:
        xp = tx(t_val)
        lines.append(f'<line x1="{xp:.1f}" y1="{PAD_T + m*ROW_H}" x2="{xp:.1f}" '
                     f'y2="{PAD_T + m*ROW_H + 5}" stroke="#aaa"/>')
        lines.append(f'<text x="{xp:.1f}" y="{PAD_T + m*ROW_H + 18}" text-anchor="middle" '
                     f'fill="#888">{t_val:.0f}s</text>')
        t_val += tick_step

    # X轴标题
    lines.append(
        f'<text x="{PAD_L + W_PLOT//2}" y="{SVG_H - 2}" text-anchor="middle" '
        f'fill="#555" font-size="12">时间 (秒)</text>'
    )

    lines.append('</svg>')
    return '\n'.join(lines)


def _nice_step(raw):
    """计算美观的刻度间隔"""
    for s in [5, 10, 15, 20, 25, 30, 50]:
        if raw <= s: return s
    return 50


def _bar_chart_data(kpi):
    loads  = kpi['loads']
    labels = [f"工站{i+1}" for i in range(len(loads))]
    return {
        "labels": json.dumps(labels),
        "loads":  json.dumps([round(l, 2) for l in loads]),
        "ct":     kpi['ct'],
    }


def _table_rows(kpi):
    rows = []
    for i, st in enumerate(kpi['stations']):
        tasks_str = "、".join(str(t) for t in st)
        load = sum(float(kpi['task_times'][t-1]) for t in st)
        util = load / kpi['ct'] * 100
        w    = min(100, util)
        col  = "#e74c3c" if util > 98 else "#3498db" if util > 80 else "#95a5a6"
        rows.append(f"""<tr>
          <td class="c">工站 {i+1}</td><td>工序 {tasks_str}</td>
          <td class="c">{load:.2f}s</td>
          <td><div class="bw"><div class="b" style="width:{w:.1f}%;background:{col}"></div>
          <span>{util:.1f}%</span></div></td></tr>""")
    return "\n".join(rows)


def generate_html(kpi, output_path):
    now      = datetime.now().strftime("%Y-%m-%d %H:%M")
    svg      = _svg_gantt(kpi)
    bar      = _bar_chart_data(kpi)
    rows     = _table_rows(kpi)
    wan      = kpi['annual_output'] / 10000
    lbr_col  = "#27ae60" if kpi['lbr'] >= 85 else "#e67e22" if kpi['lbr'] >= 75 else "#e74c3c"
    bn_col   = "#e74c3c" if kpi['bn_rate'] >= 98 else "#27ae60"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>产线调度方案报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--blue:#2c3e50;--accent:#3498db;--green:#27ae60;--orange:#e67e22;--red:#e74c3c;--bg:#f4f6f9}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);color:#333;font-size:14px}}
.banner{{background:linear-gradient(135deg,#2c3e50,#3498db);color:#fff;padding:28px 40px}}
.banner h1{{font-size:24px;font-weight:700;margin-bottom:6px}}
.banner .meta{{font-size:13px;opacity:.75}}
.container{{max-width:1200px;margin:0 auto;padding:20px}}
.sec{{font-size:16px;font-weight:700;color:var(--blue);border-left:4px solid var(--accent);
      padding-left:10px;margin:24px 0 14px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:8px}}
.kpi{{background:#fff;border-radius:10px;padding:16px;text-align:center;
      box-shadow:0 2px 8px rgba(0,0,0,.07);border-top:4px solid var(--accent)}}
.kpi-l{{font-size:12px;color:#888;margin-bottom:6px}}
.kpi-v{{font-size:24px;font-weight:700;color:var(--blue)}}
.kpi-u{{font-size:11px;color:#aaa;margin-top:3px}}
.card{{background:#fff;border-radius:10px;padding:18px;margin-bottom:18px;
       box-shadow:0 2px 8px rgba(0,0,0,.07)}}
.card h3{{font-size:14px;color:var(--blue);margin-bottom:14px}}
.gantt-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}
th{{background:var(--blue);color:#fff;padding:9px 12px;text-align:left;font-size:13px}}
td{{padding:8px 12px;border-bottom:1px solid #eee;font-size:13px}}
tr:nth-child(even) td{{background:#f9fafb}}
td.c{{text-align:center}}
.bw{{display:flex;align-items:center;gap:8px}}
.b{{height:15px;border-radius:3px;min-width:2px}}
.footer{{text-align:center;padding:20px;color:#aaa;font-size:12px}}
</style>
</head>
<body>
<div class="banner">
  <h1>产线人员调度方案报告</h1>
  <div class="meta">年产量：{wan:.0f} 万件 &nbsp;|&nbsp; 生成时间：{now} &nbsp;|&nbsp; 遗传算法（DPGA）</div>
</div>
<div class="container">

<div class="sec">关键指标摘要</div>
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-l">目标节拍</div>
    <div class="kpi-v">{kpi['ct']:.1f}</div><div class="kpi-u">秒/件</div></div>
  <div class="kpi" style="border-top-color:#27ae60"><div class="kpi-l">推荐工人数</div>
    <div class="kpi-v">{kpi['hc']}</div><div class="kpi-u">人</div></div>
  <div class="kpi"><div class="kpi-l">工站数量</div>
    <div class="kpi-v">{kpi['m']}</div><div class="kpi-u">个</div></div>
  <div class="kpi" style="border-top-color:{lbr_col}"><div class="kpi-l">线平衡率</div>
    <div class="kpi-v" style="color:{lbr_col}">{kpi['lbr']:.1f}</div>
    <div class="kpi-u">%（目标≥85%）</div></div>
  <div class="kpi" style="border-top-color:#e67e22"><div class="kpi-l">平滑指数 SI</div>
    <div class="kpi-v">{kpi['si']:.2f}</div><div class="kpi-u">越低越好</div></div>
  <div class="kpi" style="border-top-color:{bn_col}"><div class="kpi-l">瓶颈负荷率</div>
    <div class="kpi-v" style="color:{bn_col}">{kpi['bn_rate']:.1f}</div>
    <div class="kpi-u">%（≤100%合规）</div></div>
  <div class="kpi" style="border-top-color:#27ae60"><div class="kpi-l">工人利用率</div>
    <div class="kpi-v">{kpi['worker_util']:.1f}</div><div class="kpi-u">%</div></div>
  <div class="kpi" style="border-top-color:#e67e22"><div class="kpi-l">年人力成本</div>
    <div class="kpi-v">{kpi['annual_cost_wan']:.0f}</div><div class="kpi-u">万元/年</div></div>
  <div class="kpi" style="border-top-color:#2c3e50"><div class="kpi-l">生产天数</div>
    <div class="kpi-v">{kpi['D']}</div><div class="kpi-u">天/年</div></div>
  <div class="kpi" style="border-top-color:#e74c3c"><div class="kpi-l">年总成本</div>
    <div class="kpi-v">{kpi['total_cost_wan']:.0f}</div><div class="kpi-u">万元/年 *</div></div>
</div>

<div class="sec">山积图（各工站负荷 vs 节拍）</div>
<div class="card">
  <h3>工站负荷分布 — 节拍线 = {kpi['ct']:.1f} s</h3>
  <canvas id="barC" height="260"></canvas>
</div>

<div class="sec">甘特图（工序-工站分配）</div>
<div class="card">
  <h3>各工站工序分配时序图（红色虚线 = 节拍 CT）</h3>
  <div class="gantt-wrap">{svg}</div>
</div>

<div class="sec">工序分配明细表</div>
<div class="card" style="padding:0;overflow:hidden">
<table>
  <thead><tr><th style="width:90px">工站</th><th>分配工序</th>
  <th style="width:100px">负荷</th><th style="width:200px">负荷率</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</div>

<div class="sec">计算参数</div>
<div class="card">
<table><tbody>
  <tr><td style="width:180px;color:#888">年产量</td><td>{kpi['annual_output']:,} 件（{wan:.0f} 万件）</td></tr>
  <tr><td style="color:#888">目标节拍 CT</td><td>{kpi['ct']:.2f} 秒/件</td></tr>
  <tr><td style="color:#888">工序总数</td><td>{kpi['n_tasks']} 道</td></tr>
  <tr><td style="color:#888">工序总时间</td><td>{kpi['total_task_time']:.2f} 秒</td></tr>
  <tr><td style="color:#888">理论最少工站</td><td>{kpi['theoretical_min_stations']} 个</td></tr>
  <tr><td style="color:#888">算法优化工站</td><td>{kpi['m']} 个 → {kpi['hc']} 人（一人一站）</td></tr>
  <tr><td style="color:#888">年人力成本</td><td>{kpi['annual_cost_wan']:.0f} 万元（12万/人/年）</td></tr>
  <tr><td style="color:#888">生产天数</td><td>{kpi['D']} 天/年</td></tr>
  <tr><td style="color:#888">年总成本</td><td>{kpi['total_cost_wan']:.0f} 万元（* 仅含人力成本，工站固定成本需企业提供）</td></tr>
</tbody></table>
</div>

</div>
<div class="footer">产线弹性精益优化研究 · 遗传算法决策支持工具 · {now}</div>

<script>
const barLabels = {bar['labels']};
const barLoads  = {bar['loads']};
const CT = {bar['ct']};
new Chart(document.getElementById('barC').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: barLabels,
    datasets: [{{
      label: '工站负荷 (s)',
      data: barLoads,
      backgroundColor: barLoads.map(v => v > CT ? 'rgba(231,76,60,.75)' : v > CT*.85 ? 'rgba(52,152,219,.75)' : 'rgba(149,165,166,.6)'),
      borderColor:     barLoads.map(v => v > CT ? '#c0392b' : v > CT*.85 ? '#2980b9' : '#7f8c8d'),
      borderWidth: 1, borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{display:false}}, tooltip: {{callbacks: {{label: c => ` ${{c.parsed.y.toFixed(2)}}s`}}}} }},
    scales: {{ y: {{ title: {{display:true,text:'时间 (s)'}}, min:0,
      max: Math.max(CT*1.15, Math.max(...barLoads)*1.1) }} }},
    animation: {{duration:600}}
  }},
  plugins: [{{
    id:'ctLine',
    afterDraw(chart){{
      const {{ctx:c, scales:{{x,y}}}} = chart;
      const yp = y.getPixelForValue(CT);
      c.save(); c.strokeStyle='#e74c3c'; c.lineWidth=2; c.setLineDash([6,4]);
      c.beginPath(); c.moveTo(x.left,yp); c.lineTo(x.right,yp); c.stroke();
      c.fillStyle='#e74c3c'; c.font='bold 12px sans-serif';
      c.fillText('CT='+CT.toFixed(1)+'s', x.right-110, yp-5);
      c.restore();
    }}
  }}]
}});
</script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [报告] HTML已保存: {output_path}")
    return output_path
