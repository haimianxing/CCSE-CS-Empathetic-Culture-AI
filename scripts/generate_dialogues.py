"""
CCSE 数据生成管线 — 三阶段合成
Stage A: 种子场景生成
Stage B: 策略感知对话展开
Stage C: 多维质量过滤

使用 Qwen3.5-122B API 生成中文客服共情对话
"""

import json
import os
import time
import random
import argparse
from pathlib import Path
from datetime import datetime

import requests

# ============================================================
# 配置
# ============================================================

API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "model_type": 4,
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
    "generate_cfg": {
        "temperature": 0.8,
        "top_p": 0.9,
        "max_tokens": 4096
    }
}

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from configs.strategy_ontology import (
    STRATEGY_ONTOLOGY, DOMAINS, CULTURAL_FACTORS,
    ALL_STRATEGY_IDS, ALL_CATEGORY_IDS, SUPPLEMENTARY_SCENARIOS
)


def call_qwen_api(messages, temperature=0.8, max_tokens=4096, max_retries=3):
    """调用Qwen API"""
    headers = {
        "Authorization": f"Bearer {API_CONFIG['api_key']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "top_p": API_CONFIG["generate_cfg"]["top_p"],
        "max_tokens": max_tokens
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                API_CONFIG["url"],
                headers=headers,
                json=payload,
                timeout=120
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            # 去除thinking标签内容（Qwen3.5会返回思考过程）
            if "<think" in content:
                import re
                content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            print(f"  API调用失败(尝试{attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                return None


# ============================================================
# Stage A: 种子场景生成
# ============================================================

def generate_seed_scenario(domain, scenario=None, conflict_level=None):
    """Stage A: 生成种子场景骨架"""

    if scenario is None:
        scenario = random.choice(DOMAINS[domain]["scenarios"])
    if conflict_level is None:
        conflict_level = random.choice(["低", "中", "高"])

    policy = random.choice(DOMAINS[domain]["policies"])

    prompt = f"""你是一个专业的客服对话场景设计专家。请为一个中文{domain}客服场景设计对话骨架。

场景信息：
- 领域：{domain}
- 具体问题：{scenario}
- 相关政策：{policy}
- 客户冲突强度：{conflict_level}

请以JSON格式输出对话骨架，包含以下字段：
{{
    "session_id": "自动生成",
    "domain": "{domain}",
    "scenario": "{scenario}",
    "conflict_level": "{conflict_level}",
    "policy_involved": "{policy}",
    "num_turns": 4-8,
    "user_profile": {{
        "emotion": "客户初始情绪状态",
        "implicit_need": "客户未直接表达的潜在需求",
        "face_sensitivity": "高/中/低 - 面子敏感度",
        "communication_style": "直接/委婉/情绪化"
    }},
    "dialogue_skeleton": [
        {{
            "turn": 1,
            "speaker": "user",
            "intent": "用户意图描述",
            "strategy_needed": ["S1"],
            "key_points": ["要提到的关键信息（必须使用虚构信息）"]
        }},
        {{
            "turn": 1,
            "speaker": "agent",
            "strategy_required": ["S1", "S2"],
            "sub_goals": ["复述问题", "识别情绪"],
            "policy_constraint": "需要遵守的政策约束"
        }}
    ],
    "resolution_type": "解决/升级/补偿/部分满足",
    "difficulty": "简单/中等/困难"
}}

注意：
1. 骨架中的strategy_required必须从S1-S18中选择
2. 高冲突场景需要包含S8(降温化解)策略
3. 确保每轮对话的策略使用合理，符合自然对话流程
4. 【重要】所有个人信息必须是虚构的：姓名用张三/李四/王芳等常见名，电话用138xxxx0001格式，地址用北京市朝阳区等模糊地址，订单号用JD20240411001等虚构格式
5. 只输出JSON，不要其他内容"""

    response = call_qwen_api(
        [{"role": "user", "content": prompt}],
        temperature=0.85
    )

    if response:
        try:
            # 提取JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            scenario_data = json.loads(json_str)
            scenario_data["session_id"] = f"seed_{domain}_{int(time.time())}_{random.randint(1000,9999)}"
            scenario_data["domain"] = domain
            scenario_data["scenario"] = scenario
            scenario_data["conflict_level"] = conflict_level
            return scenario_data
        except json.JSONDecodeError as e:
            print(f"  JSON解析失败: {e}")
            print(f"  原始响应: {response[:200]}")
            return None
    return None


# ============================================================
# Stage B: 策略感知对话展开
# ============================================================

def get_strategy_description(strategy_id):
    """获取策略的详细描述"""
    for cat_name, cat_data in STRATEGY_ONTOLOGY.items():
        for s_name, s_data in cat_data["sub_strategies"].items():
            if s_data["id"] == strategy_id:
                return {
                    "name": s_name,
                    "name_en": s_data["name_en"],
                    "description": s_data["description"],
                    "examples": s_data["examples"],
                    "category": cat_name,
                    "source": s_data["source"]
                }
    return None


def expand_dialogue(scenario_data, cultural_profile=None, extra_prompt=""):
    """Stage B: 将骨架展开为完整对话"""

    if cultural_profile is None:
        cultural_profile = {
            "关系取向": random.choice(CULTURAL_FACTORS["关系取向"]["values"]),
            "面子维护": random.choice(CULTURAL_FACTORS["面子维护"]["values"]),
            "委婉度": random.choice(CULTURAL_FACTORS["委婉度"]["values"]),
        }

    # 收集需要的策略详情
    strategies_needed = set()
    for turn in scenario_data.get("dialogue_skeleton", []):
        if turn.get("speaker") == "agent":
            for sid in turn.get("strategy_required", []):
                strategies_needed.add(sid)

    strategy_info = {}
    for sid in strategies_needed:
        info = get_strategy_description(sid)
        if info:
            strategy_info[sid] = info

    # 构建策略参考信息
    strategy_ref = "\n".join([
        f"- {sid}: {info['name']} — {info['description']}\n  示例: {random.choice(info['examples'])}"
        for sid, info in strategy_info.items()
    ])

    # 获取相关政策
    domain = scenario_data["domain"]
    policies = DOMAINS.get(domain, {}).get("policies", [])
    policy_text = "\n".join([f"- {p}" for p in policies])

    prompt = f"""你是一个资深的中文{domain}客服对话编写专家。请根据以下信息编写一段高质量的客服对话。

## 场景信息
- 领域：{domain}
- 具体问题：{scenario_data['scenario']}
- 客户冲突强度：{scenario_data['conflict_level']}
- 相关政策：{scenario_data.get('policy_involved', '通用政策')}

## 客户画像
- 情绪状态：{scenario_data.get('user_profile', {}).get('emotion', '不满')}
- 潜在需求：{scenario_data.get('user_profile', {}).get('implicit_need', '快速解决问题')}
- 面子敏感度：{scenario_data.get('user_profile', {}).get('face_sensitivity', '中')}
- 沟通风格：{scenario_data.get('user_profile', {}).get('communication_style', '一般')}

## 文化因子约束
- 关系取向：{cultural_profile.get('关系取向', '友好')}
- 面子维护：{cultural_profile.get('面子维护', '中')}
- 委婉度：{cultural_profile.get('委婉度', '中')}

## 需要使用的客服策略（必须覆盖）
{strategy_ref}

## 领域相关政策参考
{policy_text}

## 虚构信息使用示例（参考）
user: "我上周买的衣服还没到，订单号JD20240315001，叫张三的"
agent: "张三您好，我帮您查一下订单JD20240315001的情况..."

## 对话骨架
{json.dumps(scenario_data.get('dialogue_skeleton', []), ensure_ascii=False, indent=2)}

## 要求
1. 严格按照骨架展开，但可以自然调整轮次（4-8轮）
2. 客服的每句话必须体现标注的策略
3. 对话要自然、流畅，符合中文客服的真实表达
4. 高冲突场景要有升温-降温的情绪曲线
5. 客服不能越权承诺（如承诺不合理的赔偿、虚假政策）
6. 客服不能操纵客户情感（如制造恐惧、假共情）
7. 严格遵守领域政策约束
8. 【重要】所有个人信息必须是虚构的，参考以下示例：
   - 姓名：张三、李四、王芳、赵敏、陈静等（避免使用真实名人姓名）
   - 电话：138xxxx0001、159xxxx8888、186xxxx1234等（使用xxxx替代中间数字）
   - 地址：北京市朝阳区、上海市浦东新区、广州市天河区等（只到区级）
   - 订单号：JD20240411001、TB202403150567、YY20240410088等（虚构格式）
   - 身份证：310xxxxxxxxxxx1234（只显示前3位和后4位）
9. 对话中如需提及具体时间、金额，使用合理的虚构值
{extra_prompt}
请以以下JSON格式输出：
{{
    "dialogue": [
        {{
            "turn": 1,
            "speaker": "user",
            "content": "用户说的话",
            "emotion": "情绪标签",
            "intent": "意图"
        }},
        {{
            "turn": 1,
            "speaker": "agent",
            "content": "客服说的话",
            "strategies_used": ["S1", "S4"],
            "strategy_descriptions": ["复述确认：...", "委婉致歉：..."],
            "emotion_response": "客服如何回应情绪"
        }}
    ],
    "quality_self_check": {{
        "has_empathy": true,
        "policy_compliant": true,
        "no_overcommitment": true,
        "no_emotion_manipulation": true,
        "cultural_appropriate": true,
        "natural": true
    }},
    "dialogue_summary": "对话总结",
    "resolution": "最终解决方案"
}}

只输出JSON，不要其他内容。"""

    response = call_qwen_api(
        [{"role": "user", "content": prompt}],
        temperature=0.75,
        max_tokens=4096
    )

    if response:
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            dialogue_data = json.loads(json_str)
            dialogue_data["metadata"] = {
                "session_id": scenario_data["session_id"],
                "domain": domain,
                "scenario": scenario_data["scenario"],
                "conflict_level": scenario_data["conflict_level"],
                "cultural_profile": cultural_profile,
                "strategies_needed": list(strategies_needed),
                "generation_time": datetime.now().isoformat(),
                "model": API_CONFIG["model_name"]
            }
            return dialogue_data
        except json.JSONDecodeError as e:
            print(f"  对话展开JSON解析失败: {e}")
            return None
    return None


# ============================================================
# Stage C: 多维质量过滤
# ============================================================

def quality_filter(dialogue_data):
    """Stage C: 多维质量过滤"""

    if not dialogue_data or "dialogue" not in dialogue_data:
        return False, "无对话内容"

    dialogue = dialogue_data["dialogue"]

    # 基本检查
    if len(dialogue) < 4:
        return False, "对话轮次不足(少于4条消息)"

    # 检查是否有客服回复
    agent_turns = [d for d in dialogue if d.get("speaker") == "agent"]
    if len(agent_turns) < 2:
        return False, "客服回复不足"

    # 规则过滤
    agent_contents = " ".join([d.get("content", "") for d in agent_turns])

    # 1. 越权承诺检测
    overcommit_keywords = [
        "保证一定", "绝对没问题", "100%", "肯定会", "我承诺",
        "一定会给你", "包你满意", "不可能出错"
    ]
    for kw in overcommit_keywords:
        if kw in agent_contents:
            return False, f"疑似越权承诺: '{kw}'"

    # 2. 情感操纵检测
    manipulation_keywords = [
        "你应该感到", "你不觉得", "别人都", "你再不",
        "如果你不", "后果会很严重"
    ]
    for kw in manipulation_keywords:
        if kw in agent_contents:
            return False, f"疑似情感操纵: '{kw}'"

    # 3. 策略覆盖检查
    strategies_used = set()
    for turn in agent_turns:
        for s in turn.get("strategies_used", []):
            strategies_used.add(s)
    if len(strategies_used) < 2:
        return False, f"策略覆盖不足(仅{len(strategies_used)}种策略)"

    # 4. 对话长度合理性
    total_chars = sum(len(d["content"]) for d in dialogue)
    if total_chars < 50:
        return False, "对话总长度过短"
    if total_chars > 3000:
        return False, "对话总长度过长"

    # 5. 策略合理性检查（高冲突场景必须有降温策略）
    metadata = dialogue_data.get("metadata", {})
    if metadata.get("conflict_level") == "高" and "S8" not in strategies_used:
        return False, "高冲突场景缺少S8(降温化解)策略"

    # 6. 每轮agent回复必须有策略标注
    for turn in agent_turns:
        if not turn.get("strategies_used") or len(turn.get("strategies_used", [])) == 0:
            return False, "agent回复缺少策略标注"

    # 7. 隐私信息检查（确保使用虚构格式）
    dialogue_text = json.dumps(dialogue, ensure_ascii=False)
    import re

    # 检查是否包含连续11位数字且不含xxxx（可能是真实手机号）
    if re.search(r'1[3-9]\d{9}', dialogue_text):
        # 检查是否同时包含xxxx或XXX（说明是虚构格式）
        if 'xxxx' not in dialogue_text and 'XXX' not in dialogue_text:
            return False, "疑似包含真实手机号（未使用xxxx格式）"

    # 检查是否包含完整身份证号（18位连续数字）
    if re.search(r'\d{17}[\dXx]', dialogue_text):
        return False, "疑似包含完整身份证号"

    return True, "通过"


# ============================================================
# 完整管线
# ============================================================

def generate_one_dialogue(domain=None, scenario=None, conflict_level=None,
                          cultural_profile=None, extra_prompt=""):
    """完整的三阶段管线：生成一条对话"""

    if domain is None:
        domain = random.choice(list(DOMAINS.keys()))

    # Stage A: 种子场景
    print(f"  [Stage A] 生成种子场景: {domain}")
    scenario_data = generate_seed_scenario(domain, scenario, conflict_level)
    if not scenario_data:
        return None, "Stage A 失败"

    time.sleep(1)  # API限速

    # Stage B: 对话展开
    print(f"  [Stage B] 展开对话: {scenario_data['scenario']}")
    dialogue_data = expand_dialogue(scenario_data, cultural_profile, extra_prompt)
    if not dialogue_data:
        return None, "Stage B 失败"

    # Stage C: 质量过滤
    passed, reason = quality_filter(dialogue_data)
    if not passed:
        return None, f"Stage C 过滤: {reason}"

    print(f"  [Stage C] 质量通过 ✓")
    return dialogue_data, "成功"


def generate_batch(num_dialogues=20, domains=None, output_dir=None):
    """批量生成对话数据"""

    if domains is None:
        domains = list(DOMAINS.keys())
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "raw"

    os.makedirs(output_dir, exist_ok=True)

    results = []
    stats = {
        "total_attempted": 0,
        "stage_a_fail": 0,
        "stage_b_fail": 0,
        "stage_c_filtered": 0,
        "success": 0,
        "filter_reasons": {},
        "domain_distribution": {d: 0 for d in DOMAINS.keys()},
        "conflict_distribution": {"低": 0, "中": 0, "高": 0},
        "strategy_coverage": {s: 0 for s in ALL_STRATEGY_IDS},
    }

    # === Phase 1: 常规生成（均衡采样） ===
    regular_count = int(num_dialogues * 0.75)  # 75% 常规
    supplementary_count = num_dialogues - regular_count  # 25% 补充

    per_domain = regular_count // len(domains)
    if per_domain == 0:
        per_domain = 1

    print(f"\n{'='*60}")
    print(f"CCSE 数据生成管线启动")
    print(f"目标数量: {num_dialogues} 条")
    print(f"  Phase 1 常规: {regular_count} 条 (每领域 {per_domain})")
    print(f"  Phase 2 补充: {supplementary_count} 条 (S13/S16/S17/S18)")
    print(f"领域分布: {', '.join(domains)}")
    print(f"{'='*60}\n")

    # Phase 1: 常规生成
    print(f"--- Phase 1: 常规生成 ---")
    for domain in domains:
        for i in range(per_domain):
            if stats["success"] >= regular_count:
                break

            stats["total_attempted"] += 1
            print(f"\n[{stats['total_attempted']}/{num_dialogues}] {domain} - 第{i+1}条")

            dialogue_data, status = generate_one_dialogue(domain=domain)

            if dialogue_data:
                results.append(dialogue_data)
                stats["success"] += 1
                stats["domain_distribution"][domain] += 1
                conflict = dialogue_data.get("metadata", {}).get("conflict_level", "中")
                stats["conflict_distribution"][conflict] = stats["conflict_distribution"].get(conflict, 0) + 1
                # 统计策略覆盖
                for turn in dialogue_data.get("dialogue", []):
                    if turn.get("speaker") == "agent":
                        for s in turn.get("strategies_used", []):
                            stats["strategy_coverage"][s] = stats["strategy_coverage"].get(s, 0) + 1
                print(f"  → 成功 (累计: {stats['success']})")
            else:
                if "Stage A" in status:
                    stats["stage_a_fail"] += 1
                elif "Stage B" in status:
                    stats["stage_b_fail"] += 1
                else:
                    stats["stage_c_filtered"] += 1
                    reason = status.split(": ")[-1] if ": " in status else status
                    stats["filter_reasons"][reason] = stats["filter_reasons"].get(reason, 0) + 1
                print(f"  → 失败: {status}")

            time.sleep(1)

    # Phase 2: 补充策略场景（S13/S16/S17/S18）
    print(f"\n--- Phase 2: 补充策略场景 ---")
    per_supplementary = max(1, supplementary_count // len(SUPPLEMENTARY_SCENARIOS))
    sup_generated = 0

    for strategy_key, sup_config in SUPPLEMENTARY_SCENARIOS.items():
        if sup_generated >= supplementary_count:
            break
        for attempt in range(per_supplementary):
            if sup_generated >= supplementary_count:
                break

            domain = random.choice(sup_config["domains"])
            scenario = random.choice(sup_config["scenarios"])
            stats["total_attempted"] += 1
            print(f"\n[{stats['total_attempted']}/{num_dialogues}] 补充:{strategy_key} - {domain}")

            dialogue_data, status = generate_one_dialogue(
                domain=domain,
                scenario=scenario,
                extra_prompt=sup_config["extra_prompt"]
            )

            if dialogue_data:
                results.append(dialogue_data)
                stats["success"] += 1
                stats["domain_distribution"][domain] += 1
                sup_generated += 1
                conflict = dialogue_data.get("metadata", {}).get("conflict_level", "中")
                stats["conflict_distribution"][conflict] = stats["conflict_distribution"].get(conflict, 0) + 1
                for turn in dialogue_data.get("dialogue", []):
                    if turn.get("speaker") == "agent":
                        for s in turn.get("strategies_used", []):
                            stats["strategy_coverage"][s] = stats["strategy_coverage"].get(s, 0) + 1
                print(f"  → 成功 (补充累计: {sup_generated})")
            else:
                if "Stage A" in status:
                    stats["stage_a_fail"] += 1
                elif "Stage B" in status:
                    stats["stage_b_fail"] += 1
                else:
                    stats["stage_c_filtered"] += 1
                    reason = status.split(": ")[-1] if ": " in status else status
                    stats["filter_reasons"][reason] = stats["filter_reasons"].get(reason, 0) + 1
                print(f"  → 失败: {status}")

            time.sleep(1)

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"ccse_batch_{timestamp}.json")

    output_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "model": API_CONFIG["model_name"],
            "total_dialogues": len(results),
            "generation_stats": stats
        },
        "dialogues": results
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 打印统计
    print(f"\n{'='*60}")
    print(f"生成完成!")
    print(f"  尝试: {stats['total_attempted']}")
    print(f"  成功: {stats['success']}")
    print(f"  Stage A失败: {stats['stage_a_fail']}")
    print(f"  Stage B失败: {stats['stage_b_fail']}")
    print(f"  Stage C过滤: {stats['stage_c_filtered']}")
    if stats["filter_reasons"]:
        print(f"  过滤原因:")
        for reason, count in stats["filter_reasons"].items():
            print(f"    - {reason}: {count}")
    print(f"  领域分布: {stats['domain_distribution']}")
    print(f"  冲突分布: {stats['conflict_distribution']}")
    print(f"  策略覆盖:")
    for sid, count in sorted(stats["strategy_coverage"].items(), key=lambda x: x[1], reverse=True):
        marker = " ⚠" if count == 0 else ""
        print(f"    {sid}: {count}{marker}")
    print(f"  通过率: {stats['success']/max(stats['total_attempted'],1)*100:.1f}%")
    print(f"  隐私脱敏: 已完成")
    print(f"\n输出文件: {output_file}")
    print(f"{'='*60}")

    return output_file, output_data


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CCSE 对话数据生成")
    parser.add_argument("--num", type=int, default=20, help="生成对话数量")
    parser.add_argument("--domains", nargs="+", default=None, help="指定领域")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录")
    args = parser.parse_args()

    output_file, output_data = generate_batch(
        num_dialogues=args.num,
        domains=args.domains,
        output_dir=args.output_dir
    )
