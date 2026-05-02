import numpy as np
import matplotlib.pyplot as plt
from collections import deque
import warnings

warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False 

# ============================================================================
# 1. 核心参数配置
# ============================================================================
CONFIG = {
    'POP_A_SIZE': 100,
    'POP_B_SIZE': 100,
    'MAX_GEN': 300,
    'CR_A': 0.85,
    'CR_B': 0.25,
    'PM_A': 0.2,
    'PM_B': 0.05,
    'ELITE_A': 3,
    'ELITE_B': 3,
    'MIG_INTERVAL': 20,
    'TOURNAMENT_SIZE': 3,
    'ALPHA': 0.9,       # 工位数权重
    'BETA': 0.1,        # 平滑指数权重
    
    # 惩罚项设置
    'PENALTY_VALUE': 5000.0,
    'TARGET_TASKS': (4, 5), # 目标工序4和5

    'USE_LOCAL_SEARCH': True,
    'LS_ITERATIONS': 15,
    'SEED': 42,
}

# 数据定义
TASK_TIMES = np.array([
    28.5, 25, 17.9, 30.7, 35, 32.7, 35.9, 20, 9.9, 6.1, 26.7,
    49.8, 48.1, 6.9, 3, 11.8, 40.2, 31.3, 55.9, 54.3, 13, 38.7
])

PRECEDENCE_EDGES = [
    (1, 2), (1, 7), (2, 3), (3, 6), (6, 7), (7, 8), (4, 5), (5, 8),
    (8, 9), (9, 10), (10, 11), (10, 12), (10, 13), (11, 14), (12, 14),
    (13, 14), (14, 15), (15, 16), (16, 17), (15, 18), (17, 18),
    (18, 19), (19, 20), (20, 21), (21, 22)
]

CYCLE_TIME = 60

# ============================================================================
# 2. 基础类与图逻辑
# ============================================================================
class PrecedenceGraph:
    def __init__(self, n_tasks, edges):
        self.n_tasks = n_tasks
        self.successors = [[] for _ in range(n_tasks + 1)]
        self.predecessors = [[] for _ in range(n_tasks + 1)]
        for u, v in edges:
            self.successors[u].append(v)
            self.predecessors[v].append(u)

    def is_feasible_sequence(self, sequence):
        pos = {t: i for i, t in enumerate(sequence)}
        for u in range(1, self.n_tasks + 1):
            for v in self.successors[u]:
                if pos.get(u, -1) > pos.get(v, float('inf')): return False
        return True

    def topological_sort(self):
        indeg = [0] * (self.n_tasks + 1)
        for u in range(1, self.n_tasks + 1):
            for v in self.successors[u]: indeg[v] += 1
        queue = deque([i for i in range(1, self.n_tasks + 1) if indeg[i] == 0])
        res = []
        while queue:
            u = queue.popleft()
            res.append(u)
            for v in self.successors[u]:
                indeg[v] -= 1
                if indeg[v] == 0: queue.append(v)
        return res

# ============================================================================
# 3. 评估与惩罚逻辑（相邻工位检查）
# ============================================================================
def evaluate_solution(stations, times, cycle_time):
    m = len(stations)
    loads = [float(sum(times[t-1] for t in station)) for station in stations]
    total_time = float(np.sum(times))
    si = np.sqrt(np.sum((cycle_time - np.array(loads))**2) / m)
    efficiency = total_time / (m * cycle_time) if m > 0 else 0.0

    # --- 改进：工序4和5是否相邻或在同一工位 ---
    t_a, t_b = CONFIG['TARGET_TASKS']
    idx_a, idx_b = -1, -1
    for i, station in enumerate(stations):
        if t_a in station: idx_a = i
        if t_b in station: idx_b = i
    
    # 相邻或相同判断逻辑
    is_neighbor = (abs(idx_a - idx_b) <= 1)
    penalty = 0.0 if is_neighbor else CONFIG['PENALTY_VALUE']

    return {
        'm': m, 'si': si, 'efficiency': efficiency, 
        'loads': loads, 'stations': stations,
        'penalty': penalty, 'is_valid': is_neighbor
    }

def compute_fitness(metrics):
    return CONFIG['ALPHA'] * metrics['m'] + CONFIG['BETA'] * metrics['si'] + metrics['penalty']

# ============================================================================
# 4. 解码与遗传算子
# ============================================================================
def decode_sequence(sequence, times, cycle_time, graph):
    n = len(sequence)
    assigned = [False] * (n + 1)
    stations = []
    while sum(assigned) < n:
        curr_st, curr_load = [], 0.0
        for task in sequence:
            if assigned[task]: continue
            if not all(assigned[p] for p in graph.predecessors[task]): continue
            if curr_load + times[task-1] <= cycle_time + 1e-6:
                curr_st.append(task)
                assigned[task] = True
                curr_load += times[task-1]
        if not curr_st:
            avail = [t for t in range(1, n+1) if not assigned[t] and all(assigned[p] for p in graph.predecessors[t])]
            if avail:
                t = min(avail, key=lambda x: times[x-1])
                curr_st.append(t); assigned[t] = True
        stations.append(curr_st)
    return stations

def ox_crossover(p1, p2):
    n = len(p1)
    a, b = sorted(np.random.choice(n, 2, replace=False))
    child = [-1]*n
    child[a:b+1] = p1[a:b+1]
    pos = 0
    for g in p2:
        if g not in child:
            while child[pos] != -1: pos += 1
            child[pos] = g
    return child

# ============================================================================
# 5. 可视化模块 (图2 样式甘特图)
# ============================================================================
def plot_gantt_chart_improved(metrics, times, cycle_time):
    stations = metrics['stations']
    m = metrics['m']
    efficiency = metrics['efficiency']
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # 生成足够多的颜色
    colors = plt.cm.Set3(np.linspace(0, 1, 24))
    
    for s_idx, station in enumerate(stations):
        # 翻转坐标，让工位1在最上面
        y_pos = m - s_idx 
        curr_x = 0
        
        for task in station:
            t_dur = times[task-1]
            rect = plt.Rectangle((curr_x, y_pos - 0.4), t_dur, 0.8, 
                                 facecolor=colors[task % 24], edgecolor='black', linewidth=1.2)
            ax.add_patch(rect)
            
            # 标注工序ID
            ax.text(curr_x + t_dur/2, y_pos, str(task), 
                    ha='center', va='center', fontsize=10, color='white' if task in [17, 19, 20] else 'black')
            curr_x += t_dur
            
        # 标注工位结束时间
        ax.plot([curr_x, curr_x], [y_pos - 0.45, y_pos + 0.45], color='black', linewidth=1.5)
        ax.text(curr_x + 0.5, y_pos, f"{curr_x:.1f}s", va='center', fontsize=10)

    # 绘制节拍红线
    ax.axvline(x=cycle_time, color='red', linestyle='--', linewidth=2.5, label=f"节拍 C={cycle_time}s")
    
    # 装饰
    ax.set_title(f"工位任务分配甘特图 (工位数={m}, 线效率={efficiency:.2%})", fontsize=15, pad=15)
    ax.set_ylabel("工位", fontsize=12)
    ax.set_xlabel("时间 (秒)", fontsize=12)
    
    ax.set_yticks(range(1, m + 1))
    ax.set_yticklabels([f"工位 {i}" for i in range(m, 0, -1)])
    
    ax.set_xlim(0, cycle_time + 10)
    ax.set_ylim(0.5, m + 0.5)
    ax.grid(axis='x', linestyle=':', alpha=0.5)
    ax.legend(loc='upper right', prop={'size': 11})
    
    plt.tight_layout()
    plt.show()

# ============================================================================
# 6. 主程序
# ============================================================================
def main_run():
    np.random.seed(CONFIG['SEED'])
    graph = PrecedenceGraph(len(TASK_TIMES), PRECEDENCE_EDGES)
    
    # 初始化
    pop = [graph.topological_sort() for _ in range(CONFIG['POP_A_SIZE'])]
    for i in range(1, len(pop)): np.random.shuffle(pop[i])
    pop = [s if graph.is_feasible_sequence(s) else graph.topological_sort() for s in pop]

    best_res = {'fitness': float('inf'), 'metrics': None}

    print("双种群遗传算法启动...")
    print(f"约束：工序 {CONFIG['TARGET_TASKS']} 必须在相同或相邻工位。")

    for gen in range(CONFIG['MAX_GEN']):
        # 解码与评估
        current_metrics = [evaluate_solution(decode_sequence(s, TASK_TIMES, CYCLE_TIME, graph), TASK_TIMES, CYCLE_TIME) for s in pop]
        fits = [compute_fitness(m) for m in current_metrics]

        # 更新纪录
        for i in range(len(fits)):
            if fits[i] < best_res['fitness']:
                best_res = {'fitness': fits[i], 'metrics': current_metrics[i]}

        # 精英保留与选择
        elites = [pop[i] for i in np.argsort(fits)[:CONFIG['ELITE_A']]]
        
        # 锦标赛选择
        new_pop = list(elites)
        while len(new_pop) < CONFIG['POP_A_SIZE']:
            cand = np.random.choice(len(fits), CONFIG['TOURNAMENT_SIZE'], replace=False)
            p1 = pop[cand[np.argmin([fits[j] for j in cand])]]
            
            cand = np.random.choice(len(fits), CONFIG['TOURNAMENT_SIZE'], replace=False)
            p2 = pop[cand[np.argmin([fits[j] for j in cand])]]
            
            child = ox_crossover(p1, p2) if np.random.random() < CONFIG['CR_A'] else p1.copy()
            if np.random.random() < CONFIG['PM_A']:
                idx1, idx2 = np.random.choice(len(child), 2, replace=False)
                child[idx1], child[idx2] = child[idx2], child[idx1]
            new_pop.append(child)
        
        pop = new_pop
        if gen % 50 == 0:
            m = best_res['metrics']['m']
            val = "符合" if best_res['metrics']['is_valid'] else "违规"
            print(f"第 {gen} 代: 最优工位={m}, 邻近约束={val}")

    # 输出结果
    res = best_res['metrics']
    print("\n" + "="*40)
    print("优化完成！")
    print(f"最小工位数: {res['m']}")
    print(f"线效率: {res['efficiency']:.2%}")
    print(f"平滑指数: {res['si']:.2f}")
    print(f"工序4和5是否符合要求: {'是(相同或相邻)' if res['is_valid'] else '否'}")
    print("="*40)

    plot_gantt_chart_improved(res, TASK_TIMES, CYCLE_TIME)

    # ============================================================
    # 单独输出：生产线平滑指数（SI）详细计算过程
    # ============================================================
    print("\n" + "=" * 55)
    print("       生产线平滑指数（Smoothness Index, SI）")
    print("=" * 55)
    print(f"  公式：SI = sqrt( Σ (C - t_i)² / n )")
    print(f"        其中 C = 节拍时间 = {CYCLE_TIME} s")
    print(f"             t_i = 第 i 个工位的实际作业时间")
    print(f"             n   = 工站数量")
    print("-" * 55)

    loads = res['loads']
    n = res['m']
    squared_diffs = []
    for i, load in enumerate(loads):
        diff = CYCLE_TIME - load
        sq = diff ** 2
        squared_diffs.append(sq)
        print(f"  工位 {i+1:2d}: t = {load:6.2f} s  |  "
              f"(C - t) = {diff:+7.2f}  |  (C - t)² = {sq:8.2f}")

    total_sq = sum(squared_diffs)
    si = np.sqrt(total_sq / n)
    print("-" * 55)
    print(f"  工站数量 n       = {n}")
    print(f"  Σ(C - t_i)²     = {total_sq:.4f}")
    print(f"  Σ(C - t_i)² / n = {total_sq:.4f} / {n} = {total_sq/n:.4f}")
    print(f"  SI = sqrt({total_sq/n:.4f}) = {si:.4f}")
    print("=" * 55)
    print(f"  ★ 最终平滑指数 SI = {si:.4f}")
    print("=" * 55)

if __name__ == "__main__":
    main_run()