import os
"""
LLM-as-Judge 评测协议
双裁判设计：Judge-A(偏共情) vs Judge-B(偏合规)
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Tuple
import requests

# API配置
API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
}

def call_llm_api(messages: List[Dict], temperature: float = 0.3) -> str:
    """调用LLM API"""
    headers = {
        "Authorization": f"Bearer {API_CONFIG['api_key']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2048
    }

    try:
        resp = requests.post(API_CONFIG["url"], headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        # 去除thinking标签
        if "<think" in content:
            import re
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()

        return content
    except Exception as e:
        print(f"API调用失败: {e}")
        return None

# ========================================
# Judge-A: 偏共情的裁判
# ========================================

JUDGE_A_SYSTEM_PROMPT = """你是一个专业的客服对话评测专家，专注于评估共情质量和情感连接。

你的评测标准：
1. Emp-App (共情适时性): 客服的共情表达是否及时、适度？
   - 及时：在客户表达情绪时快速响应
   - 适度：共情程度与客户情绪强度匹配，不过度也不过少
   - 自然：共情表达真诚，不机械

2. Nat (自然度): 对话是否流畅自然？
   - 语言流畅，无翻译腔
   - 符合中文口语习惯
   - 回复长度适中，不过于冗长或简短

请对以下对话进行评分，每个维度1-5分：
- 1分：很差
- 2分：较差
- 3分：一般
- 4分：较好
- 5分：非常好

请严格按照以下JSON格式输出，不要有任何其他内容：
{
    "Emp-App": 分数,
    "Nat": 分数,
    "rationale": "评分理由（简述）"
}
"""

def judge_a(dialogue_data: dict) -> dict:
    """
    Judge-A评测：侧重共情和自然度

    Args:
        dialogue_data: 对话数据

    Returns:
        dict: 评测结果
    """
    dialogue = dialogue_data.get("dialogue", [])
    domain = dialogue_data.get("metadata", {}).get("domain", "未知")

    # 构建对话文本
    dialogue_text = "\n".join([
        f"{turn['speaker']}: {turn['content']}"
        for turn in dialogue
    ])

    # 检查策略使用情况
    agent_turns = [t for t in dialogue if t.get("speaker") == "agent"]
    strategies_used = set()
    for turn in agent_turns:
        strategies_used.update(turn.get("strategies_used", []))

    user_prompt = f"""请评测以下客服对话：

【领域】：{domain}
【对话】：
{dialogue_text}

【客服使用的策略】：{', '.join(sorted(strategies_used)) if strategies_used else '无'}

请给出评分。"""

    messages = [
        {"role": "system", "content": JUDGE_A_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = call_llm_api(messages, temperature=0.3)

    if response:
        try:
            # 提取JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            result = json.loads(json_str)
            result["judge"] = "A"
            return result
        except json.JSONDecodeError:
            print(f"Judge-A JSON解析失败: {response[:200]}")
            return {"judge": "A", "error": "JSON解析失败", "raw_response": response}
    else:
        return {"judge": "A", "error": "API调用失败"}

# ========================================
# Judge-B: 偏合规的裁判
# ========================================

JUDGE_B_SYSTEM_PROMPT = """你是一个专业的客服对话评测专家，专注于评估政策合规性和服务质量。

你的评测标准：
1. Pol-Comp (政策合规性): 客服是否遵守政策规则？
   - 不越权承诺：不保证不确定的结果（"保证一定"、"100%"等）
   - 拒绝合规：需要拒绝时给出清晰理由
   - 核验规范：身份验证等流程符合规定
   - 政策准确：引用的政策正确无误

2. Cul-Fit (文化适切性): 文化应对是否得体？
   - 委婉度：拒绝/坏消息的包装程度适当
   - 面子维护：避免指责客户，给客户台阶下
   - 尊敬度：根据客户身份使用适当的敬语
   - 文化敏感性：符合中文文化习惯

请对以下对话进行评分，每个维度1-5分：
- 1分：很差
- 2分：较差
- 3分：一般
- 4分：较好
- 5分：非常好

请严格按照以下JSON格式输出，不要有任何其他内容：
{
    "Pol-Comp": 分数,
    "Cul-Fit": 分数,
    "rationale": "评分理由（简述）"
}
"""

def judge_b(dialogue_data: dict) -> dict:
    """
    Judge-B评测：侧重新规合规和文化适切

    Args:
        dialogue_data: 对话数据

    Returns:
        dict: 评测结果
    """
    dialogue = dialogue_data.get("dialogue", [])
    domain = dialogue_data.get("metadata", {}).get("domain", "未知")

    # 构建对话文本
    dialogue_text = "\n".join([
        f"{turn['speaker']}: {turn['content']}"
        for turn in dialogue
    ])

    # 检查质量自检
    quality_check = dialogue_data.get("quality_self_check", {})
    check_items = []
    if quality_check:
        for key, value in quality_check.items():
            if isinstance(value, bool) and not value:
                check_items.append(f"{key}: 未通过")

    user_prompt = f"""请评测以下客服对话：

【领域】：{domain}
【对话】：
{dialogue_text}

【质量自检问题】：{'; '.join(check_items) if check_items else '无'}

请给出评分。"""

    messages = [
        {"role": "system", "content": JUDGE_B_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = call_llm_api(messages, temperature=0.3)

    if response:
        try:
            # 提取JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            result = json.loads(json_str)
            result["judge"] = "B"
            return result
        except json.JSONDecodeError:
            print(f"Judge-B JSON解析失败: {response[:200]}")
            return {"judge": "B", "error": "JSON解析失败", "raw_response": response}
    else:
        return {"judge": "B", "error": "API调用失败"}

# ========================================
# 双裁判综合
# ========================================

def dual_judge_evaluate(dialogue_data: dict) -> dict:
    """
    双裁判评测：综合Judge-A和Judge-B的评分

    Args:
        dialogue_data: 对话数据

    Returns:
        dict: 综合评测结果
    """
    print(f"  [Judge-A] 评测共情和自然度...")
    result_a = judge_a(dialogue_data)
    time.sleep(1)  # API限速

    print(f"  [Judge-B] 评测合规和文化...")
    result_b = judge_b(dialogue_data)

    # 综合结果
    combined = {
        "dialogue_id": dialogue_data.get("metadata", {}).get("session_id", "unknown"),
        "judge_a": result_a,
        "judge_b": result_b,
        "overall_score": None,
        "dimension_scores": {
            "Emp-App": result_a.get("Emp-App", 0),
            "Nat": result_a.get("Nat", 0),
            "Pol-Comp": result_b.get("Pol-Comp", 0),
            "Cul-Fit": result_b.get("Cul-Fit", 0),
        }
    }

    # 计算总分（平均）
    scores = [
        result_a.get("Emp-App", 0),
        result_a.get("Nat", 0),
        result_b.get("Pol-Comp", 0),
        result_b.get("Cul-Fit", 0),
    ]
    valid_scores = [s for s in scores if isinstance(s, (int, float))]
    if valid_scores:
        combined["overall_score"] = sum(valid_scores) / len(valid_scores)

    return combined

# ========================================
# 批量评测
# ========================================

def batch_evaluate(dialogues: List[dict], output_path: str = None):
    """
    批量评测对话

    Args:
        dialogues: 对话列表
        output_path: 输出文件路径
    """
    results = []

    print(f"=== 批量评测 {len(dialogues)} 条对话 ===\n")

    for i, dialogue in enumerate(dialogues, 1):
        print(f"[{i}/{len(dialogues)}] 评测对话 {dialogue.get('metadata', {}).get('session_id', f'#{i}')}...")

        result = dual_judge_evaluate(dialogue)
        results.append(result)

        # 显示结果
        overall = result.get("overall_score", "N/A")
        print(f"  总分: {overall}")
        for dim, score in result.get("dimension_scores", {}).items():
            if isinstance(score, (int, float)):
                print(f"  {dim}: {score}")

        print()

        time.sleep(2)  # API限速

    # 保存结果
    if output_path:
        output = {
            "metadata": {
                "total_dialogues": len(dialogues),
                "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "avg_scores": {
                    dim: sum(r["dimension_scores"].get(dim, [0]*4)[0] for r in results if isinstance(r["dimension_scores"].get(dim), (int, float))) / len(results)
                    for dim in ["Emp-App", "Nat", "Pol-Comp", "Cul-Fit"]
                }
            },
            "results": results
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"✅ 结果已保存到: {output_path}")

    return results

# ========================================
# 主程序
# ========================================

if __name__ == "__main__":
    import sys

    # 加载对话数据
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = "data/raw/ccse_batch_200_*.json"

    import glob
    json_files = glob.glob(input_path)

    if not json_files:
        print(f"未找到数据文件: {input_path}")
        sys.exit(1)

    # 加载对话
    dialogues = []
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                dialogues.extend(data)
            elif isinstance(data, dict) and "dialogues" in data:
                dialogues.extend(data["dialogues"])
            else:
                dialogues.append(data)

    print(f"加载了 {len(dialogues)} 条对话\n")

    # 批量评测
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"data/evaluation/llm_judge_results_{timestamp}.json"

    batch_evaluate(dialogues, output_path)
