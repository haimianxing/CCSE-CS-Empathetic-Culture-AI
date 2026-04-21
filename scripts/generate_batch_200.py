#!/usr/bin/env python3
"""
大规模生成200条对话 - v0.1里程碑
使用简单可靠的单进程循环，确保稳定性
"""

import sys
sys.path.insert(0, '/mnt/data2/zcz/neurIps-emnlp')

from scripts.generate_dialogues import generate_one_dialogue
from configs.strategy_ontology import DOMAINS
import json
import time
from pathlib import Path
from datetime import datetime

def main():
    """生成200条对话"""

    print("=== 大规模生成200条对话 - v0.1里程碑 ===")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(flush=True)

    output_dir = Path('/mnt/data2/zcz/neurIps-emnlp/data/raw')
    results = []
    stats = {
        'success': 0,
        'fail': 0,
        'strategies': {},
        'domains': {d: 0 for d in DOMAINS.keys()}
    }

    domains = list(DOMAINS.keys())
    checkpoint_interval = 20  # 每20条保存一次检查点

    for i in range(200):
        # 轮换领域
        domain = domains[i % len(domains)]

        print(f"[{i+1}/200] 生成 {domain}...", flush=True)

        try:
            start = time.time()
            dialogue, msg = generate_one_dialogue(domain=domain)
            elapsed = time.time() - start

            if dialogue:
                results.append(dialogue)
                stats['success'] += 1
                stats['domains'][domain] += 1

                # 统计策略
                for s in dialogue.get('metadata', {}).get('strategies_needed', []):
                    stats['strategies'][s] = stats['strategies'].get(s, 0) + 1

                print(f"  ✓ 成功 ({elapsed:.1f}s) | 总计:{len(results)}", flush=True)
            else:
                stats['fail'] += 1
                print(f"  ✗ {msg} | 失败:{stats['fail']}", flush=True)

        except Exception as e:
            stats['fail'] += 1
            print(f"  ✗ 异常: {e} | 失败:{stats['fail']}", flush=True)

        # 每20条保存检查点
        if (i + 1) % checkpoint_interval == 0 and results:
            checkpoint_file = output_dir / f'batch_200_checkpoint_{i+1}_{int(time.time())}.json'
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  💾 检查点已保存", flush=True)

        # API限速
        time.sleep(2)

    # 最终保存
    if results:
        timestamp = int(time.time())
        output_file = output_dir / f'ccse_batch_200_final_{timestamp}.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ 生成完成！")
        print(f"{'='*60}")
        print(f"成功: {stats['success']}")
        print(f"失败: {stats['fail']}")
        print(f"成功率: {stats['success']/(stats['success']+stats['fail'])*100:.1f}%")
        print(f"\n保存到: {output_file}")
        print(f"文件大小: {output_file.stat().st_size / 1024:.1f}KB")

        print(f"\n=== 策略覆盖 ===")
        print(f"覆盖策略数: {len(stats['strategies'])}/18")
        for s in sorted(stats['strategies'].keys()):
            print(f"  {s}: {stats['strategies'][s]}次")

        print(f"\n=== 领域分布 ===")
        for domain, count in stats['domains'].items():
            pct = count / len(results) * 100 if results else 0
            print(f"  {domain}: {count} ({pct:.1f}%)")

    else:
        print("\n❌ 无数据生成")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return results

if __name__ == "__main__":
    main()
