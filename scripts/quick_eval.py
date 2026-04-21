#!/usr/bin/env python3
"""
快速评测现有对话数据
使用简化的评测协议
"""

import sys
sys.path.insert(0, '/mnt/data2/zcz/neurIps-emnlp')

import json
from pathlib import Path
from scripts.generate_dialogues import call_qwen_api
import time

def quick_evaluate(dialogue):
    """快速评测单条对话"""

    dialogue_text = f"场景：{dialogue['metadata']['domain']} - {dialogue['metadata']['scenario']}\n\n"

    for turn in dialogue['dialogue']:
        speaker = "用户" if turn['speaker'] == 'user' else "客服"
        dialogue_text += f"{speaker}: {turn['content']}\n"

    prompt = f"""评估以下客服对话的质量（1-5分）：

{dialogue_text}

评估维度：
1. 共情适时性：共情是否及时、适度
2. 政策合规性：是否遵守规则、无过度承诺
3. 文化适切性：委婉/面子/尊敬是否得体
4. 自然度：是否流畅、符合中文习惯

请以JSON格式输出：
{{
    "empathy_appropriateness": {{"score": 4, "reasoning": "理由"}},
    "policy_compliance": {{"score": 5, "reasoning": "理由"}},
    "cultural_fit": {{"score": 4, "reasoning": "理由"}},
    "naturalness": {{"score": 3, "reasoning": "理由"}}
}}

只输出JSON。"""

    try:
        response = call_qwen_api([{"role": "user", "content": prompt}], temperature=0.3)

        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response.strip()

        result = json.loads(json_str)
        return result
    except Exception as e:
        return {
            "empathy_appropriateness": {"score": 0, "reasoning": str(e)},
            "policy_compliance": {"score": 0, "reasoning": str(e)},
            "cultural_fit": {"score": 0, "reasoning": str(e)},
            "naturalness": {"score": 0, "reasoning": str(e)}
        }

def main():
    """评测所有对话"""

    # 读取合并的数据
    data_file = Path('/mnt/data2/zcz/neurIps-emnlp/data/raw/all_dialogues_merged.json')

    with open(data_file, 'r', encoding='utf-8') as f:
        dialogues = json.load(f)

    print(f"=== 快速评测 ===")
    print(f"评测数量: {len(dialogues)}条")
    print(flush=True)

    results = []

    for i, dialogue in enumerate(dialogues):
        print(f"[{i+1}/{len(dialogues)}] {dialogue['metadata']['domain']}...", flush=True)

        result = quick_evaluate(dialogue)
        results.append({
            "scenario": dialogue['metadata']['scenario'],
            "domain": dialogue['metadata']['domain'],
            "scores": result
        })

        time.sleep(1.5)  # API限速

    # 保存结果
    timestamp = int(time.time())
    output_file = Path(f'/mnt/data2/zcz/neurIps-emnlp/data/raw/eval_results_{timestamp}.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    avg_scores = {
        "empathy_appropriateness": sum(r['scores']['empathy_appropriateness']['score'] for r in results) / len(results),
        "policy_compliance": sum(r['scores']['policy_compliance']['score'] for r in results) / len(results),
        "cultural_fit": sum(r['scores']['cultural_fit']['score'] for r in results) / len(results),
        "naturalness": sum(r['scores']['naturalness']['score'] for r in results) / len(results)
    }

    print(f"\n{'='*60}")
    print(f"✅ 评测完成！")
    print(f"{'='*60}")
    print(f"\n=== 平均评分 (1-5分) ===")
    for metric, score in avg_scores.items():
        print(f"  {metric}: {score:.2f}")

    print(f"\n保存到: {output_file}")

    return results

if __name__ == "__main__":
    main()
