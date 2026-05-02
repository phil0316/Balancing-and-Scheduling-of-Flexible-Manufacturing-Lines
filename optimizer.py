"""optimizer.py - 装配线平衡遗传算法（CT参数化，轻量版）"""

import numpy as np
import math
from collections import deque

DEFAULT_TASK_TIMES = np.array([
    28.5, 25, 17.9, 30.7, 35, 32.7, 35.9, 20, 9.9, 6.1, 26.7,
    49.8, 48.1, 6.9, 3, 11.8, 40.2, 31.3, 55.9, 54.3, 13, 38.7
])

DEFAULT_PRECEDENCE_EDGES = [
    (1,2),(1,7),(2,3),(3,6),(6,7),(7,8),(4,5),(5,8),
    (8,9),(9,10),(10,11),(10,12),(10,13),(11,14),(12,14),
    (13,14),(14,15),(15,16),(16,17),(15,18),(17,18),
    (18,19),(19,20),(20,21),(21,22)
]


def calculate_ct(annual_output, D=280, SH=3, H=8, OEE=0.87):
    return round(D * SH * H * 3600 * OEE / annual_output, 2)


def tighten_ct(formula_ct, task_times):
    """
    将公式节拍收紧为：给定最少工站数下的最紧节拍。
    确保瓶颈工站恰好达到100%负荷，最大化线平衡率。

    原理：
      m_lb = ceil(总工时 / 公式CT)   ← 最少工站数
      tight_ct = max(最长单工序, 总工时 / m_lb)  ← 最紧可行节拍

    示例（360K）：
      formula_ct=58.46s → m_lb=11 → tight_ct=max(55.9, 621.4/11)=56.49s
      与遗传问题.py中CT=56s完全吻合
    """
    total = float(sum(task_times))
    max_t  = float(max(task_times))
    m_lb   = math.ceil(total / formula_ct)
    return round(max(max_t, total / m_lb), 2), m_lb


class PrecedenceGraph:
    def __init__(self, n, edges):
        self.n_tasks = n
        self.succ = [[] for _ in range(n + 1)]
        self.pred = [[] for _ in range(n + 1)]
        for u, v in edges:
            self.succ[u].append(v)
            self.pred[v].append(u)

    def topo_sort(self):
        indeg = [0] * (self.n_tasks + 1)
        for u in range(1, self.n_tasks + 1):
            for v in self.succ[u]: indeg[v] += 1
        q = deque(i for i in range(1, self.n_tasks + 1) if indeg[i] == 0)
        res = []
        while q:
            u = q.popleft(); res.append(u)
            for v in self.succ[u]:
                indeg[v] -= 1
                if indeg[v] == 0: q.append(v)
        return res

    def random_topo(self):
        """拓扑感知随机排列：每步从可用任务中随机选，保证可行性"""
        indeg = [0] * (self.n_tasks + 1)
        for u in range(1, self.n_tasks + 1):
            for v in self.succ[u]: indeg[v] += 1
        avail = [i for i in range(1, self.n_tasks + 1) if indeg[i] == 0]
        res = []
        while avail:
            u = avail[np.random.randint(len(avail))]
            avail.remove(u); res.append(u)
            for v in self.succ[u]:
                indeg[v] -= 1
                if indeg[v] == 0: avail.append(v)
        return res


def decode(seq, times, ct, graph):
    """贪心解码：序列 → 工站列表"""
    n = len(seq)
    done = [False] * (n + 1)
    stations = []
    while sum(done) < n:
        st, load = [], 0.0
        for t in seq:
            if done[t] or not all(done[p] for p in graph.pred[t]): continue
            if load + times[t-1] <= ct + 1e-9:
                st.append(t); done[t] = True; load += times[t-1]
        if not st:
            avail = [t for t in range(1, n+1) if not done[t] and all(done[p] for p in graph.pred[t])]
            if avail:
                t = min(avail, key=lambda x: times[x-1])
                st.append(t); done[t] = True
        stations.append(st)
    return stations


def fitness(stations, times, ct, graph):
    """
    适应度（越小越好）
    优先级：减工站数 > 提线平衡率 > 降平滑指数
    量纲对齐：m*200 >> lbr*2 >> si*1
    """
    m = len(stations)
    loads = [sum(times[t-1] for t in st) for st in stations]
    total = sum(times)
    lbr = total / (m * ct) * 100
    si = math.sqrt(sum((ct - l)**2 for l in loads) / m)

    # 超时惩罚
    penalty = sum(max(0, l - ct) * 2000 for l in loads)

    # 紧前约束惩罚（工站编号顺序检查）
    t2s = {t: i for i, st in enumerate(stations) for t in st}
    for u in range(1, graph.n_tasks + 1):
        for v in graph.succ[u]:
            if t2s.get(u, 0) > t2s.get(v, 0):
                penalty += 5000

    return penalty + m * 200 - lbr * 2 + si, m, lbr, si, loads


def ox_cross(p1, p2):
    n = len(p1)
    a, b = sorted(np.random.choice(n, 2, replace=False))
    child = [-1] * n
    child[a:b+1] = p1[a:b+1]
    pos = 0
    for g in p2:
        if g not in child:
            while child[pos] != -1: pos += 1
            child[pos] = g
    return child


def mutate(seq, graph):
    """insert变异：取出一个任务，插入到随机合法位置"""
    s = seq.copy()
    n = len(s)
    i = np.random.randint(n)
    task = s.pop(i)
    # 找合法插入范围：所有前驱都在task之前，所有后继都在task之后
    pred_pos = max((s.index(p) for p in graph.pred[task] if p in s), default=-1)
    succ_pos = min((s.index(v) for v in graph.succ[task] if v in s), default=n)
    lo, hi = pred_pos + 1, succ_pos  # [lo, hi] 均合法
    if lo > hi: lo = hi = max(0, min(i, n-1))
    j = np.random.randint(lo, hi + 1)
    s.insert(j, task)
    return s


def run_ga(cycle_time, task_times=None, precedence_edges=None,
           pop_size=120, max_gen=250, cr=0.85, pm=0.10,
           elite_n=4, tournament_k=3, seed=42, verbose=True):

    np.random.seed(seed)
    if task_times is None: task_times = DEFAULT_TASK_TIMES
    if precedence_edges is None: precedence_edges = DEFAULT_PRECEDENCE_EDGES

    n = len(task_times)
    graph = PrecedenceGraph(n, precedence_edges)
    topo = graph.topo_sort()

    # 初始化：第一个用topo，其余用拓扑感知随机排列（保证多样性且全部可行）
    pop = [topo] + [graph.random_topo() for _ in range(pop_size - 1)]

    best_sol, best_fit = None, float('inf')
    no_improve = 0

    if verbose:
        lb = math.ceil(sum(task_times) / cycle_time)
        print(f"\n  [GA] CT={cycle_time}s  工序={n}  理论下界={lb}站  种群={pop_size}")

    for gen in range(max_gen):
        decoded = [decode(s, task_times, cycle_time, graph) for s in pop]
        scores  = [fitness(d, task_times, cycle_time, graph) for d in decoded]
        fits    = [s[0] for s in scores]

        best_i = int(np.argmin(fits))
        if fits[best_i] < best_fit:
            best_fit = fits[best_i]
            best_sol = (decoded[best_i], scores[best_i])
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= 60:
            if verbose: print(f"  [GA] 第{gen}代收敛")
            break

        order = np.argsort(fits)
        new_pop = [pop[i] for i in order[:elite_n]]
        while len(new_pop) < pop_size:
            c1 = np.random.choice(len(pop), tournament_k, replace=False)
            c2 = np.random.choice(len(pop), tournament_k, replace=False)
            p1 = pop[c1[np.argmin([fits[j] for j in c1])]]
            p2 = pop[c2[np.argmin([fits[j] for j in c2])]]
            child = ox_cross(p1, p2) if np.random.random() < cr else p1.copy()
            if np.random.random() < pm:
                child = mutate(child, graph)
            new_pop.append(child)
        pop = new_pop

        if verbose and gen % 50 == 0:
            _, m, lbr, si, _ = best_sol[1]
            print(f"  [GA] 第{gen:3d}代: 工站={m}  LBR={lbr:.1f}%  SI={si:.2f}")

    stations, (_, m, lbr, si, loads) = best_sol
    effective_ct = round(max(loads), 2)   # 瓶颈工站负荷 = 真实节拍
    total = round(float(sum(task_times)), 2)
    eff_lbr = round(total / (m * effective_ct) * 100, 2)
    eff_si  = round(math.sqrt(sum((effective_ct - l)**2 for l in loads) / m), 4)
    return {
        'ct': cycle_time,           # GA求解用的节拍（收紧后）
        'effective_ct': effective_ct,  # 实际瓶颈节拍（最终报告用）
        'stations': stations, 'm': m,
        'lbr': eff_lbr, 'si': eff_si,
        'loads': loads, 'task_times': task_times,
        'n_tasks': n, 'total_task_time': total,
    }


def compute_kpi(ga_result, annual_output, c_w=12.0, D=280):
    m   = ga_result['m']
    ct  = ga_result['effective_ct']
    req_ct = ga_result['ct']
    hc  = m
    labor_cost = round(hc * c_w, 2)
    return {
        'annual_output': annual_output,
        'ct': ct, 'req_ct': req_ct,
        'hc': hc, 'm': m,
        'lbr': ga_result['lbr'], 'si': ga_result['si'],
        'loads': ga_result['loads'],
        'annual_cost_wan': labor_cost,
        'total_cost_wan': labor_cost,   # 当前仅含人力成本（工站成本需企业提供）
        'bottleneck_load': round(max(ga_result['loads']), 2),
        'bn_rate': 100.0,
        'worker_util': round(ga_result['total_task_time'] / (hc * ct) * 100, 2),
        'theoretical_min_stations': math.ceil(ga_result['total_task_time'] / req_ct),
        'stations': ga_result['stations'],
        'task_times': ga_result['task_times'],
        'n_tasks': ga_result['n_tasks'],
        'total_task_time': ga_result['total_task_time'],
        'D': D,
    }
