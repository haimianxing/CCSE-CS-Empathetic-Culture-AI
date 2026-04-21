#!/usr/bin/env python3
"""
策略覆盖分析工具
分析所有现有数据，识别缺失策略，生成补充计划
"""

import json
from pathlib import Path
from collections import Counter

def analyze_coverage():
    """分析策略覆盖情况"""

    # 收集所有数据
    data_dir = Path('/mnt/data2/zcz/neurIps-emnlp/data/raw')
    json_files = list(data_dir.glob('*.json'))

    all_dialogues = []
    for f in json_files:
        try:
            with open(f, 'r', encoding='utf-8') as data:
                d = json.load(data)
                if isinstance(d, list):
                    all_dialogues.extend(d)
                elif isinstance(d, dict) and 'dialogues' in d:
                    all_dialogues.extend(d['dialogues'])
                elif isinstance(d, dict) and 'dialogue' in d:
                    all_dialogues.append(d)
        except:
            pass

    print(f"=== 策略覆盖分析 ===")
    print(f"分析文件数: {len(json_files)}")
    print(f"对话总数: {len(all_dialogues)}")

    # 统计策略
    strategies = Counter()
    strategy_turns = Counter()
    domains = Counter()
    conflicts = Counter()

    for d in all_dialogues:
        metadata = d.get('metadata', {})
        for s in metadata.get('strategies_needed', []):
            strategies[s] += 1

        # 统计每轮使用的策略
        for turn in d.get('dialogue', []):
            if turn.get('speaker') == 'agent':
                for s in turn.get('strategies_used', []):
                    strategy_turns[s] += 1

        domains[metadata.get('domain', '')] += 1
        conflicts[metadata.get('conflict_level', '')] += 1

    print(f"\n=== 策略覆盖统计 ===")
    print(f"覆盖策略数: {len(strategies)}/18")
    print(f"总策略提及次数: {sum(strategies.values())}")

    print(f"\n=== 策略分布 ===")
    all_strategies = [f"S{i}" for i in range(1, 19)]
    for s in sorted(strategies.keys()):
        print(f"  {s}: {strategies[s]}次 (骨架{strategies[s]/len(all_dialogues)*100:.1f}条/对话)")

    missing = [s for s in all_strategies if s not in strategies]
    print(f"\n=== 缺失策略 ({len(missing)}/18) ===")
    for s in missing:
        print(f"  {s}: 需要专项生成")

    print(f"\n=== 领域分布 ===")
    for domain, count in domains.items():
        pct = count / len(all_dialogues) * 100
        print(f"  {domain}: {count} ({pct:.1f}%)")

    print(f"\n=== 冲突分布 ===")
    for conflict, count in conflicts.items():
        pct = count / len(all_dialogues) * 100
        print(f"  {conflict}: {count} ({pct:.1f}%)")

    # 识别最稀缺的策略（需要优先补充）
    print(f"\n=== 优先补充建议 ===")
    print("缺失策略按场景类型:")
    print("  关系修复类: S14(跟进闭环), S15(长期维护)")
    print("    → 需要完整收尾的对话")
    print("  补偿关怀类: S13(补偿关怀)")
    print("    → 需要投诉+解决场景")
    print("  文化适配类: S16(尊敬升级), S17(节日关怀)")
    print("    → 需要特殊场景触发")
    print("  方案推进类: S11(选项呈现), S12(预期管理)")
    print("    → 需要多方案或延时场景")

    # 分析对话长度
    lengths = [len(d.get('dialogue', [])) for d in all_dialogues]
    print(f"\n=== 对话长度分析 ===")
    print(f"  最短: {min(lengths)} 轮")
    print(f"  最长: {max(lengths)} 轮")
    print(f"  平均: {sum(lengths)/len(lengths):.1f} 轮")

    # 分析S14/S15触发条件
    print(f"\n=== S14/S15 缺失分析 ===")
    long_dialogues = [d for d in all_dialogues if len(d.get('dialogue', [])) >= 6]
    print(f"  对话≥6轮: {len(long_dialogues)} 条")
    if long_dialogues:
        # 检查最后几轮是否有S14/S15
        with_s14_s15 = 0
        for d in long_dialogues:
            last_turns = d.get('dialogue', [])[-3:]
            for turn in last_turns:
                if turn.get('speaker') == 'agent':
                    if 'S14' in turn.get('strategies_used', []):
                        with_s14_s15 += 1
                        break
                    if 'S15' in turn.get('strategies_used', []):
                        with_s14_s15 += 1
                        break

        print(f"  长对话中含S14/S15: {with_s14_s15} 条")
        print(f"  问题: 长对话往往缺乏收尾策略")
        print(f"  建议: 在长对话末尾强制添加S14/S15")

    return {
        'total': len(all_dialogues),
        'strategies': dict(strategies),
        'coverage': len(strategies),
        'missing': missing,
        'domains': dict(domains),
        'conflicts': dict(conflicts)
    }

def generate_missing_strategy_prompts():
    """生成缺失策略的补充方案"""

    missing_strategies = {
        'S11': {
            '场景': '退货换货场景',
            '对话结构': '用户: "我要退货" → Agent: 给出选项(换货/退款/补偿) → 用户: 选择',
            '关键话术': '您看是希望换货还是退款呢？我们也可以为您提供补偿方案。'
        },
        'S12': {
            '场景': '跨部门协调场景',
            '对话结构': '用户: "什么时候能解决？" → Agent: 给出时间预期',
            '关键话术': '通常处理时间是1-3天，如果超时我会主动跟进。'
        },
        'S13': {
            '场景': '投诉升级后',
            '对话结构': 'Agent: 问题已解决，为表示歉意，我们提供...',
            '关键话术': '为了表示歉意，我们为您申请了20元优惠券。'
        },
        'S14': {
            '场景': '对话结束前',
            '对话结构': 'Agent: 还有其他问题吗？请对我的服务进行评价。',
            '关键话术': '请您对我的服务进行评价，3天后我会再次联系您确认问题是否彻底解决。'
        },
        'S15': {
            '场景': '对话收尾',
            '对话结构': 'Agent: 祝您生活愉快，后续有问题随时联系我们。',
            '关键话术': '期待下次为您服务，我们会定期为您提供最新的产品信息。'
        },
        'S16': {
            '场景': '老年/VIP客户',
            '对话结构': 'Agent: 叔叔/阿姨您好，您放心我来帮您处理。',
            '关键话术': '尊敬的XXX会员，感谢您的信任，我们为您开通绿色通道。'
        },
        'S17': {
            '场景': '节日前后',
            '对话结构': 'Agent: 快过年了，提前祝您新年快乐，这个问题加急处理。',
            '关键话术': '中秋节快乐，希望这个问题解决后您能好好过节。'
        }
    }

    print(f"\n=== 缺失策略补充方案 ===")
    for s, info in missing_strategies.items():
        print(f"\n{s} {info['场景']}")
        print(f"  结构: {info['对话结构']}")
        print(f"  话术: {info['关键话术']}")
        print(f"  建议: 在相关场景的prompt中强制要求使用{s}")

if __name__ == "__main__":
    result = analyze_coverage()
    generate_missing_strategy_prompts()

    print(f"\n=== 下一步建议 ===")
    print(f"1. 等待当前10条生成完成")
    print(f"2. 运行分析工具，查看最终策略覆盖")
    print(f"3. 针对缺失策略生成专项对话")
    print(f"4. 重复生成直到达到15/18策略覆盖")
