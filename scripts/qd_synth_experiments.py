"""
QD-Synth 真实实验脚本
=====================
对比 QD-Synth vs 4 baselines 在 Math/Code/Dialogue 三域的表现
所有数据真实生成，零占位符

用法:
    python scripts/qd_synth_experiments.py --samples 200 --workers 4
    python scripts/qd_synth_experiments.py --domain dialogue --samples 522  # 仅Dialogue域
"""

import json
import os
import sys
import re
import time
import random
import argparse
import hashlib
import math
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

import requests
import numpy as np
from tqdm import tqdm

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))
from configs.strategy_ontology import (
    STRATEGY_ONTOLOGY, DOMAINS, CULTURAL_FACTORS, ALL_STRATEGY_IDS
)

# ============================================================
# API配置
# ============================================================
API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
    "top_p": 0.9,
}


def call_api(messages, temperature=0.8, max_tokens=4096, max_retries=3):
    headers = {
        "Authorization": f"Bearer {API_CONFIG['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "top_p": API_CONFIG["top_p"],
        "max_tokens": max_tokens
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_CONFIG["url"], headers=headers,
                                json=payload, timeout=120)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if "<think" in content:
                content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content,
                                flags=re.DOTALL).strip()
            return content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return None


def extract_json(text):
    if not text:
        return None
    for delim in ["```json", "```"]:
        if delim in text:
            parts = text.split(delim)
            if len(parts) >= 2:
                candidate = parts[1].split("```")[0].strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    # Try array
    start, end = text.find('['), text.rfind(']')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


# ============================================================
# 行为描述子计算
# ============================================================

def compute_math_descriptor(problem_data: dict) -> np.ndarray:
    """Math域行为描述子: (difficulty, steps, multi_step)"""
    diff = problem_data.get("difficulty", 3)
    steps = problem_data.get("num_steps", 1)
    multi = 1.0 if steps >= 3 else 0.0

    d_diff = min(1.0, (diff - 1) / 4.0)  # 1-5 -> 0-1
    d_steps = min(1.0, (steps - 1) / 6.0)  # 1-7 -> 0-1
    d_multi = multi

    return np.array([d_diff, d_steps, d_multi])


def compute_code_descriptor(problem_data: dict) -> np.ndarray:
    """Code域行为描述子: (difficulty, api_diversity, needs_debugging)"""
    diff = problem_data.get("difficulty", 3)
    apis = problem_data.get("num_apis", 2)
    debug = 1.0 if problem_data.get("needs_debugging", False) else 0.0

    d_diff = min(1.0, (diff - 1) / 4.0)
    d_apis = min(1.0, (apis - 1) / 5.0)
    d_debug = debug

    return np.array([d_diff, d_apis, d_debug])


def compute_dialogue_descriptor(dialogue_data: dict) -> np.ndarray:
    """Dialogue域行为描述子: (empathy, strategy_category, conflict)"""
    dialogue = dialogue_data.get("dialogue", [])
    metadata = dialogue_data.get("metadata", {})

    # Empathy strength
    empathy_strategies = {"S2", "S7", "S8", "S9"}
    empathy_count = 0
    agent_turns = 0
    for turn in dialogue:
        if turn.get("speaker") == "agent":
            agent_turns += 1
            if any(s in empathy_strategies for s in turn.get("strategies_used", [])):
                empathy_count += 1
    empathy = min(1.0, empathy_count / max(1, agent_turns))

    # Strategy category (main category index / 5)
    category_map = {
        "C1": ["S1", "S2", "S3"], "C2": ["S4", "S5", "S6"],
        "C3": ["S7", "S8", "S9"], "C4": ["S10", "S11", "S12"],
        "C5": ["S13", "S14", "S15"], "C6": ["S16", "S17", "S18"]
    }
    cat_counts = {k: 0 for k in category_map}
    for turn in dialogue:
        if turn.get("speaker") == "agent":
            for s in turn.get("strategies_used", []):
                for cat, strategies in category_map.items():
                    if s in strategies:
                        cat_counts[cat] += 1
    main_cat = max(cat_counts, key=cat_counts.get)
    strategy_cat = list(category_map.keys()).index(main_cat) / 5.0

    # Conflict
    conflict_map = {"低": 0.25, "中": 0.5, "高": 0.75}
    conflict = conflict_map.get(metadata.get("conflict_level", "中"), 0.5)

    return np.array([empathy, strategy_cat, conflict])


# ============================================================
# 质量评估
# ============================================================

def compute_math_quality(problem_data: dict) -> float:
    """Math域质量评分"""
    score = 0.0
    # Has complete solution
    if "solution" in problem_data and problem_data["solution"]:
        score += 0.3
    # Has step-by-step reasoning
    solution = str(problem_data.get("solution", ""))
    if any(kw in solution for kw in ["Step", "步骤", "首先", "然后", "因此", "所以"]):
        score += 0.2
    # Has correct answer format
    if "answer" in problem_data and problem_data["answer"]:
        score += 0.2
    # Problem is well-formed
    problem = str(problem_data.get("problem", ""))
    if len(problem) > 20 and any(c.isdigit() for c in problem):
        score += 0.15
    # Difficulty matches
    diff = problem_data.get("difficulty", 3)
    if 1 <= diff <= 5:
        score += 0.15
    return min(1.0, score)


def compute_code_quality(problem_data: dict) -> float:
    """Code域质量评分"""
    score = 0.0
    # Has function signature
    if "function_signature" in problem_data or "prompt" in problem_data:
        score += 0.25
    # Has test cases
    if "test_cases" in problem_data and problem_data["test_cases"]:
        score += 0.25
    # Has solution attempt
    if "solution" in problem_data and problem_data["solution"]:
        score += 0.2
        sol = str(problem_data["solution"])
        if "def " in sol or "function" in sol:
            score += 0.1
    # Has docstring
    if "description" in problem_data and len(str(problem_data["description"])) > 30:
        score += 0.1
    # Difficulty is reasonable
    diff = problem_data.get("difficulty", 3)
    if 1 <= diff <= 5:
        score += 0.1
    return min(1.0, score)


def compute_dialogue_quality(dialogue_data: dict) -> float:
    """Dialogue域质量评分"""
    dialogue = dialogue_data.get("dialogue", [])
    metadata = dialogue_data.get("metadata", {})

    # Empathy (0.25)
    empathy_strategies = {"S2", "S7", "S8", "S9"}
    empathy_count = sum(
        1 for t in dialogue if t.get("speaker") == "agent"
        and any(s in empathy_strategies for s in t.get("strategies_used", []))
    )
    agent_turns = sum(1 for t in dialogue if t.get("speaker") == "agent")
    emp_score = min(1.0, empathy_count / max(1, agent_turns))

    # Policy compliance (0.25)
    quality_check = dialogue_data.get("quality_self_check", {})
    pol_score = 1.0 if all([
        quality_check.get("policy_compliant", True),
        quality_check.get("no_overcommitment", True),
        quality_check.get("no_emotion_manipulation", True)
    ]) else 0.5

    # Strategy coverage (0.25)
    strategies = set()
    for t in dialogue:
        if t.get("speaker") == "agent":
            for s in t.get("strategies_used", []):
                strategies.add(s)
    strat_score = min(1.0, len(strategies) / 6.0)  # 6 strategies = full

    # Naturalness (0.25)
    total_chars = sum(len(t.get("content", "")) for t in dialogue)
    nat_score = min(1.0, max(0.0, (total_chars - 100) / 1500))

    return emp_score * 0.25 + pol_score * 0.25 + strat_score * 0.25 + nat_score * 0.25


# ============================================================
# MAP-Elites Archive (QD-Synth核心)
# ============================================================

class MAPelitesArchive:
    def __init__(self, descriptor_fn, quality_fn, grid_res=10, dim=3):
        self.descriptor_fn = descriptor_fn
        self.quality_fn = quality_fn
        self.grid_res = grid_res
        self.dim = dim
        self.archive = {}  # grid_coord -> (sample, quality, descriptor)
        self.history = []  # (iteration, coverage, entropy, avg_quality, num_samples)

    def discretize(self, descriptor):
        return tuple(
            int(min(d * self.grid_res, self.grid_res - 1))
            for d in descriptor
        )

    def add(self, sample):
        desc = self.descriptor_fn(sample)
        quality = self.quality_fn(sample)
        coord = self.discretize(desc)

        added = False
        if coord not in self.archive:
            self.archive[coord] = (sample, quality, desc)
            added = True
        elif quality > self.archive[coord][1]:
            self.archive[coord] = (sample, quality, desc)
            added = True
        return added, coord, quality

    def get_coverage(self):
        total = self.grid_res ** self.dim
        return len(self.archive) / total

    def get_entropy(self):
        if not self.archive:
            return 0.0
        qualities = [v[1] for v in self.archive.values()]
        total = sum(qualities) + 1e-10
        probs = [q / total for q in qualities]
        return -sum(p * np.log(p + 1e-10) for p in probs if p > 0)

    def get_avg_quality(self):
        if not self.archive:
            return 0.0
        return np.mean([v[1] for v in self.archive.values()])

    def get_samples(self):
        return [v[0] for v in self.archive.values()]

    def record_history(self, iteration):
        self.history.append({
            "iteration": iteration,
            "coverage": self.get_coverage(),
            "entropy": self.get_entropy(),
            "avg_quality": self.get_avg_quality(),
            "num_samples": len(self.archive)
        })


# ============================================================
# Baselines
# ============================================================

def greedy_quality_select(samples, quality_fn, k):
    """Greedy: keep top-K by quality"""
    scored = [(s, quality_fn(s)) for s in samples]
    scored.sort(key=lambda x: -x[1])
    return [s for s, _ in scored[:k]]


def random_select(samples, k, seed=42):
    """Random: random sampling"""
    rng = random.Random(seed)
    return rng.sample(samples, min(k, len(samples)))


def cluster_select(samples, descriptor_fn, k, n_clusters=10, seed=42):
    """Cluster: K-means on descriptors, sample per cluster"""
    if len(samples) <= k:
        return samples

    descs = np.array([descriptor_fn(s) for s in samples])
    n_clusters = min(n_clusters, len(samples))

    # Simple K-means
    rng = np.random.RandomState(seed)
    indices = rng.choice(len(samples), n_clusters, replace=False)
    centroids = descs[indices].copy()

    for _ in range(20):
        # Assign
        dists = np.linalg.norm(descs[:, None] - centroids[None, :], axis=2)
        labels = np.argmin(dists, axis=1)
        # Update
        new_centroids = np.zeros_like(centroids)
        for c in range(n_clusters):
            mask = labels == c
            if mask.any():
                new_centroids[c] = descs[mask].mean(axis=0)
            else:
                new_centroids[c] = centroids[c]
        if np.allclose(centroids, new_centroids, atol=1e-6):
            break
        centroids = new_centroids

    # Sample per cluster
    per_cluster = max(1, k // n_clusters)
    selected = []
    for c in range(n_clusters):
        mask = labels == c
        cluster_samples = [s for s, m in zip(samples, mask) if m]
        rng2 = random.Random(seed + c)
        sel = rng2.sample(cluster_samples, min(per_cluster, len(cluster_samples)))
        selected.extend(sel)

    return selected[:k]


def dedup_select(samples, descriptor_fn, k, quality_fn, similarity_threshold=0.15):
    """Dedup: remove near-duplicates in descriptor space, keep highest quality"""
    if len(samples) <= k:
        return samples

    descs = np.array([descriptor_fn(s) for s in samples])
    qualities = np.array([quality_fn(s) for s in samples])

    # Sort by quality descending
    order = np.argsort(-qualities)
    selected = []
    selected_descs = []

    for idx in order:
        if len(selected) >= k:
            break
        d = descs[idx]
        # Check similarity with already selected
        too_similar = False
        for sd in selected_descs:
            sim = 1.0 - np.linalg.norm(d - sd)
            if sim > (1.0 - similarity_threshold):
                too_similar = True
                break
        if not too_similar:
            selected.append(samples[idx])
            selected_descs.append(d)

    return selected


# ============================================================
# Self-BLEU 计算
# ============================================================

def compute_self_bleu(samples, text_fn, max_n=4):
    """计算Self-BLEU: 越低越好（表明多样性越高）"""
    def tokenize(text):
        # Simple character-level tokenization for Chinese
        text = str(text)
        return [c for c in text if c.strip()]

    texts = [tokenize(text_fn(s)) for s in samples]
    if len(texts) < 2:
        return 1.0

    scores = []
    for i, hyp in enumerate(texts):
        if len(hyp) < 2:
            continue
        refs = [texts[j] for j in range(len(texts)) if j != i]
        # BLEU-like score
        ref_tokens = Counter()
        for r in refs:
            ref_tokens.update(r)

        # Unigram precision
        hyp_counts = Counter(hyp)
        clipped = sum(min(c, ref_tokens.get(t, 0)) for t, c in hyp_counts.items())
        total = max(1, sum(hyp_counts.values()))
        precision = clipped / total if total > 0 else 0

        # Brevity penalty
        ref_len = np.mean([len(r) for r in refs])
        bp = min(1.0, np.exp(1 - ref_len / max(1, len(hyp))))

        scores.append(bp * precision)

    return np.mean(scores) if scores else 1.0


def compute_embedding_diversity(samples, text_fn):
    """基于文本长度的多样性代理（无需embedding模型）"""
    texts = [str(text_fn(s)) for s in samples]
    if len(texts) < 2:
        return 0.0

    # Use character n-gram overlap as diversity proxy
    def get_ngrams(text, n=3):
        return set(text[i:i+n] for i in range(max(0, len(text) - n + 1)))

    ngrams_list = [get_ngrams(t) for t in texts]
    overlaps = []
    for i in range(min(len(ngrams_list), 100)):
        for j in range(i + 1, min(len(ngrams_list), 100)):
            if ngrams_list[i] and ngrams_list[j]:
                overlap = len(ngrams_list[i] & ngrams_list[j]) / max(
                    len(ngrams_list[i]), len(ngrams_list[j]))
                overlaps.append(overlap)

    avg_overlap = np.mean(overlaps) if overlaps else 1.0
    return 1.0 - avg_overlap  # Higher = more diverse


# ============================================================
# Math域生成
# ============================================================

def generate_math_problem(task_idx, difficulty=None):
    """生成一条GSM8K-style数学问题"""
    if difficulty is None:
        difficulty = random.randint(1, 5)

    diff_desc = {1: "very easy (elementary)", 2: "easy", 3: "medium",
                 4: "hard (multi-step)", 5: "very hard (complex reasoning)"}
    steps_range = {1: "1-2", 2: "2-3", 3: "3-4", 4: "4-5", 5: "5-7"}
    num_steps = random.randint(
        *{1: (1, 2), 2: (2, 3), 3: (3, 4), 4: (4, 5), 5: (5, 7)}[difficulty]
    )

    prompt = f"""Generate a GSM8K-style math word problem.

Requirements:
- Difficulty: {diff_desc[difficulty]} (level {difficulty}/5)
- Number of reasoning steps: {num_steps}
- Use realistic numbers and scenarios
- Include a clear final answer

Output JSON:
{{"problem": "...", "solution": "Step 1: ...\\nStep 2: ...\\n...", "answer": "numerical answer", "difficulty": {difficulty}, "num_steps": {num_steps}}}

Only output JSON."""

    resp = call_api([{"role": "user", "content": prompt}], temperature=0.85)
    data = extract_json(resp)
    if data and "problem" in data:
        data["task_idx"] = task_idx
        data["difficulty"] = difficulty
        data["num_steps"] = num_steps
        return data
    return None


# ============================================================
# Code域生成
# ============================================================

def generate_code_problem(task_idx, difficulty=None):
    """生成一条HumanEval-style编程问题"""
    if difficulty is None:
        difficulty = random.randint(1, 5)

    diff_desc = {1: "very easy (single function)", 2: "easy",
                 3: "medium (data structures)", 4: "hard (algorithms)",
                 5: "very hard (complex logic)"}
    num_apis = random.randint(1, min(difficulty + 1, 6))
    needs_debug = random.random() < (difficulty / 6.0)

    prompt = f"""Generate a HumanEval-style Python programming problem.

Requirements:
- Difficulty: {diff_desc[difficulty]} (level {difficulty}/5)
- Number of distinct Python standard library APIs used: {num_apis}
- Needs debugging: {"Yes" if needs_debug else "No"}
- Include function signature, description, and at least 2 test cases

Output JSON:
{{"prompt": "def function_name(...):\\n    '''Description'''", "description": "...", "function_signature": "def function_name(param1, param2):", "solution": "def function_name(...):\\n    # implementation\\n    return ...", "test_cases": ["assert function_name(...) == ...", "assert function_name(...) == ..."], "difficulty": {difficulty}, "num_apis": {num_apis}, "needs_debugging": {"true" if needs_debug else "false"}}}

Only output JSON."""

    resp = call_api([{"role": "user", "content": prompt}], temperature=0.85)
    data = extract_json(resp)
    if data and ("prompt" in data or "description" in data):
        data["task_idx"] = task_idx
        data["difficulty"] = difficulty
        data["num_apis"] = num_apis
        data["needs_debugging"] = needs_debug
        return data
    return None


# ============================================================
# QD-Synth Mutation Operators
# ============================================================

def mutate_math(parent, target_empty_cells=None):
    """变异Math问题: 朝未覆盖区域探索"""
    current_diff = parent.get("difficulty", 3)
    current_steps = parent.get("num_steps", 3)

    # Decide mutation direction
    if target_empty_cells:
        # Target a specific empty cell
        target = random.choice(target_empty_cells)
        new_diff = int(target[0] / 10 * 5) + 1
        new_steps = int(target[1] / 10 * 7) + 1
        new_diff = max(1, min(5, new_diff))
        new_steps = max(1, min(7, new_steps))
    else:
        # Random perturbation
        new_diff = max(1, min(5, current_diff + random.choice([-1, 0, 1])))
        new_steps = max(1, min(7, current_steps + random.choice([-1, 0, 1, 1])))

    prompt = f"""Modify this math problem to be at difficulty level {new_diff}/5 with {new_steps} reasoning steps.

Original problem: {parent.get('problem', '')}

Create a NEW problem (not just rewording) with:
- Difficulty: {new_diff}/5
- Steps: {new_steps}
- Different numbers and scenario

Output JSON:
{{"problem": "...", "solution": "Step 1: ...", "answer": "...", "difficulty": {new_diff}, "num_steps": {new_steps}}}

Only output JSON."""

    resp = call_api([{"role": "user", "content": prompt}], temperature=0.9)
    data = extract_json(resp)
    if data and "problem" in data:
        data["difficulty"] = new_diff
        data["num_steps"] = new_steps
        data["parent_id"] = parent.get("task_idx", -1)
        return data
    return None


def mutate_code(parent, target_empty_cells=None):
    """变异Code问题"""
    current_diff = parent.get("difficulty", 3)
    current_apis = parent.get("num_apis", 2)

    if target_empty_cells:
        target = random.choice(target_empty_cells)
        new_diff = int(target[0] / 10 * 5) + 1
        new_apis = int(target[1] / 10 * 6) + 1
        new_diff = max(1, min(5, new_diff))
        new_apis = max(1, min(6, new_apis))
    else:
        new_diff = max(1, min(5, current_diff + random.choice([-1, 0, 1])))
        new_apis = max(1, min(6, current_apis + random.choice([-1, 0, 1])))

    prompt = f"""Modify this programming problem to use {new_apis} APIs at difficulty {new_diff}/5.

Original: {parent.get('prompt', parent.get('description', ''))}

Create a NEW problem with different functionality:
- Difficulty: {new_diff}/5
- APIs: {new_apis}
- Different domain (e.g., string/math/file/list processing)

Output JSON:
{{"prompt": "def ...", "description": "...", "function_signature": "...", "solution": "...", "test_cases": ["assert ...", "assert ..."], "difficulty": {new_diff}, "num_apis": {new_apis}, "needs_debugging": false}}

Only output JSON."""

    resp = call_api([{"role": "user", "content": prompt}], temperature=0.9)
    data = extract_json(resp)
    if data and ("prompt" in data or "description" in data):
        data["difficulty"] = new_diff
        data["num_apis"] = new_apis
        data["needs_debugging"] = parent.get("needs_debugging", False)
        return data
    return None


# ============================================================
# Main Experiment Pipeline
# ============================================================

def run_math_experiment(n_samples=200, n_workers=4):
    """Math域完整实验: QD-Synth vs 4 baselines"""
    print("\n" + "="*60)
    print("MATH DOMAIN EXPERIMENT")
    print(f"Samples per method: {n_samples}")
    print("="*60)

    output_dir = Path("/tmp/qd_experiments/math")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate pool of math problems
    pool_file = output_dir / "math_pool.json"
    if pool_file.exists():
        print("Loading existing math pool...")
        pool = json.load(open(pool_file))
    else:
        print("Generating math problem pool...")
        tasks = []
        for i in range(n_samples * 3):  # Generate 3x for selection
            diff = (i % 5) + 1  # Balanced difficulty
            tasks.append((i, diff))

        pool = []
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(generate_math_problem, i, d): i
                      for i, d in tasks}
            for future in tqdm(as_completed(futures), total=len(futures),
                             desc="Math pool"):
                result = future.result()
                if result:
                    pool.append(result)

        json.dump(pool, open(pool_file, 'w'), ensure_ascii=False, indent=2)
        print(f"Pool: {len(pool)} problems generated")

    if not pool:
        print("ERROR: No math problems generated!")
        return None

    # Step 2: Run QD-Synth
    print("\n--- QD-Synth (MAP-Elites) ---")
    qd_archive = MAPelitesArchive(compute_math_descriptor, compute_math_quality,
                                   grid_res=10, dim=3)

    # Initialize with pool
    for p in pool:
        qd_archive.add(p)
    qd_archive.record_history(0)

    # Iterate: mutate from existing samples
    qd_samples = list(qd_archive.get_samples())
    mutation_rounds = min(3, max(1, n_samples // 50))
    for round_idx in range(mutation_rounds):
        print(f"  Mutation round {round_idx+1}/{mutation_rounds}...")
        parents = random.sample(qd_samples, min(50, len(qd_samples)))
        new_samples = []
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(mutate_math, p): i
                      for i, p in enumerate(parents)}
            for future in tqdm(as_completed(futures), total=len(futures)):
                result = future.result()
                if result:
                    new_samples.append(result)

        added = 0
        for s in new_samples:
            was_added, _, _ = qd_archive.add(s)
            if was_added:
                added += 1
        qd_archive.record_history(round_idx + 1)
        qd_samples = qd_archive.get_samples()
        print(f"    Added {added}/{len(new_samples)}, total: {len(qd_archive.archive)}")

    qd_results = qd_archive.get_samples()

    # Step 3: Run baselines
    k = len(qd_results)  # Match QD output size
    print(f"\n--- Baselines (k={k}) ---")

    greedy_results = greedy_quality_select(pool, compute_math_quality, k)
    random_results = random_select(pool, k)
    cluster_results = cluster_select(pool, compute_math_descriptor, k, n_clusters=20)
    dedup_results = dedup_select(pool, compute_math_descriptor, k, compute_math_quality)

    # Step 4: Compute metrics
    print("\n--- Computing Metrics ---")
    methods = {
        "Greedy-Quality": greedy_results,
        "Random-Subset": random_results,
        "Cluster-Sampling": cluster_results,
        "Deduplication": dedup_results,
        "QD-Synth": qd_results,
    }

    results = {}
    for name, samples in methods.items():
        if not samples:
            continue

        # Grid coverage
        descs = [compute_math_descriptor(s) for s in samples]
        grid_coords = set(
            tuple(int(min(d * 10, 9)) for d in desc)
            for desc in descs
        )
        coverage = len(grid_coords) / (10 ** 3)

        # Entropy
        qualities = [compute_math_quality(s) for s in samples]
        total_q = sum(qualities) + 1e-10
        probs = [q / total_q for q in qualities]
        entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)

        # Self-BLEU
        self_bleu = compute_self_bleu(samples, lambda s: s.get("problem", ""))

        # Avg quality
        avg_quality = np.mean(qualities)

        # Difficulty distribution
        diff_dist = Counter(s.get("difficulty", 0) for s in samples)

        # Hard example coverage (difficulty 4-5)
        hard = sum(1 for s in samples if s.get("difficulty", 0) >= 4)
        hard_ratio = hard / len(samples)

        results[name] = {
            "n_samples": len(samples),
            "coverage": coverage,
            "entropy": entropy,
            "self_bleu": self_bleu,
            "avg_quality": avg_quality,
            "difficulty_dist": dict(diff_dist),
            "hard_ratio": hard_ratio,
        }

        print(f"  {name}: coverage={coverage:.2%}, entropy={entropy:.3f}, "
              f"self_bleu={self_bleu:.3f}, quality={avg_quality:.3f}, "
              f"hard={hard_ratio:.2%}")

    # Save results
    results["metadata"] = {
        "domain": "math",
        "pool_size": len(pool),
        "grid_res": 10,
        "dim": 3,
        "qd_history": qd_archive.history,
        "timestamp": datetime.now().isoformat()
    }

    out_file = output_dir / "math_results.json"
    json.dump(results, open(out_file, 'w'), ensure_ascii=False, indent=2,
              default=str)
    print(f"\nResults saved to {out_file}")

    return results


def run_code_experiment(n_samples=200, n_workers=4):
    """Code域完整实验"""
    print("\n" + "="*60)
    print("CODE DOMAIN EXPERIMENT")
    print(f"Samples per method: {n_samples}")
    print("="*60)

    output_dir = Path("/tmp/qd_experiments/code")
    output_dir.mkdir(parents=True, exist_ok=True)

    pool_file = output_dir / "code_pool.json"
    if pool_file.exists():
        print("Loading existing code pool...")
        pool = json.load(open(pool_file))
    else:
        print("Generating code problem pool...")
        tasks = [(i, (i % 5) + 1) for i in range(n_samples * 3)]

        pool = []
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(generate_code_problem, i, d): i
                      for i, d in tasks}
            for future in tqdm(as_completed(futures), total=len(futures),
                             desc="Code pool"):
                result = future.result()
                if result:
                    pool.append(result)

        json.dump(pool, open(pool_file, 'w'), ensure_ascii=False, indent=2)
        print(f"Pool: {len(pool)} problems generated")

    if not pool:
        print("ERROR: No code problems generated!")
        return None

    # QD-Synth
    print("\n--- QD-Synth (MAP-Elites) ---")
    qd_archive = MAPelitesArchive(compute_code_descriptor, compute_code_quality,
                                   grid_res=10, dim=3)
    for p in pool:
        qd_archive.add(p)
    qd_archive.record_history(0)

    qd_samples = qd_archive.get_samples()
    for round_idx in range(3):
        print(f"  Mutation round {round_idx+1}/3...")
        parents = random.sample(qd_samples, min(50, len(qd_samples)))
        new_samples = []
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(mutate_code, p): i
                      for i, p in enumerate(parents)}
            for future in tqdm(as_completed(futures), total=len(futures)):
                result = future.result()
                if result:
                    new_samples.append(result)

        for s in new_samples:
            qd_archive.add(s)
        qd_archive.record_history(round_idx + 1)
        qd_samples = qd_archive.get_samples()

    qd_results = qd_archive.get_samples()

    # Baselines
    k = len(qd_results)
    greedy_results = greedy_quality_select(pool, compute_code_quality, k)
    random_results = random_select(pool, k)
    cluster_results = cluster_select(pool, compute_code_descriptor, k, n_clusters=20)
    dedup_results = dedup_select(pool, compute_code_descriptor, k, compute_code_quality)

    # Metrics
    print("\n--- Computing Metrics ---")
    methods = {
        "Greedy-Quality": greedy_results,
        "Random-Subset": random_results,
        "Cluster-Sampling": cluster_results,
        "Deduplication": dedup_results,
        "QD-Synth": qd_results,
    }

    results = {}
    for name, samples in methods.items():
        if not samples:
            continue

        descs = [compute_code_descriptor(s) for s in samples]
        grid_coords = set(
            tuple(int(min(d * 10, 9)) for d in desc)
            for desc in descs
        )
        coverage = len(grid_coords) / (10 ** 3)

        qualities = [compute_code_quality(s) for s in samples]
        total_q = sum(qualities) + 1e-10
        probs = [q / total_q for q in qualities]
        entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)

        self_bleu = compute_self_bleu(
            samples,
            lambda s: s.get("prompt", s.get("description", ""))
        )

        avg_quality = np.mean(qualities)

        diff_dist = Counter(s.get("difficulty", 0) for s in samples)
        hard = sum(1 for s in samples if s.get("difficulty", 0) >= 4)
        hard_ratio = hard / len(samples)

        results[name] = {
            "n_samples": len(samples),
            "coverage": coverage,
            "entropy": entropy,
            "self_bleu": self_bleu,
            "avg_quality": avg_quality,
            "difficulty_dist": dict(diff_dist),
            "hard_ratio": hard_ratio,
        }

        print(f"  {name}: coverage={coverage:.2%}, entropy={entropy:.3f}, "
              f"self_bleu={self_bleu:.3f}, quality={avg_quality:.3f}, "
              f"hard={hard_ratio:.2%}")

    results["metadata"] = {
        "domain": "code",
        "pool_size": len(pool),
        "grid_res": 10,
        "dim": 3,
        "qd_history": qd_archive.history,
        "timestamp": datetime.now().isoformat()
    }

    out_file = output_dir / "code_results.json"
    json.dump(results, open(out_file, 'w'), ensure_ascii=False, indent=2,
              default=str)
    print(f"\nResults saved to {out_file}")

    return results


def run_dialogue_experiment(n_workers=4):
    """Dialogue域实验: 使用已有的522条对话"""
    print("\n" + "="*60)
    print("DIALOGUE DOMAIN EXPERIMENT")
    print("Using existing 522 dialogues")
    print("="*60)

    data_file = PROJECT_DIR / "data" / "raw" / "all_dialogues_final.json"
    if not data_file.exists():
        print("ERROR: No dialogue data found!")
        return None

    pool = json.load(open(data_file))
    # Filter valid dialogues
    pool = [d for d in pool if d.get("dialogue") and len(d.get("dialogue", [])) >= 2]
    print(f"Valid dialogues: {len(pool)}")

    output_dir = Path("/tmp/qd_experiments/dialogue")
    output_dir.mkdir(parents=True, exist_ok=True)

    # QD-Synth
    print("\n--- QD-Synth (MAP-Elites) ---")
    qd_archive = MAPelitesArchive(compute_dialogue_descriptor, compute_dialogue_quality,
                                   grid_res=10, dim=3)
    for d in pool:
        qd_archive.add(d)
    qd_archive.record_history(0)
    qd_results = qd_archive.get_samples()
    print(f"  QD archive: {len(qd_results)} samples, coverage={qd_archive.get_coverage():.2%}")

    # Baselines
    k = len(qd_results)
    print(f"\n--- Baselines (k={k}) ---")

    greedy_results = greedy_quality_select(pool, compute_dialogue_quality, k)
    random_results = random_select(pool, k)
    cluster_results = cluster_select(pool, compute_dialogue_descriptor, k, n_clusters=20)
    dedup_results = dedup_select(pool, compute_dialogue_descriptor, k, compute_dialogue_quality)

    # Metrics
    print("\n--- Computing Metrics ---")
    methods = {
        "Greedy-Quality": greedy_results,
        "Random-Subset": random_results,
        "Cluster-Sampling": cluster_results,
        "Deduplication": dedup_results,
        "QD-Synth": qd_results,
    }

    results = {}
    for name, samples in methods.items():
        if not samples:
            continue

        descs = [compute_dialogue_descriptor(s) for s in samples]
        grid_coords = set(
            tuple(int(min(d * 10, 9)) for d in desc)
            for desc in descs
        )
        coverage = len(grid_coords) / (10 ** 3)

        qualities = [compute_dialogue_quality(s) for s in samples]
        total_q = sum(qualities) + 1e-10
        probs = [q / total_q for q in qualities]
        entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)

        # For dialogue, Self-BLEU on agent text
        def get_dialogue_text(d):
            turns = d.get("dialogue", [])
            return " ".join(t.get("content", "") for t in turns if t.get("speaker") == "agent")

        self_bleu = compute_self_bleu(samples, get_dialogue_text)

        avg_quality = np.mean(qualities)

        # Strategy coverage
        strategies = set()
        for s in samples:
            for t in s.get("dialogue", []):
                if t.get("speaker") == "agent":
                    for strat in t.get("strategies_used", []):
                        strategies.add(strat)
        strat_coverage = len(strategies) / 18.0

        # Conflict distribution
        conflict_dist = Counter(
            s.get("metadata", {}).get("conflict_level", "?") for s in samples
        )

        results[name] = {
            "n_samples": len(samples),
            "coverage": coverage,
            "entropy": entropy,
            "self_bleu": self_bleu,
            "avg_quality": avg_quality,
            "strategy_coverage": strat_coverage,
            "strategies_found": sorted(strategies),
            "conflict_dist": dict(conflict_dist),
        }

        print(f"  {name}: coverage={coverage:.2%}, entropy={entropy:.3f}, "
              f"self_bleu={self_bleu:.3f}, quality={avg_quality:.3f}, "
              f"strat_cov={strat_coverage:.2%}")

    results["metadata"] = {
        "domain": "dialogue",
        "pool_size": len(pool),
        "grid_res": 10,
        "dim": 3,
        "qd_history": qd_archive.history,
        "qd_archive_stats": {
            "coverage": qd_archive.get_coverage(),
            "entropy": qd_archive.get_entropy(),
            "avg_quality": qd_archive.get_avg_quality(),
        },
        "timestamp": datetime.now().isoformat()
    }

    out_file = output_dir / "dialogue_results.json"
    json.dump(results, open(out_file, 'w'), ensure_ascii=False, indent=2,
              default=str)
    print(f"\nResults saved to {out_file}")

    return results


# ============================================================
# Ablation Experiments
# ============================================================

def run_ablation_experiments(domain="dialogue"):
    """消融实验: grid_res, descriptor_dim, mutation"""
    print("\n" + "="*60)
    print(f"ABLATION EXPERIMENTS ({domain})")
    print("="*60)

    output_dir = Path("/tmp/qd_experiments/ablation")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    if domain == "dialogue":
        data_file = PROJECT_DIR / "data" / "raw" / "all_dialogues_final.json"
        pool = json.load(open(data_file))
        pool = [d for d in pool if d.get("dialogue") and len(d.get("dialogue", [])) >= 2]
        desc_fn = compute_dialogue_descriptor
        quality_fn = compute_dialogue_quality
    else:
        data_file = Path(f"/tmp/qd_experiments/{domain}/{domain}_pool.json")
        if not data_file.exists():
            print(f"No pool for {domain}, run main experiment first")
            return None
        pool = json.load(open(data_file))
        desc_fn = compute_math_descriptor if domain == "math" else compute_code_descriptor
        quality_fn = compute_math_quality if domain == "math" else compute_code_quality

    ablation_results = {}

    # Ablation 1: Grid resolution
    print("\n--- Ablation 1: Grid Resolution ---")
    grid_ablation = {}
    for r in [5, 8, 10, 15, 20]:
        archive = MAPelitesArchive(desc_fn, quality_fn, grid_res=r, dim=3)
        for p in pool:
            archive.add(p)
        stats = {
            "coverage": archive.get_coverage(),
            "entropy": archive.get_entropy(),
            "avg_quality": archive.get_avg_quality(),
            "num_samples": len(archive.archive),
            "empty_cells": 1.0 - archive.get_coverage()
        }
        grid_ablation[f"r={r}"] = stats
        print(f"  r={r}: coverage={stats['coverage']:.2%}, "
              f"quality={stats['avg_quality']:.3f}, "
              f"empty={stats['empty_cells']:.2%}")
    ablation_results["grid_resolution"] = grid_ablation

    # Ablation 2: Descriptor dimension (use subset of dimensions)
    print("\n--- Ablation 2: Descriptor Dimension ---")
    dim_ablation = {}
    for d in [1, 2, 3]:
        if d == 3:
            # Full 3D
            archive = MAPelitesArchive(desc_fn, quality_fn, grid_res=10, dim=3)
            for p in pool:
                archive.add(p)
            coverage = archive.get_coverage()
            entropy = archive.get_entropy()
        elif d == 2:
            # 2D: use first 2 dimensions
            def desc_2d(s):
                full = desc_fn(s)
                return full[:2]
            archive = MAPelitesArchive(desc_2d, quality_fn, grid_res=10, dim=2)
            for p in pool:
                archive.add(p)
            coverage = archive.get_coverage()
            entropy = archive.get_entropy()
        else:
            # 1D: use first dimension only
            def desc_1d(s):
                full = desc_fn(s)
                return np.array([full[0]])
            archive = MAPelitesArchive(desc_1d, quality_fn, grid_res=10, dim=1)
            for p in pool:
                archive.add(p)
            coverage = archive.get_coverage()
            entropy = archive.get_entropy()

        dim_ablation[f"d={d}"] = {
            "coverage": coverage,
            "entropy": entropy,
            "avg_quality": archive.get_avg_quality(),
            "num_samples": len(archive.archive),
        }
        print(f"  d={d}: coverage={coverage:.2%}, entropy={entropy:.3f}, "
              f"quality={archive.get_avg_quality():.3f}")
    ablation_results["descriptor_dim"] = dim_ablation

    # Ablation 3: Mutation strategy (only for domains with enough data)
    print("\n--- Ablation 3: Selection Strategy ---")
    mutation_ablation = {}

    # No selection (just random pool)
    random_pool = random_select(pool, min(200, len(pool)))
    descs_r = [desc_fn(s) for s in random_pool]
    coords_r = set(tuple(int(min(d * 10, 9)) for d in desc) for desc in descs_r)
    mutation_ablation["random_no_selection"] = {
        "coverage": len(coords_r) / 1000,
        "n_samples": len(random_pool),
    }

    # Quality only (greedy)
    greedy_pool = greedy_quality_select(pool, quality_fn, 200)
    descs_g = [desc_fn(s) for s in greedy_pool]
    coords_g = set(tuple(int(min(d * 10, 9)) for d in desc) for desc in descs_g)
    mutation_ablation["greedy_quality"] = {
        "coverage": len(coords_g) / 1000,
        "n_samples": len(greedy_pool),
    }

    # QD (MAP-Elites)
    qd_archive = MAPelitesArchive(desc_fn, quality_fn, grid_res=10, dim=3)
    for p in pool:
        qd_archive.add(p)
    mutation_ablation["qd_synth"] = {
        "coverage": qd_archive.get_coverage(),
        "entropy": qd_archive.get_entropy(),
        "n_samples": len(qd_archive.archive),
        "avg_quality": qd_archive.get_avg_quality(),
    }

    for name, stats in mutation_ablation.items():
        print(f"  {name}: coverage={stats['coverage']:.2%}, "
              f"samples={stats['n_samples']}")
    ablation_results["mutation_strategy"] = mutation_ablation

    ablation_results["metadata"] = {
        "domain": domain,
        "pool_size": len(pool),
        "timestamp": datetime.now().isoformat()
    }

    out_file = output_dir / f"ablation_{domain}_results.json"
    json.dump(ablation_results, open(out_file, 'w'), ensure_ascii=False, indent=2,
              default=str)
    print(f"\nAblation results saved to {out_file}")

    return ablation_results


# ============================================================
# Collapse Dynamics Analysis
# ============================================================

def analyze_collapse_dynamics(domain="dialogue"):
    """分析塌缩动力学: 贪心 vs QD随迭代变化"""
    print("\n" + "="*60)
    print(f"COLLAPSE DYNAMICS ({domain})")
    print("="*60)

    output_dir = Path("/tmp/qd_experiments/collapse")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    if domain == "dialogue":
        data_file = PROJECT_DIR / "data" / "raw" / "all_dialogues_final.json"
        pool = json.load(open(data_file))
        pool = [d for d in pool if d.get("dialogue") and len(d.get("dialogue", [])) >= 2]
        desc_fn = compute_dialogue_descriptor
        quality_fn = compute_dialogue_quality
    else:
        data_file = Path(f"/tmp/qd_experiments/{domain}/{domain}_pool.json")
        if not data_file.exists():
            print(f"No pool for {domain}")
            return None
        pool = json.load(open(data_file))
        desc_fn = compute_math_descriptor if domain == "math" else compute_code_descriptor
        quality_fn = compute_math_quality if domain == "math" else compute_code_quality

    # Simulate iterative synthesis
    checkpoints = [10, 25, 50, 100, 150, 200, len(pool)]
    checkpoints = [c for c in checkpoints if c <= len(pool)]

    greedy_dynamics = []
    qd_dynamics = []

    for n in checkpoints:
        subset = pool[:n]

        # Greedy: quality-sorted
        greedy_subset = sorted(subset, key=lambda x: -quality_fn(x))[:min(n, len(subset))]
        g_descs = [desc_fn(s) for s in greedy_subset]
        g_coords = set(tuple(int(min(d * 10, 9)) for d in desc) for desc in g_descs)
        g_coverage = len(g_coords) / 1000
        g_qualities = [quality_fn(s) for s in greedy_subset]
        g_entropy = 0.0
        if g_qualities:
            total = sum(g_qualities) + 1e-10
            probs = [q / total for q in g_qualities]
            g_entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)

        greedy_dynamics.append({
            "n_samples": n,
            "coverage": g_coverage,
            "entropy": g_entropy,
            "avg_quality": np.mean(g_qualities) if g_qualities else 0,
        })

        # QD: MAP-Elites
        qd_archive = MAPelitesArchive(desc_fn, quality_fn, grid_res=10, dim=3)
        for p in subset:
            qd_archive.add(p)
        qd_dynamics.append({
            "n_samples": n,
            "coverage": qd_archive.get_coverage(),
            "entropy": qd_archive.get_entropy(),
            "avg_quality": qd_archive.get_avg_quality(),
            "archive_size": len(qd_archive.archive),
        })

    dynamics = {
        "greedy": greedy_dynamics,
        "qd_synth": qd_dynamics,
        "metadata": {
            "domain": domain,
            "pool_size": len(pool),
            "checkpoints": checkpoints,
            "timestamp": datetime.now().isoformat()
        }
    }

    out_file = output_dir / f"collapse_dynamics_{domain}.json"
    json.dump(dynamics, open(out_file, 'w'), ensure_ascii=False, indent=2,
              default=str)

    print("\n--- Collapse Dynamics ---")
    print(f"{'N':>5} | {'Greedy Cov':>12} | {'QD Cov':>8} | {'Greedy Ent':>12} | {'QD Ent':>8}")
    print("-" * 60)
    for g, q in zip(greedy_dynamics, qd_dynamics):
        print(f"{g['n_samples']:>5} | {g['coverage']:>11.2%} | {q['coverage']:>7.2%} | "
              f"{g['entropy']:>11.3f} | {q['entropy']:>7.3f}")

    print(f"\nResults saved to {out_file}")
    return dynamics


# ============================================================
# Summary Report Generator
# ============================================================

def generate_summary_report(all_results):
    """生成实验总结报告"""
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY REPORT")
    print("="*60)

    report = {
        "title": "QD-Synth Experiment Results",
        "timestamp": datetime.now().isoformat(),
        "domains": {}
    }

    for domain in ["math", "code", "dialogue"]:
        rfile = Path(f"/tmp/qd_experiments/{domain}/{domain}_results.json")
        if rfile.exists():
            data = json.load(open(rfile))
            report["domains"][domain] = data

    # Generate main table
    print("\n" + "="*80)
    print(f"{'Method':<20} | {'Math Coverage':>14} | {'Code Coverage':>14} | {'Dialogue Coverage':>18} | {'Self-BLEU':>10}")
    print("-" * 80)

    for method in ["Greedy-Quality", "Random-Subset", "Cluster-Sampling",
                   "Deduplication", "QD-Synth"]:
        row = [method]
        for domain in ["math", "code", "dialogue"]:
            if domain in report["domains"]:
                m = report["domains"][domain].get(method, {})
                cov = m.get("coverage", 0)
                row.append(f"{cov:>12.2%}")
            else:
                row.append(f"{'N/A':>12}")

        # Average Self-BLEU
        bleus = []
        for domain in ["math", "code", "dialogue"]:
            if domain in report["domains"]:
                m = report["domains"][domain].get(method, {})
                if "self_bleu" in m:
                    bleus.append(m["self_bleu"])
        avg_bleu = np.mean(bleus) if bleus else 0
        row.append(f"{avg_bleu:>10.3f}")

        print(" | ".join(row))

    # Save report
    report_file = Path("/tmp/qd_experiments/summary_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(report_file, 'w'), ensure_ascii=False, indent=2,
              default=str)
    print(f"\nFull report saved to {report_file}")

    return report


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="QD-Synth Real Experiments")
    parser.add_argument("--domain", type=str, default="all",
                       choices=["math", "code", "dialogue", "all", "ablation", "collapse"])
    parser.add_argument("--samples", type=int, default=200,
                       help="Samples per method per domain")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    random.seed(42)
    np.random.seed(42)

    all_results = {}

    if args.domain in ["math", "all"]:
        r = run_math_experiment(args.samples, args.workers)
        if r:
            all_results["math"] = r

    if args.domain in ["code", "all"]:
        r = run_code_experiment(args.samples, args.workers)
        if r:
            all_results["code"] = r

    if args.domain in ["dialogue", "all"]:
        r = run_dialogue_experiment(args.workers)
        if r:
            all_results["dialogue"] = r

    if args.domain in ["ablation", "all"]:
        for domain in ["dialogue", "math", "code"]:
            r = run_ablation_experiments(domain)
            if r:
                all_results[f"ablation_{domain}"] = r

    if args.domain in ["collapse", "all"]:
        for domain in ["dialogue", "math", "code"]:
            r = analyze_collapse_dynamics(domain)
            if r:
                all_results[f"collapse_{domain}"] = r

    if all_results:
        generate_summary_report(all_results)

    print("\n" + "="*60)
    print("ALL EXPERIMENTS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
