"""
QD-Synth: Quality-Diversity 框架原型
Dialogue域的MAP-Elites实现

核心思想：
- 行为描述子(Behavior Descriptor): φ(x) ∈ [0,1]^d
- 质量(Quality): q(x) — 裁判打分
- 档案库(Archive): A 在离散网格G上，每格保留精英(最高q)
"""

import numpy as np
import json
from typing import List, Dict, Tuple, Callable, Any
from dataclasses import dataclass
from pathlib import Path
import time

@dataclass
class ArchiveCell:
    """档案库单元格"""
    dialogue: dict  # 对话数据
    quality: float  # 质量分数
    descriptor: np.ndarray  # 行为描述子
    added_at: str  # 添加时间

class DialogueDescriptor:
    """
    Dialogue域的行为描述子计算

    三维描述子:
    1. 共情强度 (empathy_strength): [0,1]
       - 计算: (S2 + S7 + S8 出现次数) / 总轮次
    2. 策略类型 (strategy_type): one-hot 6维
       - C1: 倾听确认, C2: 面子维护, C3: 情绪安抚, C4: 方案推进, C5: 关系修复, C6: 文化适配
    3. 冲突强度 (conflict_intensity): {低:0.25, 中:0.5, 高:0.75}
    """

    # 策略分类映射
    STRATEGY_CATEGORIES = {
        "C1": ["S1", "S2", "S3"],  # 倾听确认
        "C2": ["S4", "S5", "S6"],  # 面子维护
        "C3": ["S7", "S8", "S9"],  # 情绪安抚
        "C4": ["S10", "S11", "S12"],  # 方案推进
        "C5": ["S13", "S14", "S15"],  # 关系修复
        "C6": ["S16", "S17", "S18"]  # 文化适配
    }

    # 冲突强度映射
    CONFLICT_MAPPING = {
        "低": 0.25,
        "中": 0.5,
        "高": 0.75
    }

    def compute(self, dialogue_data: dict) -> np.ndarray:
        """
        计算行为描述子

        Returns:
            np.ndarray: [empathy_strength, strategy_category, conflict_intensity]
        """
        dialogue = dialogue_data.get("dialogue", [])

        # 1. 计算共情强度
        empathy_strategies = set(["S2", "S7", "S8"])
        empathy_count = 0
        total_turns = 0

        for turn in dialogue:
            if turn.get("speaker") == "agent":
                total_turns += 1
                strategies_used = turn.get("strategies_used", [])
                if any(s in empathy_strategies for s in strategies_used):
                    empathy_count += 1

        empathy_strength = min(1.0, empathy_count / max(1, total_turns))

        # 2. 确定主要策略类型（使用最多的类别）
        category_counts = {cat: 0 for cat in self.STRATEGY_CATEGORIES.keys()}

        for turn in dialogue:
            if turn.get("speaker") == "agent":
                strategies_used = turn.get("strategies_used", [])
                for strategy in strategies_used:
                    for cat, strategies in self.STRATEGY_CATEGORIES.items():
                        if strategy in strategies:
                            category_counts[cat] += 1

        # 找出使用最多的类别
        main_category = max(category_counts, key=category_counts.get)
        strategy_category = list(self.STRATEGY_CATEGORIES.keys()).index(main_category) / 5.0  # 归一化到[0,1]

        # 3. 冲突强度
        conflict_level = dialogue_data.get("metadata", {}).get("conflict_level", "中")
        conflict_intensity = self.CONFLICT_MAPPING.get(conflict_level, 0.5)

        return np.array([empathy_strength, strategy_category, conflict_intensity])

class DialogueQualityJudge:
    """
    Dialogue域的质量裁判（规则版）

    评分维度:
    1. Emp-App (共情适时性): [0,1]
    2. Pol-Comp (政策合规性): [0,1]
    3. Cul-Fit (文化适切性): [0,1]
    4. Nat (自然度): [0,1]

    总质量: 平均分
    """

    def judge(self, dialogue_data: dict) -> float:
        """
        评估对话质量

        Returns:
            float: 质量分数 [0,1]
        """
        dialogue = dialogue_data.get("dialogue", [])
        metadata = dialogue_data.get("metadata", {})

        # 1. Emp-App: 共情适时性
        empathy_strategies = set(["S2", "S7", "S8", "S9"])
        empathy_count = 0
        agent_turns = 0

        for turn in dialogue:
            if turn.get("speaker") == "agent":
                agent_turns += 1
                strategies_used = turn.get("strategies_used", [])
                if any(s in empathy_strategies for s in strategies_used):
                    empathy_count += 1

        emp_app = min(1.0, empathy_count / max(1, agent_turns))

        # 2. Pol-Comp: 政策合规性（检查quality_self_check）
        quality_check = dialogue_data.get("quality_self_check", {})
        pol_comp = 1.0 if all([
            quality_check.get("policy_compliant", False),
            quality_check.get("no_overcommitment", True),
            quality_check.get("no_emotion_manipulation", True)
        ]) else 0.5

        # 3. Cul-Fit: 文化适切性（检查文化因子是否合理应用）
        cultural_profile = metadata.get("cultural_profile", {})
        # 简化版：检查是否使用了文化相关策略
        cultural_strategies = set(["S4", "S5", "S6", "S16", "S17", "S18"])
        has_cultural = False
        for turn in dialogue:
            if turn.get("speaker") == "agent":
                strategies_used = turn.get("strategies_used", [])
                if any(s in cultural_strategies for s in strategies_used):
                    has_cultural = True
                    break

        cul_fit = 1.0 if has_cultural else 0.7  # 有文化策略加分，但不是必须

        # 4. Nat: 自然度（检查对话长度和多样性）
        dialogue_natural = quality_check.get("natural", True)
        nat = 1.0 if dialogue_natural else 0.5

        # 平均分
        quality = (emp_app + pol_comp + cul_fit + nat) / 4.0

        return quality

class QDArchive:
    """
    QD档案库：MAP-Elites实现

    在离散网格上维护精英样本
    """

    def __init__(self, descriptor_dim: int = 3, grid_res: int = 10):
        """
        Args:
            descriptor_dim: 描述子维度
            grid_res: 网格分辨率（每维的区间数）
        """
        self.descriptor_dim = descriptor_dim
        self.grid_res = grid_res
        self.archive = {}  # (g1, g2, ..., gd) -> ArchiveCell
        self.descriptor_computer = DialogueDescriptor()
        self.quality_judge = DialogueQualityJudge()

    def discretize(self, descriptor: np.ndarray) -> Tuple[int, ...]:
        """
        将连续描述子映射到离散网格

        Args:
            descriptor: [d1, d2, ..., dd]

        Returns:
            Tuple: (g1, g2, ..., gd)
        """
        grid_coords = tuple(
            int(min(d * self.grid_res, self.grid_res - 1))
            for d in descriptor
        )
        return grid_coords

    def add(self, dialogue_data: dict) -> bool:
        """
        添加对话到档案库

        MAP-Elites规则：
        1. 如果网格为空，直接添加
        2. 如果网格已存在，仅当新样本质量更高时替换

        Args:
            dialogue_data: 对话数据

        Returns:
            bool: 是否添加成功（新格或替换）
        """
        # 计算描述子和质量
        descriptor = self.descriptor_computer.compute(dialogue_data)
        quality = self.quality_judge.judge(dialogue_data)

        # 映射到网格
        grid_coord = self.discretize(descriptor)

        # MAP-Elites更新规则
        if grid_coord not in self.archive:
            # 新格，直接添加
            self.archive[grid_coord] = ArchiveCell(
                dialogue=dialogue_data,
                quality=quality,
                descriptor=descriptor,
                added_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
            return True
        else:
            # 已存在，比较质量
            if quality > self.archive[grid_coord].quality:
                self.archive[grid_coord] = ArchiveCell(
                    dialogue=dialogue_data,
                    quality=quality,
                    descriptor=descriptor,
                    added_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                return True
            return False

    def get_coverage(self) -> float:
        """
        计算网格占用率（覆盖率）

        Returns:
            float: 占用率 [0,1]
        """
        total_cells = self.grid_res ** self.descriptor_dim
        occupied_cells = len(self.archive)
        return occupied_cells / total_cells

    def get_entropy(self) -> float:
        """
        计算档案熵（分布均匀性）

        Returns:
            float: 熵值
        """
        if not self.archive:
            return 0.0

        # 计算每个格的质量分布（用于熵计算）
        qualities = [cell.quality for cell in self.archive.values()]
        if not qualities:
            return 0.0

        total = sum(qualities)
        if total == 0:
            return 0.0

        # 归一化
        probs = [q / total for q in qualities]

        # 计算熵
        entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)
        return entropy

    def get_statistics(self) -> dict:
        """
        获取档案库统计信息

        Returns:
            dict: 统计信息
        """
        if not self.archive:
            return {
                "total_samples": 0,
                "coverage": 0.0,
                "entropy": 0.0,
                "avg_quality": 0.0,
                "grid_resolution": self.grid_res,
                "descriptor_dim": self.descriptor_dim
            }

        qualities = [cell.quality for cell in self.archive.values()]

        return {
            "total_samples": len(self.archive),
            "coverage": self.get_coverage(),
            "entropy": self.get_entropy(),
            "avg_quality": np.mean(qualities),
            "min_quality": min(qualities),
            "max_quality": max(qualities),
            "grid_resolution": self.grid_res,
            "descriptor_dim": self.descriptor_dim
        }

    def export_dataset(self, output_path: str):
        """
        导出档案库为数据集

        Args:
            output_path: 输出文件路径
        """
        output_data = {
            "metadata": {
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "archive_stats": self.get_statistics(),
                "qd_synth_version": "0.1.0"
            },
            "dialogues": [cell.dialogue for cell in self.archive.values()]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 数据集已导出到: {output_path}")
        print(f"   总样本数: {len(self.archive)}")
        print(f"   覆盖率: {self.get_coverage():.2%}")
        print(f"   平均质量: {np.mean([cell.quality for cell in self.archive.values()]):.3f}")

def demo_qd_synth():
    """QD-Synth演示"""
    print("=== QD-Synth 框架演示 ===\n")

    # 创建档案库
    archive = QDArchive(descriptor_dim=3, grid_res=5)

    # 加载已有的对话数据
    data_dir = Path(__file__).parent / "data" / "raw"
    json_files = list(data_dir.glob("ccse_batch_*.json"))

    if not json_files:
        print("⚠️  未找到对话数据，请先运行生成脚本")
        return

    print(f"找到 {len(json_files)} 个数据文件\n")

    added_count = 0
    replaced_count = 0

    for json_file in json_files:
        print(f"处理: {json_file.name}")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # 如果是批次文件，提取对话列表
            if isinstance(data, list):
                dialogues = data
            elif isinstance(data, dict) and "dialogues" in data:
                dialogues = data["dialogues"]
            else:
                dialogues = [data]

            for dialogue in dialogues:
                # 先检查网格是否已存在
                descriptor = archive.descriptor_computer.compute(dialogue)
                grid_coord = archive.discretize(descriptor)
                was_empty = grid_coord not in archive.archive

                result = archive.add(dialogue)
                if result:
                    if was_empty:
                        added_count += 1
                    else:
                        replaced_count += 1

    print(f"\n=== 档案库统计 ===")
    print(f"新增: {added_count}")
    print(f"替换: {replaced_count}")
    print(f"总样本: {len(archive.archive)}")

    stats = archive.get_statistics()
    print(f"\n详细统计:")
    print(f"  覆盖率: {stats['coverage']:.2%}")
    print(f"  熵: {stats['entropy']:.3f}")
    print(f"  平均质量: {stats['avg_quality']:.3f}")
    print(f"  质量范围: [{stats['min_quality']:.3f}, {stats['max_quality']:.3f}]")

    # 导出数据集
    output_dir = Path(__file__).parent / "data" / "qd_synth"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ccse_qd_dataset_{int(time.time())}.json"

    archive.export_dataset(str(output_path))

    print(f"\n=== QD-Synth 演示完成 ===")

if __name__ == "__main__":
    demo_qd_synth()
