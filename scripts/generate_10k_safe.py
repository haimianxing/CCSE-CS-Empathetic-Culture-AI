"""
CCSE 10K 并发生成脚本
- ThreadPoolExecutor 并发加速（参考 infer/utils/clean_data_ol.py 模式）
- chunked 分块 + checkpoint 断点续传
- 每chunk即时存盘，crash-safe
- 质量与现有522条一致：三阶段管线 + 多维过滤

用法:
    python scripts/generate_10k_safe.py --target 10000 --workers 4 --chunk-size 10
    # 中断后重跑同样命令，自动从checkpoint续传
"""

import json
import os
import sys
import re
import time
import random
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

# ============================================================
# 项目路径 & 导入
# ============================================================
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))
from configs.strategy_ontology import (
    STRATEGY_ONTOLOGY, DOMAINS, CULTURAL_FACTORS,
    ALL_STRATEGY_IDS, SUPPLEMENTARY_SCENARIOS
)

# ============================================================
# API 配置
# ============================================================
API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
    "top_p": 0.9,
}


def call_qwen_api(messages, temperature=0.8, max_tokens=4096, max_retries=3):
    """线程安全的API调用"""
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
    """从LLM回复中提取JSON"""
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
    # 最后尝试找 { ... }
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


# ============================================================
# Fast模式：单次API调用直接生成完整对话
# ============================================================

def generate_one_dialogue_fast(task_config):
    """一次API调用直接生成完整对话（跳过Stage A骨架），速度约2x"""
    domain = task_config["domain"]
    scenario = task_config.get("scenario") or random.choice(DOMAINS[domain]["scenarios"])
    conflict = task_config.get("conflict_level") or random.choice(["低", "中", "高"])
    cultural = task_config.get("cultural_profile") or {
        "关系取向": random.choice(CULTURAL_FACTORS["关系取向"]["values"]),
        "面子维护": random.choice(CULTURAL_FACTORS["面子维护"]["values"]),
        "委婉度": random.choice(CULTURAL_FACTORS["委婉度"]["values"]),
    }
    extra_prompt = task_config.get("extra_prompt", "")
    task_idx = task_config.get("task_idx", 0)
    policy = random.choice(DOMAINS[domain]["policies"])

    n_strategies = random.randint(3, 5)
    must_have = ["S8"] if conflict == "高" else []
    pool = [s for s in ALL_STRATEGY_IDS if s not in must_have]
    selected = must_have + random.sample(pool, min(n_strategies, len(pool)))

    strategy_parts = []
    for sid in selected:
        info = get_strategy_info(sid)
        if info:
            strategy_parts.append(f"- {sid}({info['name']}): {info['description']}")
    strategy_text = "\n".join(strategy_parts)

    prompt = f"""你是资深中文{domain}客服对话编写专家。根据以下条件编写4-8轮高质量客服对话。

条件：领域={domain} 问题={scenario} 冲突={conflict} 政策={policy}
客户：面子={cultural['面子维护']} 委婉={cultural['委婉度']}
策略：{strategy_text}

要求：agent每轮标strategies_used；不越权承诺；信息虚构(张三/138xxxx0001)；高冲突有升温降温。{extra_prompt}
只输出JSON：{{"dialogue":[{{"turn":1,"speaker":"user","content":"...","emotion":"...","intent":"..."}},{{"turn":1,"speaker":"agent","content":"...","strategies_used":["S1"],"strategy_descriptions":["..."],"emotion_response":"..."}}],"quality_self_check":{{"has_empathy":true,"policy_compliant":true}},"dialogue_summary":"...","resolution":"..."}}"""

    resp = call_qwen_api([{"role": "user", "content": prompt}],
                         temperature=0.75, max_tokens=4096)
    dialogue_data = extract_json(resp)
    if not dialogue_data or "dialogue" not in dialogue_data:
        return None, f"[{task_idx}] Fast: JSON解析失败"

    dialogue_data["metadata"] = {
        "session_id": f"10k_{domain}_{int(time.time())}_{random.randint(1000,9999)}",
        "domain": domain, "scenario": scenario, "conflict_level": conflict,
        "cultural_profile": cultural, "strategies_needed": selected,
        "generation_time": datetime.now().isoformat(),
        "model": API_CONFIG["model_name"], "mode": "fast"
    }

    # Stage C 质量过滤
    dialogue = dialogue_data["dialogue"]
    if len(dialogue) < 4:
        return None, f"[{task_idx}] Fast: 轮次不足"
    agent_turns = [d for d in dialogue if d.get("speaker") == "agent"]
    if len(agent_turns) < 2:
        return None, f"[{task_idx}] Fast: agent不足"
    agent_text = " ".join(d["content"] for d in agent_turns)
    for kw in ["保证一定", "绝对没问题", "100%", "肯定会", "我承诺"]:
        if kw in agent_text:
            return None, f"[{task_idx}] Fast: 越权"
    for kw in ["你应该感到", "你不觉得", "后果会很严重"]:
        if kw in agent_text:
            return None, f"[{task_idx}] Fast: 操纵"
    strategies_used = set()
    for t in agent_turns:
        if not t.get("strategies_used"):
            return None, f"[{task_idx}] Fast: 缺策略标注"
        for s in t["strategies_used"]:
            strategies_used.add(s)
    if len(strategies_used) < 2:
        return None, f"[{task_idx}] Fast: 策略不足"
    total_chars = sum(len(d["content"]) for d in dialogue)
    if total_chars < 50 or total_chars > 3000:
        return None, f"[{task_idx}] Fast: 长度异常"
    if conflict == "高" and "S8" not in strategies_used:
        return None, f"[{task_idx}] Fast: 高冲突缺S8"
    return dialogue_data, "success"


# ============================================================
# 三阶段管线（单条对话生成，线程安全）
# ============================================================

def get_strategy_info(strategy_id):
    """获取策略描述（含中文名）"""
    for cat_data in STRATEGY_ONTOLOGY.values():
        for s_name, s_data in cat_data["sub_strategies"].items():
            if s_data["id"] == strategy_id:
                # s_name 如 "S1_复述确认"，取中文部分
                cn_name = s_name.split("_", 1)[1] if "_" in s_name else s_name
                return {
                    "name": cn_name,
                    "name_en": s_data["name_en"],
                    "description": s_data["description"],
                    "examples": s_data["examples"],
                }
    return None


def generate_one_dialogue(task_config):
    """
    生成一条对话（线程安全）
    task_config: dict with domain, scenario, conflict_level, cultural_profile, extra_prompt, task_idx
    Returns: (dialogue_data, status_str)
    """
    domain = task_config["domain"]
    scenario = task_config.get("scenario")
    conflict = task_config.get("conflict_level")
    cultural = task_config.get("cultural_profile")
    extra_prompt = task_config.get("extra_prompt", "")
    task_idx = task_config.get("task_idx", 0)

    if scenario is None:
        scenario = random.choice(DOMAINS[domain]["scenarios"])
    if conflict is None:
        conflict = random.choice(["低", "中", "高"])
    if cultural is None:
        cultural = {
            "关系取向": random.choice(CULTURAL_FACTORS["关系取向"]["values"]),
            "面子维护": random.choice(CULTURAL_FACTORS["面子维护"]["values"]),
            "委婉度": random.choice(CULTURAL_FACTORS["委婉度"]["values"]),
        }

    policy = random.choice(DOMAINS[domain]["policies"])

    # ---- Stage A: 种子骨架 ----
    skeleton_prompt = f"""你是一个专业的客服对话场景设计专家。请为一个中文{domain}客服场景设计对话骨架。

场景信息：
- 领域：{domain}
- 具体问题：{scenario}
- 相关政策：{policy}
- 客户冲突强度：{conflict}

以JSON格式输出：
{{"session_id":"auto","domain":"{domain}","scenario":"{scenario}","conflict_level":"{conflict}","policy_involved":"{policy}","user_profile":{{"emotion":"客户初始情绪","implicit_need":"潜在需求","face_sensitivity":"高/中/低","communication_style":"直接/委婉/情绪化"}},"dialogue_skeleton":[{{"turn":1,"speaker":"user","intent":"意图","strategy_needed":["S1"],"key_points":["关键信息(必须使用虚构信息)"]}},{{"turn":1,"speaker":"agent","strategy_required":["S1","S2"],"sub_goals":["复述问题","识别情绪"],"policy_constraint":"政策约束"}}],"resolution_type":"解决/升级/补偿/部分满足"}}

注意：strategy_required从S1-S18选；高冲突含S8；所有个人信息必须虚构(张三/138xxxx0001等)；只输出JSON。"""

    skeleton_resp = call_qwen_api([{"role": "user", "content": skeleton_prompt}],
                                  temperature=0.85)
    scenario_data = extract_json(skeleton_resp)
    if not scenario_data:
        return None, f"[{task_idx}] StageA: JSON解析失败"

    scenario_data["session_id"] = f"10k_{domain}_{int(time.time())}_{random.randint(1000,9999)}"
    scenario_data["domain"] = domain
    scenario_data["scenario"] = scenario
    scenario_data["conflict_level"] = conflict

    # ---- Stage B: 对话展开 ----
    strategies_needed = set()
    for turn in scenario_data.get("dialogue_skeleton", []):
        if turn.get("speaker") == "agent":
            for sid in turn.get("strategy_required", []):
                strategies_needed.add(sid)

    strategy_ref_parts = []
    for sid in strategies_needed:
        info = get_strategy_info(sid)
        if info:
            strategy_ref_parts.append(
                f"- {sid}: {info['name']} — {info['description']}\n  示例: {random.choice(info['examples'])}"
            )
    strategy_ref = "\n".join(strategy_ref_parts)
    policy_text = "\n".join([f"- {p}" for p in DOMAINS.get(domain, {}).get("policies", [])])

    expand_prompt = f"""你是一个资深的中文{domain}客服对话编写专家。根据以下信息编写一段高质量客服对话。

## 场景：{domain} / {scenario} / 冲突{conflict}
## 客户画像：{json.dumps(scenario_data.get('user_profile',{}), ensure_ascii=False)}
## 文化因子：{json.dumps(cultural, ensure_ascii=False)}
## 策略（必须覆盖）：{strategy_ref}
## 政策：{policy_text}
## 骨架：{json.dumps(scenario_data.get('dialogue_skeleton',[]), ensure_ascii=False)}

要求：4-8轮；每轮agent必须标注strategies_used；自然流畅；不越权承诺；不操纵情感；个人信息必须虚构(张三/138xxxx0001等)。{extra_prompt}

输出JSON：{{"dialogue":[{{"turn":1,"speaker":"user","content":"...","emotion":"...","intent":"..."}},{{"turn":1,"speaker":"agent","content":"...","strategies_used":["S1"],"strategy_descriptions":["..."],"emotion_response":"..."}}],"quality_self_check":{{"has_empathy":true,"policy_compliant":true,"no_overcommitment":true,"no_emotion_manipulation":true}},"dialogue_summary":"...","resolution":"..."}}
只输出JSON。"""

    expand_resp = call_qwen_api([{"role": "user", "content": expand_prompt}],
                                temperature=0.75, max_tokens=4096)
    dialogue_data = extract_json(expand_resp)
    if not dialogue_data or "dialogue" not in dialogue_data:
        return None, f"[{task_idx}] StageB: JSON解析失败"

    dialogue_data["metadata"] = {
        "session_id": scenario_data["session_id"],
        "domain": domain,
        "scenario": scenario,
        "conflict_level": conflict,
        "cultural_profile": cultural,
        "strategies_needed": list(strategies_needed),
        "generation_time": datetime.now().isoformat(),
        "model": API_CONFIG["model_name"]
    }

    # ---- Stage C: 质量过滤 ----
    dialogue = dialogue_data["dialogue"]
    if len(dialogue) < 4:
        return None, f"[{task_idx}] StageC: 轮次不足"

    agent_turns = [d for d in dialogue if d.get("speaker") == "agent"]
    if len(agent_turns) < 2:
        return None, f"[{task_idx}] StageC: agent回复不足"

    agent_text = " ".join(d["content"] for d in agent_turns)

    for kw in ["保证一定", "绝对没问题", "100%", "肯定会", "我承诺",
               "一定会给你", "包你满意", "不可能出错"]:
        if kw in agent_text:
            return None, f"[{task_idx}] StageC: 越权承诺'{kw}'"

    for kw in ["你应该感到", "你不觉得", "后果会很严重"]:
        if kw in agent_text:
            return None, f"[{task_idx}] StageC: 情感操纵'{kw}'"

    strategies_used = set()
    for t in agent_turns:
        if not t.get("strategies_used"):
            return None, f"[{task_idx}] StageC: 缺策略标注"
        for s in t["strategies_used"]:
            strategies_used.add(s)

    if len(strategies_used) < 2:
        return None, f"[{task_idx}] StageC: 策略覆盖不足"

    total_chars = sum(len(d["content"]) for d in dialogue)
    if total_chars < 50 or total_chars > 3000:
        return None, f"[{task_idx}] StageC: 长度异常({total_chars})"

    if conflict == "高" and "S8" not in strategies_used:
        return None, f"[{task_idx}] StageC: 高冲突缺S8"

    return dialogue_data, "success"


# ============================================================
# 任务分配器：均衡领域 + 补充策略
# ============================================================

def create_task_pool(target_count):
    """生成 target_count 个任务配置"""
    domains = list(DOMAINS.keys())
    sup_keys = list(SUPPLEMENTARY_SCENARIOS.keys())

    regular_ratio = 0.75
    regular_count = int(target_count * regular_ratio)
    sup_count = target_count - regular_count

    tasks = []

    # 常规任务：均衡领域
    for i in range(regular_count):
        tasks.append({
            "domain": domains[i % len(domains)],
            "task_idx": i,
        })

    # 补充任务：S13/S16/S17/S18
    per_sup = sup_count // len(sup_keys)
    for sk in sup_keys:
        sup_cfg = SUPPLEMENTARY_SCENARIOS[sk]
        for j in range(per_sup):
            tasks.append({
                "domain": random.choice(sup_cfg["domains"]),
                "scenario": random.choice(sup_cfg["scenarios"]),
                "extra_prompt": sup_cfg["extra_prompt"],
                "task_idx": len(tasks),
            })

    random.shuffle(tasks)
    return tasks


# ============================================================
# 主流程：chunked + ThreadPoolExecutor + checkpoint
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="CCSE 10K 并发生成")
    parser.add_argument("--target", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=4, help="并发线程数")
    parser.add_argument("--chunk-size", type=int, default=10)
    parser.add_argument("--output-dir", type=str,
                        default=str(PROJECT_DIR / "data" / "raw"))
    parser.add_argument("--fast", action="store_true",
                        help="单次API调用模式（跳过骨架生成），速度约2x")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 已有数据
    existing_file = PROJECT_DIR / "data" / "raw" / "all_dialogues_final.json"
    existing_count = 0
    existing_data = []
    if existing_file.exists():
        existing_data = json.load(open(existing_file))
        existing_count = len(existing_data)
        print(f"已有数据: {existing_count} 条")

    remaining = max(0, args.target - existing_count)
    if remaining <= 0:
        print(f"已达到目标 {args.target} 条，无需生成")
        return

    print(f"\n{'='*60}")
    print(f"CCSE 10K 并发生成")
    print(f"目标: {args.target} | 已有: {existing_count} | 需生成: {remaining}")
    print(f"并发: {args.workers} workers | chunk: {args.chunk_size} | fast: {args.fast}")
    print(f"{'='*60}\n")

    gen_fn = generate_one_dialogue_fast if args.fast else generate_one_dialogue

    # 创建任务池
    tasks = create_task_pool(remaining)
    chunks = [tasks[i:i + args.chunk_size]
              for i in range(0, len(tasks), args.chunk_size)]

    # Checkpoint
    ckpt_file = os.path.join(args.output_dir, "10k_checkpoint.txt")
    start_chunk = 0
    if os.path.exists(ckpt_file):
        start_chunk = int(open(ckpt_file).read().strip())
        print(f"从 checkpoint 恢复: chunk {start_chunk}/{len(chunks)}")

    total_success = 0
    total_fail = 0
    all_new = []

    for chunk_idx in range(start_chunk, len(chunks)):
        chunk = chunks[chunk_idx]
        results = [None] * len(chunk)

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(gen_fn, task): i
                for i, task in enumerate(chunk)
            }
            for future in tqdm(as_completed(futures),
                               total=len(chunk),
                               desc=f"Chunk {chunk_idx+1}/{len(chunks)}",
                               colour="CYAN"):
                i = futures[future]
                try:
                    dlg_data, status = future.result()
                    if dlg_data:
                        results[i] = dlg_data
                    else:
                        results[i] = None
                except Exception as e:
                    results[i] = None

        # 统计本chunk
        chunk_success = sum(1 for r in results if r is not None)
        chunk_fail = len(results) - chunk_success
        total_success += chunk_success
        total_fail += chunk_fail
        all_new.extend([r for r in results if r is not None])

        # 即时存盘：每chunk保存累计数据
        combined = existing_data + all_new
        out_path = os.path.join(
            args.output_dir,
            f"10k_checkpoint_{len(combined)}.json"
        )
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)

        # 更新checkpoint
        with open(ckpt_file, 'w') as f:
            f.write(str(chunk_idx + 1))

        # 策略覆盖统计
        strategies_in_chunk = set()
        for r in results:
            if r:
                for t in r.get("dialogue", []):
                    if t.get("speaker") == "agent":
                        for s in t.get("strategies_used", []):
                            strategies_in_chunk.add(s)

        print(f"  Chunk {chunk_idx+1}: +{chunk_success} 条 "
              f"(累计 {len(combined)} | 失败 {chunk_fail}) "
              f"| 策略: {sorted(strategies_in_chunk)}")

        # 达标检查
        if len(combined) >= args.target:
            print(f"\n已达到目标 {args.target} 条!")
            break

    # 最终保存
    combined = existing_data + all_new
    final_path = os.path.join(args.output_dir, "all_dialogues_final.json")
    with open(final_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    # 统计
    domains_count = {}
    conflicts_count = {}
    strategies_count = {}
    for dlg in combined:
        meta = dlg.get("metadata", {})
        d = meta.get("domain", "unknown")
        c = meta.get("conflict_level", "unknown")
        domains_count[d] = domains_count.get(d, 0) + 1
        conflicts_count[c] = conflicts_count.get(c, 0) + 1
        for t in dlg.get("dialogue", []):
            if t.get("speaker") == "agent":
                for s in t.get("strategies_used", []):
                    strategies_count[s] = strategies_count.get(s, 0) + 1

    print(f"\n{'='*60}")
    print(f"生成完成!")
    print(f"  总对话数: {len(combined)}")
    print(f"  领域: {domains_count}")
    print(f"  冲突: {conflicts_count}")
    print(f"  策略覆盖 ({len(strategies_count)}种):")
    for s, c in sorted(strategies_count.items(), key=lambda x: -x[1]):
        print(f"    {s}: {c}")
    print(f"  成功率: {total_success}/{total_success+total_fail} "
          f"= {total_success/max(total_success+total_fail,1)*100:.1f}%")
    print(f"  输出: {final_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
