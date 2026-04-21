#!/usr/bin/env python3
"""
P0-5: 统计显著性分析
对实验结果进行t检验、ANOVA，报告p值
"""

import json
import numpy as np
from scipy import stats
from pathlib import Path
import sys

def calculate_mean_std(scores):
    """计算均值和标准差"""
    return np.mean(scores), np.std(scores, ddof=1)

def independent_t_test(scores1, scores2):
    """独立样本t检验"""
    t_stat, p_value = stats.ttest_ind(scores1, scores2)
    return t_stat, p_value

def paired_t_test(scores1, scores2):
    """配对样本t检验（同一样本不同条件）"""
    t_stat, p_value = stats.ttest_rel(scores1, scores2)
    return t_stat, p_value

def one_way_anova(*groups):
    """单因素方差分析"""
    f_stat, p_value = stats.f_oneway(*groups)
    return f_stat, p_value

def calculate_effect_size(scores1, scores2):
    """计算Cohen's d效应量"""
    n1, n2 = len(scores1), len(scores2)
    var1, var2 = np.var(scores1, ddof=1), np.var(scores2, ddof=1)

    # 合并标准差
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

    # Cohen's d
    cohens_d = (np.mean(scores1) - np.mean(scores2)) / pooled_std

    return cohens_d

def format_p_value(p):
    """格式化p值"""
    if p < 0.001:
        return "p < 0.001***"
    elif p < 0.01:
        return "p < 0.01**"
    elif p < 0.05:
        return "p < 0.05*"
    else:
        return f"p = {p:.3f} (ns)"

def analyze_baseline_comparison(results_file):
    """分析基线对比实验（t检验）"""

    print("\n=== P0-5.1: 基线对比 - t检验 ===\n")

    with open(results_file, 'r') as f:
        data = json.load(f)

    # 假设数据结构：{"baseline_name": [scores...]}
    baselines = ["ESConv", "CSConv", "cuDialog", "CCSE-CS"]

    results = []

    for i, baseline1 in enumerate(baselines):
        for baseline2 in baselines[i+1:]:
            scores1 = data.get(baseline1, [])
            scores2 = data.get(baseline2, [])

            if not scores1 or not scores2:
                continue

            # t检验
            t_stat, p_value = independent_t_test(scores1, scores2)

            # 效应量
            cohens_d = calculate_effect_size(scores1, scores2)

            # 均值
            mean1, std1 = calculate_mean_std(scores1)
            mean2, std2 = calculate_mean_std(scores2)

            results.append({
                "comparison": f"{baseline1} vs {baseline2}",
                "mean1": f"{mean1:.3f}±{std1:.3f}",
                "mean2": f"{mean2:.3f}±{std2:.3f}",
                "diff": f"{mean1-mean2:+.3f}",
                "t_stat": f"{t_stat:.3f}",
                "p_value": format_p_value(p_value),
                "cohens_d": f"{cohens_d:.3f}",
                "significant": p_value < 0.05
            })

    # 打印表格
    print("对比组 | 均值1 | 均值2 | 差值 | t值 | p值 | 效应量")
    print("-" * 80)
    for r in results:
        sig_mark = "***" if r["significant"] else ""
        print(f"{r['comparison']:20s} | {r['mean1']:10s} | {r['mean2']:10s} | {r['diff']:6s} | {r['t_stat']:6s} | {r['p_value']:15s} | {r['cohens_d']:6s} {sig_mark}")

    return results

def analyze_cultural_ablation(results_file):
    """分析文化维度消融（ANOVA）"""

    print("\n=== P0-5.2: 文化维度消融 - 单因素ANOVA ===\n")

    with open(results_file, 'r') as f:
        data = json.load(f)

    # 假设数据结构：{"condition_name": [scores...]}
    conditions = [
        "full_model",
        "ablate_relationship",
        "ablate_face",
        "ablate_euphemism",
        "ablate_conflict",
        "ablate_all"
    ]

    # 准备数据
    groups = []
    for condition in conditions:
        scores = data.get(condition, [])
        if scores:
            groups.append(scores)
            mean, std = calculate_mean_std(scores)
            print(f"{condition:20s}: {mean:.3f}±{std:.3f} (n={len(scores)})")

    # ANOVA
    if len(groups) >= 2:
        f_stat, p_value = one_way_anova(*groups)

        print(f"\nANOVA结果:")
        print(f"  F({len(groups)-1}, {sum(len(g) for g in groups)-len(groups)}) = {f_stat:.3f}")
        print(f"  {format_p_value(p_value)}")

        if p_value < 0.05:
            print("  ✅ 总体显著：至少有一个条件与其他有显著差异")
        else:
            print("  ❌ 总体不显著：各条件之间无显著差异")

    return groups

def analyze_strategy_ablation(results_file):
    """分析策略分类消融（ANOVA）"""

    print("\n=== P0-5.3: 策略分类消融 - 单因素ANOVA ===\n")

    with open(results_file, 'r') as f:
        data = json.load(f)

    conditions = [
        "full_model_18",
        "inherit_only_8",
        "no_upgrade_16",
        "no_novel_10"
    ]

    # 准备数据
    groups = []
    for condition in conditions:
        scores = data.get(condition, [])
        if scores:
            groups.append(scores)
            mean, std = calculate_mean_std(scores)
            print(f"{condition:20s}: {mean:.3f}±{std:.3f} (n={len(scores)})")

    # ANOVA
    if len(groups) >= 2:
        f_stat, p_value = one_way_anova(*groups)

        print(f"\nANOVA结果:")
        print(f"  F({len(groups)-1}, {sum(len(g) for g in groups)-len(groups)}) = {f_stat:.3f}")
        print(f"  {format_p_value(p_value)}")

        if p_value < 0.05:
            print("  ✅ 总体显著：至少有一个条件与其他有显著差异")

            # 事后两两对比
            print("\n  事后对比（t检验）:")
            for i in range(len(groups)):
                for j in range(i+1, len(groups)):
                    t_stat, p_value = stats.ttest_ind(groups[i], groups[j])
                    print(f"    {conditions[i]:20s} vs {conditions[j]:20s}: {format_p_value(p_value)}")
        else:
            print("  ❌ 总体不显著：各条件之间无显著差异")

    return groups

def main():
    """主函数"""

    print("=== P0-5: 统计显著性分析 ===\n")
    print("检验方法：")
    print("  - 独立样本t检验：基线对比")
    print("  - 单因素ANOVA：消融实验")
    print("  - 显著性水平：α = 0.05")
    print("  - 效应量：Cohen's d")

    print("\n⚠️  当前状态: 统计脚本已准备")
    print("⚠️  需要实验结果数据才能运行")
    print("⚠️  待完成: P0-2/P0-3实验生成数据")

    # 生成分析框架
    analysis_framework = {
        "tests": {
            "baseline_comparison": {
                "method": "independent_t_test",
                "pairs": ["ESConv vs CSConv", "ESConv vs cuDialog", "ESConv vs CCSE-CS", "CSConv vs cuDialog", "CSConv vs CCSE-CS", "cuDialog vs CCSE-CS"],
                "alpha": 0.05,
                "effect_size": "cohens_d"
            },
            "cultural_ablation": {
                "method": "one_way_anova",
                "groups": ["full_model", "ablate_relationship", "ablate_face", "ablate_euphemism", "ablate_conflict", "ablate_all"],
                "alpha": 0.05,
                "post_hoc": "paired_t_test"
            },
            "strategy_ablation": {
                "method": "one_way_anova",
                "groups": ["full_model_18", "inherit_only_8", "no_upgrade_16", "no_novel_10"],
                "alpha": 0.05,
                "post_hoc": "paired_t_test"
            }
        },
        "status": "framework_ready",
        "required_data": {
            "baseline_results": "data/evaluation/baseline_results.json",
            "cultural_ablation_results": "data/evaluation/cultural_ablation_results.json",
            "strategy_ablation_results": "data/evaluation/strategy_ablation_results.json"
        },
        "output": "data/evaluation/statistical_analysis.json"
    }

    output_dir = Path('/mnt/data2/zcz/neurIps-emnlp/data/evaluation')
    output_file = output_dir / 'statistical_analysis_framework.json'

    with open(output_file, 'w') as f:
        json.dump(analysis_framework, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 分析框架已保存: {output_file}")

    print("\n预期结果:")
    print("- CCSE-CS vs ESConv: p < 0.05*** (显著优)")
    print("- CCSE-CS vs CSConv: p < 0.05** (显著优)")
    print("- CCSE-CS vs cuDialog: p < 0.05* (边际显著)")
    print("- 完全消融文化维度: p < 0.001*** (极显著下降)")
    print("- 完全消融Novel层: p < 0.01** (显著下降)")

if __name__ == "__main__":
    main()
