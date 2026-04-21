#!/usr/bin/env python3
"""
LLM-as-Judge 评测系统 v2.0
双裁判：Judge-A（偏共情）评估 Emp-App/Nat，Judge-B（偏合规）评估 Pol-Comp/Cul-Fit
支持大规模并发评测 (ThreadPoolExecutor) + 断点续传
"""

import sys
sys.path.insert(0, '/mnt/data2/zcz/neurIps-emnlp')

import json
import re
import os
import time
import random
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ============================================================
# API Config
# ============================================================
API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
}

def call_qwen_api(messages, temperature=0.3, max_tokens=2048, max_retries=3):
    """调用Qwen API"""
    headers = {
        "Authorization": f"Bearer {API_CONFIG['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": max_tokens
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_CONFIG["url"], headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if "<think" in content:
                content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            print(f"  API failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
    return None

# ============================================================
# Judge Prompts
# ============================================================

JUDGE_A_PROMPT = """你是一位专业的客服对话评测专家，专注于共情与自然度评估。

请仔细阅读以下中文客服对话，从两个维度给出1-5分评分：

**维度1: 共情适时性 (Empathy Appropriateness)**
共情表达是否及时（在用户情绪高点附近）、适度（不过度煽情也不冷漠）、方式恰当（使用合适的共情策略）

评分标准：
- 1分: 完全无共情，机械回复
- 2分: 有共情尝试但不及时或不恰当
- 3分: 基本共情到位但深度不够
- 4分: 共情及时适度，方式较好
- 5分: 共情精准到位，时机和方式都恰到好处

**维度2: 自然度 (Naturalness)**
对话是否流畅、符合中文表达习惯、无翻译腔、无生硬模板痕迹

评分标准：
- 1分: 明显翻译腔或模板化，非常不自然
- 2分: 有较多生硬表达，可识别为生成文本
- 3分: 基本流畅但偶有不自然表达
- 4分: 流畅自然，接近真人客服水平
- 5分: 完全自然，无法区分是否为生成文本

**对话内容**：
{dialogue_text}

**请严格以JSON格式输出**：
{{
    "empathy_appropriateness": {{"score": 0, "reasoning": "评分理由"}},
    "naturalness": {{"score": 0, "reasoning": "评分理由"}}
}}

只输出JSON，不要其他内容。"""

JUDGE_B_PROMPT = """你是一位严格的客服对话合规与合规评测专家，专注于政策合规性与文化适切性评估。

请仔细阅读以下中文客服对话，从两个维度给出1-5分评分：

**维度1: 政策合规性 (Policy Compliance)**
客服是否遵守业务规则：不过度承诺赔偿、不越权处理、需要核验时执行核验、涉及升级时规范引导

评分标准：
- 1分: 严重违规，如擅自承诺全额退款、泄露客户信息
- 2分: 有明显不合规表述，如越权承诺、跳过必要核验
- 3分: 基本合规但有轻微不当表述
- 4分: 合规良好，边界处理得当
- 5分: 完全合规，话术规范且灵活

**维度2: 文化适切性 (Cultural Fit)**
是否符合中文客服文化习惯：委婉拒绝而非直接说不、维护客户面子、使用恰当的敬语、根据冲突等级调整语气

评分标准：
- 1分: 完全不考虑文化因素，语气生硬冒犯
- 2分: 偶有文化不适的表现，如直接生硬拒绝
- 3分: 基本得体但缺乏细腻的面子维护
- 4分: 委婉得体，面子维护较好
- 5分: 文化适切性极佳，语气拿捏精准

**对话内容**：
{dialogue_text}

**请严格以JSON格式输出**：
{{
    "policy_compliance": {{"score": 0, "reasoning": "评分理由"}},
    "cultural_fit": {{"score": 0, "reasoning": "评分理由"}}
}}

只输出JSON，不要其他内容。"""

# ============================================================
# Core Functions
# ============================================================

def format_dialogue_for_judge(dialogue: Dict) -> str:
    """格式化对话供评测"""
    meta = dialogue.get('metadata', {})
    domain = meta.get('domain', '未知')
    scenario = meta.get('scenario', '未知')
    conflict = meta.get('conflict_intensity', '未知')

    text = f"【场景】{domain} - {scenario}（冲突等级: {conflict}）\n\n"

    for turn in dialogue.get('dialogue', []):
        speaker = "用户" if turn.get('speaker') == 'user' else "客服"
        text += f"{speaker}: {turn['content']}\n"
        if turn.get('speaker') == 'agent' and turn.get('strategies_used'):
            text += f"  [策略: {', '.join(turn['strategies_used'])}]\n"

    return text

def parse_json_response(response: str) -> Optional[Dict]:
    """从API响应中提取JSON"""
    if response is None:
        return None
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response.strip()
        return json.loads(json_str)
    except:
        # Try to find JSON object directly
        match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\{[^{}]*\}[^{}]*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return None

def evaluate_single_dialogue(dialogue: Dict, dialogue_idx: int) -> Dict:
    """评测单条对话（双裁判）"""
    dialogue_text = format_dialogue_for_judge(dialogue)
    meta = dialogue.get('metadata', {})
    dialogue_id = meta.get('scenario', f'dialogue_{dialogue_idx}')

    # Judge-A: Emp-App + Nat
    prompt_a = JUDGE_A_PROMPT.format(dialogue_text=dialogue_text)
    resp_a = call_qwen_api([{"role": "user", "content": prompt_a}])
    result_a = parse_json_response(resp_a) or {}

    # Judge-B: Pol-Comp + Cul-Fit
    prompt_b = JUDGE_B_PROMPT.format(dialogue_text=dialogue_text)
    resp_b = call_qwen_api([{"role": "user", "content": prompt_b}])
    result_b = parse_json_response(resp_b) or {}

    # Extract scores with fallback
    ea = result_a.get("empathy_appropriateness", {})
    nat = result_a.get("naturalness", {})
    pc = result_b.get("policy_compliance", {})
    cf = result_b.get("cultural_fit", {})

    scores = {
        "empathy_appropriateness": ea.get("score", 0) if isinstance(ea, dict) else 0,
        "naturalness": nat.get("score", 0) if isinstance(nat, dict) else 0,
        "policy_compliance": pc.get("score", 0) if isinstance(pc, dict) else 0,
        "cultural_fit": cf.get("score", 0) if isinstance(cf, dict) else 0,
    }

    return {
        "idx": dialogue_idx,
        "dialogue_id": dialogue_id,
        "domain": meta.get("domain", "unknown"),
        "conflict_intensity": meta.get("conflict_intensity", "unknown"),
        "judge_a": result_a,
        "judge_b": result_b,
        "scores": scores,
        "overall": sum(scores.values()) / 4.0 if all(s > 0 for s in scores.values()) else 0,
    }

# ============================================================
# Stratified Sampling
# ============================================================

def stratified_sample(dialogues: List[Dict], n: int, seed: int = 42) -> List[Tuple[int, Dict]]:
    """按领域+冲突等级分层抽样，返回 (original_idx, dialogue) 列表"""
    random.seed(seed)

    # Group by (domain, conflict_intensity)
    groups = {}
    for i, d in enumerate(dialogues):
        meta = d.get('metadata', {})
        key = (meta.get('domain', 'unknown'), meta.get('conflict_intensity', 'unknown'))
        if key not in groups:
            groups[key] = []
        groups[key].append((i, d))

    # Proportional allocation
    total = len(dialogues)
    sampled = []
    remaining = n

    for key, items in groups.items():
        alloc = max(1, round(len(items) / total * n))
        alloc = min(alloc, len(items), remaining)
        random.shuffle(items)
        sampled.extend(items[:alloc])
        remaining -= alloc

    # If under-sampled due to rounding, fill from remaining
    if remaining > 0:
        sampled_ids = {s[0] for s in sampled}
        pool = [(i, d) for i, d in enumerate(dialogues) if i not in sampled_ids]
        random.shuffle(pool)
        sampled.extend(pool[:remaining])

    return sampled

# ============================================================
# Main Evaluation with Checkpoint
# ============================================================

def run_evaluation(
    data_path: str,
    n_samples: int = 500,
    workers: int = 4,
    checkpoint_dir: str = '/mnt/data2/zcz/neurIps-emnlp/data/raw/judge_checkpoint',
):
    """运行大规模评测"""
    os.makedirs(checkpoint_dir, exist_ok=True)

    # Load data
    print(f"Loading data from {data_path}...")
    with open(data_path, 'r', encoding='utf-8') as f:
        all_dialogues = json.load(f)
    print(f"Total dialogues: {len(all_dialogues)}")

    # Stratified sample
    sampled = stratified_sample(all_dialogues, min(n_samples, len(all_dialogues)))
    print(f"Sampled {len(sampled)} dialogues (stratified by domain × conflict)")

    # Domain/conflict distribution
    domain_counts = {}
    for _, d in sampled:
        dom = d.get('metadata', {}).get('domain', 'unknown')
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
    print(f"Domain distribution: {domain_counts}")

    # Check for existing checkpoint
    checkpoint_file = os.path.join(checkpoint_dir, 'progress.txt')
    results_file = os.path.join(checkpoint_dir, 'results.json')

    start_idx = 0
    results = []
    if os.path.exists(checkpoint_file):
        start_idx = int(open(checkpoint_file).read().strip())
        print(f"Resuming from checkpoint: {start_idx}/{len(sampled)}")
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)

    # Evaluate in chunks with ThreadPoolExecutor
    chunk_size = 20  # Save checkpoint every 20 dialogues
    chunks = [sampled[i:i+chunk_size] for i in range(0, len(sampled), chunk_size)]

    for chunk_idx, chunk in enumerate(chunks):
        if chunk_idx * chunk_size < start_idx:
            continue

        print(f"\n--- Chunk {chunk_idx+1}/{len(chunks)} ({len(chunk)} dialogues) ---")
        chunk_results = [None] * len(chunk)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(evaluate_single_dialogue, d, idx): i
                for i, (idx, d) in enumerate(chunk)
            }
            for future in as_completed(futures):
                i = futures[future]
                try:
                    chunk_results[i] = future.result()
                    scores = chunk_results[i]['scores']
                    print(f"  [{len(results) + i + 1}/{len(sampled)}] {chunk_results[i]['domain']} | "
                          f"EA={scores['empathy_appropriateness']} Nat={scores['naturalness']} "
                          f"PC={scores['policy_compliance']} CF={scores['cultural_fit']} "
                          f"Avg={chunk_results[i]['overall']:.2f}")
                except Exception as e:
                    print(f"  ⚠️  Evaluation failed: {e}")
                    chunk_results[i] = None

        # Append successful results
        results.extend([r for r in chunk_results if r is not None and r.get('overall', 0) > 0])

        # Save checkpoint
        with open(checkpoint_file, 'w') as f:
            f.write(str((chunk_idx + 1) * chunk_size))
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"  Checkpoint saved: {len(results)} results so far")

    # ============================================================
    # Statistics
    # ============================================================
    print(f"\n{'='*60}")
    print(f"EVALUATION COMPLETE: {len(results)} dialogues evaluated")
    print(f"{'='*60}")

    valid_results = [r for r in results if r.get('overall', 0) > 0]
    n_valid = len(valid_results)

    if n_valid == 0:
        print("No valid results!")
        return valid_results

    # Overall statistics
    dims = ['empathy_appropriateness', 'naturalness', 'policy_compliance', 'cultural_fit']
    print(f"\n{'Dimension':<30} {'Mean':>6} {'Std':>6} {'Median':>6} {'Min':>4} {'Max':>4} {'95% CI':>12}")
    print("-" * 80)

    stats = {}
    for dim in dims:
        scores = [r['scores'][dim] for r in valid_results if r['scores'][dim] > 0]
        if not scores:
            continue
        mean = sum(scores) / len(scores)
        std = (sum((s - mean)**2 for s in scores) / len(scores)) ** 0.5
        median = sorted(scores)[len(scores)//2]
        ci95 = 1.96 * std / (len(scores) ** 0.5)
        stats[dim] = {"mean": mean, "std": std, "n": len(scores), "ci95": ci95}
        print(f"{dim:<30} {mean:>6.2f} {std:>6.3f} {median:>6.1f} {min(scores):>4} {max(scores):>4} [{mean-ci95:.2f}, {mean+ci95:.2f}]")

    overall_scores = [r['overall'] for r in valid_results]
    overall_mean = sum(overall_scores) / len(overall_scores)
    overall_std = (sum((s - overall_mean)**2 for s in overall_scores) / len(overall_scores)) ** 0.5
    print(f"\n{'Overall (CCSE-CS)':<30} {overall_mean:>6.2f} {overall_std:>6.3f}")

    # Per-domain statistics
    print(f"\n{'='*40}")
    print("Per-Domain Statistics")
    print(f"{'='*40}")
    for domain in sorted(set(r['domain'] for r in valid_results)):
        domain_results = [r for r in valid_results if r['domain'] == domain]
        domain_mean = sum(r['overall'] for r in domain_results) / len(domain_results)
        print(f"  {domain}: n={len(domain_results)}, Overall={domain_mean:.2f}")

    # Per-conflict statistics
    print(f"\nPer-Conflict Statistics")
    for conflict in sorted(set(r['conflict_intensity'] for r in valid_results)):
        conflict_results = [r for r in valid_results if r['conflict_intensity'] == conflict]
        conflict_mean = sum(r['overall'] for r in conflict_results) / len(conflict_results)
        print(f"  {conflict}: n={len(conflict_results)}, Overall={conflict_mean:.2f}")

    # Save final results
    final_file = f'/mnt/data2/zcz/neurIps-emnlp/data/raw/llm_judge_N{n_valid}_{int(time.time())}.json'
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "n_samples": n_valid,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": API_CONFIG["model_name"],
            },
            "statistics": stats,
            "overall_mean": overall_mean,
            "overall_std": overall_std,
            "results": valid_results
        }, f, ensure_ascii=False, indent=2)

    print(f"\nFinal results saved to: {final_file}")
    return valid_results

# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='/mnt/data2/zcz/neurIps-emnlp/data/raw/ccse_cs_clean.json',
                        help='Path to dialogue data file')
    parser.add_argument('--n', type=int, default=500, help='Number of samples to evaluate')
    parser.add_argument('--workers', type=int, default=4, help='Concurrent API workers')
    args = parser.parse_args()

    run_evaluation(args.data, n_samples=args.n, workers=args.workers)
