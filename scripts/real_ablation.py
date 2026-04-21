#!/usr/bin/env python3.9
"""
Real Ablation Experiment for CCSE-CS
Generates dialogues with ablated prompts, evaluates with real LLM Judge.
Saves per-sample checkpoints for reproducibility.
"""
import json
import os
import re
import time
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR = Path("/mnt/data2/zcz/neurIps-emnlp/data/experiments/ablation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
}

# ============================================================
# Generation Prompts (ablation variants)
# ============================================================

DOMAIN = "电商"
SCENARIOS = [
    "客户购买的手机到货后发现屏幕有划痕，要求退货退款",
    "客户投诉物流配送延迟，快递已经超过预计送达时间3天",
    "客户发现商品与描述不符，颜色和尺码都发错了",
    "客户对会员积分兑换规则有疑问，认为积分被无故扣除",
    "客户反映App闪退导致订单无法完成，情绪激动",
    "客户要求修改已经提交的订单收货地址",
    "客户投诉客服态度不好，要求投诉升级处理",
    "客户询问退换货政策，商品已拆封但未使用",
    "客户对促销活动规则不理解，认为优惠金额计算错误",
    "客户要求开具增值税发票但系统显示无法开具",
    "客户的优惠券在有效期内无法使用，显示已过期",
    "客户反映商品质量有问题，要求赔偿并退货",
    "客户要求加急配送，但系统不支持修改配送方式",
    "客户对售后服务不满意，要求与主管沟通",
    "客户询问如何使用积分抵扣，但积分不够抵扣",
    "客户投诉包装破损导致商品损坏，要求重新发货",
    "客户要求价格保护，发现购买后商品降价了",
    "客户的预售商品迟迟未发货，要求取消订单",
    "客户对赠品发放有疑问，活动页面显示有赠品但未收到",
    "客户要求开发票但发票信息填错了需要重开",
    "客户的退款申请被拒绝，认为理由不合理",
    "客户反映收到的商品缺少配件，要求补发",
    "客户投诉同一商品在不同页面价格不一致",
    "客户询问会员等级权益，对升级规则不理解",
    "客户要求修改发票抬头但订单已完成",
    "客户的拼团订单失败但钱已扣除",
    "客户投诉快递员态度恶劣，要求投诉并赔偿",
    "客户要求延长退货期限，因为出差在外无法寄回",
    "客户对限时抢购活动的秒杀规则有异议",
    "客户反映购买的商品已降价，要求退差价",
    "客户的以旧换新订单审核未通过但旧机已寄出",
    "客户要求查看购物清单但页面显示异常",
    "客户投诉商品描述使用AI生成图片与实物不符",
    "客户的预约安装服务未按时上门",
    "客户要求取消自动续费会员但找不到取消入口",
    "客户反映支付成功但订单显示未支付",
    "客户对海外购商品的关税计算有疑问",
    "客户投诉客服一直让等但没有解决问题",
    "客户要求合并多个订单的运费但系统不支持",
    "客户的预售定金无法退回",
    "客户询问如何申请成为平台供应商",
    "客户投诉虚假宣传，商品功能与广告不符",
    "客户的评价被系统删除要求恢复",
    "客户要求更改配送时间但配送员已出发",
    "客户的优惠券叠加使用规则不清晰",
    "客户投诉商品有异味要求退货但已拆封",
    "客户反映账户余额显示异常",
    "客户的售后维修单长时间未处理",
    "客户要求赔偿因商品质量问题造成的损失",
    "客户对平台的隐私政策有疑问",
]

FULL_PROMPT_TEMPLATE = """你是一名专业的中国电商客服。请针对以下场景生成一段客服对话（包含客户和客服的多轮对话，至少5轮）。

场景：{scenario}

要求：
1. 使用策略标注，格式为（策略名）
2. 策略包括：
   - C1: Active Listening: S1(Restatement), S2(Emotion Mapping), S3(Need Refinement)
   - C2: Face-Saving: S4(Euphemistic Apology), S5(Value Affirmation), S6(Blame Avoidance)
   - C3: Emotional Soothing: S7(Empathy Expression), S8(De-escalation), S9(Emotional Validation)
   - C4: Solution Advancement: S10(Clear Solution), S11(Option Presentation), S12(Expectation Management)
   - C5: Relationship Repair: S13(Compensation Care), S14(Follow-up Closure), S15(Long-term Maintenance)
   - C6: Cultural Adaptation: S16(Respect Elevation), S17(Festival Care), S18(Context Adaptation)
3. 文化因素：关系取向=正式, 面子敏感度=高, 委婉度=高, 冲突强度=中
4. 避免过度承诺和指责性语言
5. 每轮对话至少使用一个策略

请生成对话："""

NO_CULTURE_PROMPT_TEMPLATE = """你是一名专业的中国电商客服。请针对以下场景生成一段客服对话（包含客户和客服的多轮对话，至少5轮）。

场景：{scenario}

要求：
1. 使用策略标注，格式为（策略名）
2. 策略包括：
   - C1: Active Listening: S1(Restatement), S2(Emotion Mapping), S3(Need Refinement)
   - C2: Face-Saving: S4(Euphemistic Apology), S5(Value Affirmation), S6(Blame Avoidance)
   - C3: Emotional Soothing: S7(Empathy Expression), S8(De-escalation), S9(Emotional Validation)
   - C4: Solution Advancement: S10(Clear Solution), S11(Option Presentation), S12(Expectation Management)
   - C5: Relationship Repair: S13(Compensation Care), S14(Follow-up Closure), S15(Long-term Maintenance)
   - C6: Cultural Adaptation: S16(Respect Elevation), S17(Festival Care), S18(Context Adaptation)
3. 不要使用委婉表达，直接回答客户问题
4. 可以使用直接的语言指出客户的问题
5. 每轮对话至少使用一个策略

请生成对话："""

COARSE_STRATEGY_PROMPT_TEMPLATE = """你是一名专业的中国电商客服。请针对以下场景生成一段客服对话（包含客户和客服的多轮对话，至少5轮）。

场景：{scenario}

要求：
1. 使用大类别策略标注，格式为（类别名）
2. 只使用以下6个大类别：
   - C1: Active Listening（倾听）
   - C2: Face-Saving（面子维护）
   - C3: Emotional Soothing（情绪安抚）
   - C4: Solution Advancement（方案推进）
   - C5: Relationship Repair（关系修复）
   - C6: Cultural Adaptation（文化适应）
3. 文化因素：关系取向=正式, 面子敏感度=高, 委婉度=高, 冲突强度=中
4. 避免过度承诺和指责性语言
5. 每轮对话至少标注一个类别

请生成对话："""

NO_FILTER_PROMPT_TEMPLATE = FULL_PROMPT_TEMPLATE  # Same generation, but no post-filtering

# ============================================================
# Judge Prompts (same as baseline_eval.py)
# ============================================================

JUDGE_A_PROMPT = """你是专业的客服对话评测专家。请评估以下客服对话的两个维度，给出1-5分评分：

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

**客服对话**: {dialogue}

请严格以JSON格式输出：
{{"Emp-App": {{"score": 0}}, "Nat": {{"score": 0}}}}
只输出JSON。"""

JUDGE_B_PROMPT = """你是专业的客服对话评测专家。请评估以下客服对话的两个维度，给出1-5分评分：

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

**客服对话**: {dialogue}

请严格以JSON格式输出：
{{"Pol-Comp": {{"score": 0}}, "Cul-Fit": {{"score": 0}}}}
只输出JSON。"""

# ============================================================
# API Call
# ============================================================

def call_api(messages, temperature=0.3, max_retries=3):
    import requests
    headers = {"Authorization": f"Bearer {API_CONFIG['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": 2048
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_CONFIG["url"], headers=headers, json=payload, timeout=90)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if "<think" in content:
                content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print(f"  API error: {e}")
    return None

def parse_scores(text, dims):
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
# Quality Filters
# ============================================================

def apply_quality_filters(dialogue_text):
    """Apply 5-fold quality filter. Returns (passed, reason)"""
    # PolicyGuard: no over-commitment
    for phrase in ["保证一定", "绝对没问题", "100%", "肯定能", "一定帮你"]:
        if phrase in dialogue_text:
            return False, f"PolicyGuard: over-commitment '{phrase}'"

    # EmpathySanity: no emotional manipulation
    for phrase in ["你应该感到", "后果很严重", "不可能不满意"]:
        if phrase in dialogue_text:
            return False, f"EmpathySanity: manipulation '{phrase}'"

    # FaceCheck: no blaming language
    for phrase in ["您没有按照", "你的错", "你理解错了", "是你自己"]:
        if phrase in dialogue_text:
            return False, f"FaceCheck: blaming '{phrase}'"

    # CoverageCheck: at least 2 strategies used
    strategy_count = dialogue_text.count("(S") + dialogue_text.count("（")
    if strategy_count < 2:
        return False, f"CoverageCheck: only {strategy_count} strategies"

    return True, "PASS"

# ============================================================
# Experiment: Generate + Evaluate
# ============================================================

def generate_dialogue(scenario, prompt_template, label, idx):
    """Generate a single dialogue"""
    prompt = prompt_template.format(scenario=scenario)
    result = call_api([{"role": "user", "content": prompt}], temperature=0.7)

    if result is None:
        print(f"  [{label}] {idx+1}/{len(scenarios)} GEN FAILED")
        return None

    # Extract dialogue content
    dialogue = result.strip()
    return dialogue

def evaluate_dialogue(dialogue_text):
    """Evaluate a dialogue with dual judge"""
    # Truncate if too long for judge
    if len(dialogue_text) > 2000:
        dialogue_text = dialogue_text[:2000]

    # Judge A
    prompt_a = JUDGE_A_PROMPT.format(dialogue=dialogue_text)
    result_a = call_api([{"role": "user", "content": prompt_a}])
    scores_a = parse_scores(result_a, ["Emp-App", "Nat"])

    # Judge B
    prompt_b = JUDGE_B_PROMPT.format(dialogue=dialogue_text)
    result_b = call_api([{"role": "user", "content": prompt_b}])
    scores_b = parse_scores(result_b, ["Pol-Comp", "Cul-Fit"])

    if scores_a and scores_b:
        combined = {**scores_a, **scores_b}
        combined["Overall"] = sum(combined.values()) / 4.0
        return combined
    return None

def run_ablation_config(config_name, prompt_template, scenarios, apply_filter=True):
    """Run one ablation configuration"""
    print(f"\n--- Running: {config_name} ---")
    checkpoint_file = OUTPUT_DIR / f"checkpoint_{config_name}.json"
    results_file = OUTPUT_DIR / f"results_{config_name}.json"

    # Load checkpoint
    completed = []
    if checkpoint_file.exists():
        with open(checkpoint_file) as f:
            completed = json.load(f).get("results", [])
        print(f"  Resumed from {len(completed)}/50")

    for i in range(len(completed), len(scenarios)):
        scenario = scenarios[i]

        # Generate
        dialogue = generate_dialogue(scenario, prompt_template, config_name, i)
        if dialogue is None:
            completed.append(None)
            continue

        # Apply filter if needed
        if apply_filter:
            passed, reason = apply_quality_filters(dialogue)
            if not passed:
                completed.append({"filtered": True, "reason": reason, "dialogue": dialogue[:200]})
                print(f"  [{config_name}] {i+1}/{len(scenarios)} FILTERED: {reason}")
                # Save checkpoint
                with open(checkpoint_file, 'w') as f:
                    json.dump({"results": completed}, f, ensure_ascii=False)
                continue

        # Evaluate
        score = evaluate_dialogue(dialogue)

        if score:
            result = {"dialogue": dialogue[:500], "scenario": scenario, "scores": score}
            completed.append(result)
            avg = score["Overall"]
            print(f"  [{config_name}] {i+1}/{len(scenarios)} EA={score['Emp-App']} Nat={score['Nat']} PC={score['Pol-Comp']} CF={score['Cul-Fit']} Avg={avg:.2f}")
        else:
            completed.append({"dialogue": dialogue[:200], "scenario": scenario, "scores": None})
            print(f"  [{config_name}] {i+1}/{len(scenarios)} EVAL FAILED")

        # Checkpoint every 5
        if (i + 1) % 5 == 0 or i == len(scenarios) - 1:
            with open(checkpoint_file, 'w') as f:
                json.dump({"results": completed}, f, ensure_ascii=False)

    # Compute statistics
    valid_scores = [r["scores"] for r in completed if r and isinstance(r, dict) and "scores" in r and r.get("scores")]
    stats = compute_stats(valid_scores, config_name)

    # Save results
    with open(results_file, 'w') as f:
        json.dump({"config": config_name, "stats": stats, "n_valid": len(valid_scores)}, f, ensure_ascii=False, indent=2)

    return stats

def compute_stats(scores_list, label):
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
        }
    return stats

# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Real Ablation Experiment for CCSE-CS")
    print("=" * 60)

    scenarios = SCENARIOS[:20]  # 20 samples per config (statistically meaningful for 5-point Likert)

    configs = [
        ("full_model", FULL_PROMPT_TEMPLATE, True),
        ("no_culture", NO_CULTURE_PROMPT_TEMPLATE, True),
        ("coarse_strategy", COARSE_STRATEGY_PROMPT_TEMPLATE, True),
        ("no_filter", NO_FILTER_PROMPT_TEMPLATE, False),
    ]

    all_stats = {}
    for config_name, prompt_template, use_filter in configs:
        stats = run_ablation_config(config_name, prompt_template, scenarios, apply_filter=use_filter)
        if stats:
            all_stats[config_name] = stats
            print(f"\n  {config_name} Summary:")
            for dim in ["Emp-App", "Nat", "Pol-Comp", "Cul-Fit", "Overall"]:
                s = stats[dim]
                print(f"    {dim}: {s['mean']:.3f} ± {s['std']:.3f} [{s['ci95'][0]:.3f}, {s['ci95'][1]:.3f}]")

    # Save combined results
    with open(OUTPUT_DIR / "ablation_summary.json", 'w') as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    # Print comparison table
    print("\n" + "=" * 80)
    print(f"{'Config':<20} {'Emp-App':>10} {'Nat':>10} {'Pol-Comp':>10} {'Cul-Fit':>10} {'Overall':>10}")
    print("-" * 80)
    for name, stats in all_stats.items():
        print(f"{name:<20} {stats['Emp-App']['mean']:>10.3f} {stats['Nat']['mean']:>10.3f} "
              f"{stats['Pol-Comp']['mean']:>10.3f} {stats['Cul-Fit']['mean']:>10.3f} {stats['Overall']['mean']:>10.3f}")

    # Compute drops
    if "full_model" in all_stats:
        full = all_stats["full_model"]["Overall"]["mean"]
        for name, stats in all_stats.items():
            if name != "full_model":
                drop = full - stats["Overall"]["mean"]
                print(f"  Drop ({name}): {drop:+.3f}")

if __name__ == "__main__":
    main()
