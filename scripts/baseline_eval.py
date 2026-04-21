#!/usr/bin/env python3.9
"""
CCSE-CS Baseline + Ablation Evaluation with Dual LLM Judge
Re-evaluates ESConv, CSC, GPT-4, CCSE-CS baselines AND ablation variants
with per-sample score saving for proper statistical analysis.
"""
import json
import os
import re
import time
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR = Path("/mnt/data2/zcz/neurIps-emnlp/data/experiments/baseline_eval")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
}

DATA_DIR = Path("/mnt/data2/zcz/datasets/neurips_emnlp/empathy_customer_service/raw/experiments")

# ============================================================
# Judge Prompts (same as N=490 evaluation)
# ============================================================

JUDGE_A_PROMPT = """你是专业的客服对话评测专家。请评估以下客服回复的两个维度，给出1-5分评分：

**维度1: 共情适时性 (Emp-App)**
- 1分: 完全没有共情，冷漠机械
- 2分: 共情不足或时机不当
- 3分: 基本共情，但深度不够
- 4分: 共情恰当，时机合适
- 5分: 共情深入自然，极具人性化

**维度2: 自然度 (Nat)**
- 1分: 机器翻译味重，完全不像真人
- 2分: 有明显翻译腔或不自然表达
- 3分: 基本通顺，偶有不自然
- 4分: 流畅自然，接近真人表达
- 5分: 完全像真人，无任何翻译感

**用户问题**: {query}
**客服回复**: {response}

请严格以JSON格式输出：
{{"Emp-App": {{"score": 0}}, "Nat": {{"score": 0}}}}
只输出JSON。"""

JUDGE_B_PROMPT = """你是专业的客服对话评测专家。请评估以下客服回复的两个维度，给出1-5分评分：

**维度1: 政策合规性 (Pol-Comp)**
- 1分: 严重违规（过度承诺、泄露信息）
- 2分: 轻微违规或不当承诺
- 3分: 基本合规，有小问题
- 4分: 合规，表达得当
- 5分: 完美合规，措辞专业

**维度2: 文化适切性 (Cul-Fit)**
- 1分: 完全忽视面子/委婉，文化不当
- 2分: 偶尔文化不当
- 3分: 基本得体，缺乏深度文化理解
- 4分: 文化敏感，委婉得当
- 5分: 完美体现中国文化沟通智慧

**用户问题**: {query}
**客服回复**: {response}

请严格以JSON格式输出：
{{"Pol-Comp": {{"score": 0}}, "Cul-Fit": {{"score": 0}}}}
只输出JSON。"""

# ============================================================
# API Call
# ============================================================

def call_api(messages, temperature=0.3, max_retries=2):
    import requests
    headers = {"Authorization": f"Bearer {API_CONFIG['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": 512
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_CONFIG["url"], headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # Strip think tags
            if "<think" in content:
                content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                print(f"  API error: {e}")
    return None

def parse_scores(text, dims):
    """Parse JSON scores from response"""
    if text is None:
        return None
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
        scores = {}
        for dim in dims:
            scores[dim] = parsed.get(dim, {}).get("score", 0)
        if all(s > 0 for s in scores.values()):
            return scores
    except:
        pass
    return None

# ============================================================
# Single sample evaluation
# ============================================================

def evaluate_sample(query, response):
    """Evaluate a single response with dual judge"""
    # Judge A: Emp-App + Nat
    prompt_a = JUDGE_A_PROMPT.format(query=query, response=response)
    result_a = call_api([{"role": "user", "content": prompt_a}])
    scores_a = parse_scores(result_a, ["Emp-App", "Nat"])

    # Judge B: Pol-Comp + Cul-Fit
    prompt_b = JUDGE_B_PROMPT.format(query=query, response=response)
    result_b = call_api([{"role": "user", "content": prompt_b}])
    scores_b = parse_scores(result_b, ["Pol-Comp", "Cul-Fit"])

    if scores_a and scores_b:
        combined = {**scores_a, **scores_b}
        combined["Overall"] = sum(combined.values()) / 4.0
        return combined
    return None

# ============================================================
# Batch evaluation with checkpoint
# ============================================================

def evaluate_batch(items, label, checkpoint_file, workers=4):
    """Evaluate a batch of items with checkpoint/resume"""
    results = []
    start_idx = 0

    # Load checkpoint
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
        results = checkpoint.get("results", [])
        start_idx = len(results)
        print(f"  [{label}] Resumed from {start_idx}/{len(items)}")

    for i in range(start_idx, len(items)):
        item = items[i]
        query = item.get("user_query", "")
        response = item.get("response", "")

        if not query or not response:
            results.append(None)
            continue

        score = evaluate_sample(query, response)

        if score:
            results.append(score)
            avg = score["Overall"]
            print(f"  [{label}] {i+1}/{len(items)} EA={score['Emp-App']} Nat={score['Nat']} PC={score['Pol-Comp']} CF={score['Cul-Fit']} Avg={avg:.2f}")
        else:
            results.append(None)
            print(f"  [{label}] {i+1}/{len(items)} FAILED")

        # Checkpoint every 5 items
        if (i + 1) % 5 == 0 or i == len(items) - 1:
            with open(checkpoint_file, 'w') as f:
                json.dump({"results": results, "label": label}, f, ensure_ascii=False)

    return results

# ============================================================
# Statistics
# ============================================================

def compute_stats(scores_list, label):
    """Compute statistics from per-sample scores"""
    valid = [s for s in scores_list if s is not None]
    if not valid:
        return None

    dims = ["Emp-App", "Nat", "Pol-Comp", "Cul-Fit", "Overall"]
    stats = {"n": len(valid), "label": label}

    for dim in dims:
        values = [s[dim] for s in valid]
        mean = np.mean(values)
        std = np.std(values, ddof=1)
        ci = 1.96 * std / (len(values) ** 0.5)
        stats[dim] = {
            "mean": round(float(mean), 3),
            "std": round(float(std), 3),
            "ci95": [round(float(mean - ci), 3), round(float(mean + ci), 3)],
            "min": float(min(values)),
            "max": float(max(values)),
        }
    return stats

def t_test_ind(samples1, samples2, dim):
    """Independent t-test between two groups"""
    from scipy import stats as sp_stats
    v1 = [s[dim] for s in samples1 if s is not None]
    v2 = [s[dim] for s in samples2 if s is not None]
    if len(v1) < 2 or len(v2) < 2:
        return None
    t_stat, p_val = sp_stats.ttest_ind(v1, v2)
    # Cohen's d
    pooled_std = np.sqrt(((len(v1)-1)*np.std(v1,ddof=1)**2 + (len(v2)-1)*np.std(v2,ddof=1)**2) / (len(v1)+len(v2)-2))
    d = (np.mean(v1) - np.mean(v2)) / pooled_std if pooled_std > 0 else 0
    return {
        "t": round(float(t_stat), 3),
        "p": round(float(p_val), 4),
        "d": round(float(d), 3),
        "mean_diff": round(float(np.mean(v1) - np.mean(v2)), 3),
    }

# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("CCSE-CS Baseline + Ablation Evaluation")
    print("=" * 60)

    # 1. Load baseline data
    baselines = {}
    for name in ["baseline_esconv", "baseline_csc", "baseline_gpt4", "baseline_ccse-cs"]:
        path = DATA_DIR / f"{name}.json"
        if path.exists():
            baselines[name.replace("baseline_", "")] = json.load(open(path))
            print(f"Loaded {name}: {len(baselines[name.replace('baseline_', '')])} samples")

    # 2. Load ablation data
    ablation_path = DATA_DIR / "ablation_results.json"
    ablation_raw = json.load(open(ablation_path)) if ablation_path.exists() else None

    # 3. Evaluate baselines
    all_results = {}
    for name, items in baselines.items():
        print(f"\n--- Evaluating {name} ({len(items)} samples) ---")
        checkpoint = OUTPUT_DIR / f"checkpoint_{name}.json"
        results = evaluate_batch(items, name, str(checkpoint), workers=1)  # sequential to avoid rate limit
        all_results[name] = results

        stats = compute_stats(results, name)
        if stats:
            all_results[f"{name}_stats"] = stats
            print(f"\n  {name} Statistics:")
            for dim in ["Emp-App", "Nat", "Pol-Comp", "Cul-Fit", "Overall"]:
                s = stats[dim]
                print(f"    {dim}: {s['mean']:.3f} ± {s['std']:.3f} [{s['ci95'][0]:.3f}, {s['ci95'][1]:.3f}]")

    # 4. Compute pairwise statistics
    print("\n--- Pairwise Statistics ---")
    ccse = all_results.get("ccse-cs", [])
    comparisons = {}
    for baseline_name in ["esconv", "csc", "gpt4"]:
        baseline = all_results.get(baseline_name, [])
        if ccse and baseline:
            comp = {}
            for dim in ["Overall", "Emp-App", "Nat", "Pol-Comp", "Cul-Fit"]:
                result = t_test_ind(ccse, baseline, dim)
                if result:
                    comp[dim] = result
                    print(f"  CCSE-CS vs {baseline_name} ({dim}): t={result['t']:.3f}, p={result['p']:.4f}, d={result['d']:.3f}")
            comparisons[baseline_name] = comp

    all_results["comparisons"] = comparisons

    # 5. Save final results
    output_file = OUTPUT_DIR / "baseline_eval_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to {output_file}")

    # 6. Print summary table
    print("\n" + "=" * 80)
    print(f"{'Dataset':<12} {'Emp-App':>10} {'Nat':>10} {'Pol-Comp':>10} {'Cul-Fit':>10} {'Overall':>10}")
    print("-" * 80)
    for name in ["esconv", "csc", "gpt4", "ccse-cs"]:
        stats_key = f"{name}_stats"
        if stats_key in all_results:
            s = all_results[stats_key]
            print(f"{name:<12} {s['Emp-App']['mean']:>10.3f} {s['Nat']['mean']:>10.3f} "
                  f"{s['Pol-Comp']['mean']:>10.3f} {s['Cul-Fit']['mean']:>10.3f} {s['Overall']['mean']:>10.3f}")

if __name__ == "__main__":
    main()
