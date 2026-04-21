"""
Generate Figure 7: Cross-domain coverage comparison bar chart
Updated with real Math + Dialogue data; Code placeholder
"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

OUTPUT_DIR = Path("/tmp/neurips_paper/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Try to load Code results
code_results_path = Path("/tmp/qd_experiments/code/code_results.json")
has_code = code_results_path.exists()

if has_code:
    with open(code_results_path) as f:
        code_data = json.load(f)
    code_qd = code_data['QD-Synth']['coverage'] * 100
    code_greedy = code_data['Greedy-Quality']['coverage'] * 100
    code_random = code_data['Random-Subset']['coverage'] * 100
    code_cluster = code_data['Cluster-Sampling']['coverage'] * 100
    code_dedup = code_data['Deduplication']['coverage'] * 100
    print(f"Code results loaded: QD={code_qd:.2f}%, Greedy={code_greedy:.2f}%")
else:
    print("Code results not yet available - skipping figure generation")
    exit(0)

# Real Math results
math_qd = 2.30
math_greedy = 1.00
math_random = 1.00
math_cluster = 1.10
math_dedup = 1.10

# Real Dialogue results (r=10)
dial_qd = 5.70
dial_greedy = 0.80
dial_random = 2.40
dial_cluster = 2.50
dial_dedup = 4.30

domains = ['Math', 'Code', 'Dialogue']
methods = ['Greedy', 'Random', 'Cluster', 'Dedup', 'QD-Synth']
colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']

coverage_data = {
    'Greedy': [math_greedy, code_greedy, dial_greedy],
    'Random': [math_random, code_random, dial_random],
    'Cluster': [math_cluster, code_cluster, dial_cluster],
    'Dedup': [math_dedup, code_dedup, dial_dedup],
    'QD-Synth': [math_qd, code_qd, dial_qd],
}

fig, ax = plt.subplots(figsize=(10, 4.5))

x = np.arange(len(domains))
width = 0.15
offsets = np.arange(len(methods)) - (len(methods) - 1) / 2

for i, method in enumerate(methods):
    bars = ax.bar(x + offsets[i] * width, coverage_data[method], width,
                  label=method, color=colors[i], edgecolor='black', linewidth=0.5)
    # Add value labels on QD-Synth bars
    if method == 'QD-Synth':
        for j, v in enumerate(coverage_data[method]):
            ax.text(x[j] + offsets[i] * width, v + 0.15, f'{v:.1f}%',
                   ha='center', va='bottom', fontsize=8, fontweight='bold')

ax.set_xlabel('Domain', fontsize=12)
ax.set_ylabel('Grid Coverage (%)', fontsize=12)
ax.set_title('Cross-Domain Coverage Comparison ($r$=10, $d$=3)', fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(domains, fontsize=11)
ax.legend(fontsize=9, loc='upper left')
ax.grid(axis='y', alpha=0.3)

# Add improvement ratio annotations
for i, domain in enumerate(domains):
    qd_val = coverage_data['QD-Synth'][i]
    greedy_val = coverage_data['Greedy'][i]
    if greedy_val > 0:
        ratio = qd_val / greedy_val
        ax.annotate(f'{ratio:.1f}×', xy=(x[i] + offsets[-1] * width + width/2, qd_val),
                   xytext=(x[i] + offsets[-1] * width + width/2 + 0.15, qd_val + 0.8),
                   fontsize=9, fontweight='bold', color='#9b59b6',
                   arrowprops=dict(arrowstyle='->', color='#9b59b6', lw=1.5))

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'fig7_cross_domain.pdf', dpi=300, bbox_inches='tight')
plt.savefig(OUTPUT_DIR / 'fig7_cross_domain.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"Fig 7 saved to {OUTPUT_DIR}")
