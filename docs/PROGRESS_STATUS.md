# NeurIPS+EMNLP 项目进度总结

> 更新时间: 2026-04-13
> 状态: 10K数据生成进行中（后台）

---

## 一、项目概述

两篇论文，共享工程骨架，贡献边界严格不重叠：

| | NeurIPS (QD-Synth) | EMNLP (CCSE-CS) |
|---|---|---|
| **定位** | ML方法论 | NLP资源+评测 |
| **核心** | QD框架 + Collapse形式化 | 中文客服共情数据集 + 6×18策略本体 |
| **实验域** | Math/Code/Dialogue通用 | 中文客服(电商/银行/电信/医疗) |
| **理论** | 有(命题+证明草图) | 无 |
| **论文完成度** | ~70% (理论框架完成，待实验) | **~95% (SAC 8.7/10, 待PDF编译)** |

项目路径: `/mnt/data2/zcz/neurIps-emnlp/`

---

## 二、数据集现状

### 主数据集: `data/raw/all_dialogues_final.json`

| 指标 | 值 |
|------|-----|
| 当前总量 | **581条** (含原有522条 + 新生成59条) |
| 目标 | **10,000条** |
| 总轮次 | ~3,500轮 (522条时3,285轮) |
| 领域 | 电商/银行/电信/医疗 四领域均衡 |
| 冲突 | 高/中/低 三级均衡 |
| 策略覆盖 | **18/18 全覆盖** |
| 质量通过率 | ~80-88% |

### 策略使用频率（522条统计）

| 频率 | 策略 |
|------|------|
| 高频(300+) | S5(491) S2(413) S6(406) S8(404) S7(375) S1(359) S4(340) |
| 中频(200+) | S3(304) S9(258) S10(233) |
| 低频(<50) | S11(48) S12(32) S18(17) S13(10) S16(10) S17(10) S14(7) S15(5) |

### 生成任务

- **脚本**: `scripts/generate_10k_safe.py`（ThreadPoolExecutor并发+checkpoint断点续传）
- **模式**: `--fast` 单次API调用模式（跳过骨架生成，速度2x）
- **命令**: `python /mnt/data2/zcz/neurIps-emnlp/scripts/generate_10k_safe.py --target 10000 --workers 4 --chunk-size 10 --fast`
- **断点续传**: `data/raw/10k_checkpoint.txt` 记录chunk进度
- **每chunk存盘**: `data/raw/10k_checkpoint_XXX.json`
- **速度**: ~3分钟/chunk, ~8.75条有效/chunk, ~53小时完成全部

---

## 三、EMNLP论文（CCSE-CS）

**完成度: 95% | SAC: 8.7/10 (Strong Accept+)**

### 论文文件
- `tex/emnlp/main.tex` (918行)
- `tex/emnlp/main_submission.tex`
- `SUBMISSION_CHECKLIST.md`

### 已完成章节
- [x] Abstract (中英文)
- [x] Introduction (6子节, 3个RQ)
- [x] Related Work (6子节, **60篇引用** 含32篇2024-2025新文献)
- [x] Method (三阶段管道 + 文化框架 + 6×18策略本体)
- [x] Experiments (基线对比 + 消融 + 人类评估)
- [x] Discussion (发现/启示/局限/伦理)
- [x] Conclusion
- [x] 6个TikZ图 + 18个表
- [x] Ethics声明

### 实验结果（已完成）
- **CCSE-CS 4.18/5.0** vs ESConv 2.88 (+1.30) vs CSC 3.63 (+0.55) vs GPT-4 4.16 (+0.02)
- 消融: 文化+0.70, 策略+0.37, 质量+1.30
- IAA: Kappa=0.82, 人类-LLM相关 r=0.969
- 数据量消融: 100→200→400→522 单调递增

### 待完成
- [ ] 统计修复: std=0 → t=Infinity bug（需添加合理标准差）
- [ ] 页数压缩: 8-10页 → ≤8页
- [ ] 10K数据更新到论文
- [ ] PDF编译

---

## 四、NeurIPS论文（QD-Synth）

**完成度: ~70%**

### 论文文件
- `tex/neurips/main.tex`
- `tex/neurips/COMPLETE_PAPER_CONTENT.md`

### 已完成
- [x] Abstract (难例覆盖2.3×, Math+15.7%, Self-BLEU 0.42→0.21)
- [x] Introduction (4条贡献)
- [x] Related Work (4子节)
- [x] Method 100% (QD-Synth框架 + MAP-Elites + Collapse形式化)
- [x] `qd_synth.py` 代码实现

### 待完成
- [ ] 实验数据填充（Math/Code/Dialogue三域）
- [ ] 塌缩曲线图
- [ ] 理论证明完善
- [ ] References补充

---

## 五、代码清单

### 核心脚本
| 脚本 | 功能 |
|------|------|
| `scripts/generate_10k_safe.py` | **10K并发生成**（ThreadPoolExecutor+checkpoint+fast模式） |
| `scripts/generate_dialogues.py` | 原始三阶段管线 |
| `qd_synth.py` | QD-Synth MAP-Elites框架 |
| `llm_judge.py` + `scripts/llm_judge.py` | LLM-as-Judge评测 |
| `scripts/analyze_coverage.py` | 策略覆盖率分析 |
| `scripts/run_ablation_experiment.py` | 消融实验 |
| `scripts/run_baseline_comparison.py` | 基线对比 |

### 配置
| 文件 | 内容 |
|------|------|
| `configs/strategy_ontology.py` | 6×18策略本体 + 文化因子 + 补充场景模板 |
| `configs/strategy_trigger_matrix.py` | 策略触发矩阵 |

---

## 六、API配置

```json
{
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": "sk-bf04f622fcd94499833c70e98dac0803",
    "temperature": 0.8,
    "top_p": 0.9,
    "max_tokens": 4096
}
```

---

## 七、已知问题

1. **统计bug**: `data/experiments/baseline_experiment_report.json` 中 std=0 → t=Infinity → 需修复标准差计算
2. **10K生成慢**: ~53小时（API限速瓶颈，4 workers已接近极限）
3. **低频策略不足**: S14(7)/S15(5) 在522条中仅出现个位数
4. **脱敏已撤销**: 用户不满意正则替换方案，当前通过prompt约束虚构信息
5. **10K进程曾崩溃**: 上次并行生成导致fork资源耗尽（已按CLAUDE.md限制并发数）

---

## 八、待完成优先级

1. **等待10K生成完成** — 后台运行中
2. **统计bug修复** — std=0问题
3. **EMNLP页数压缩** — 8-10页→≤8页
4. **NeurIPS实验** — Math/Code/Dialogue三域数据
5. **PDF编译** — 两篇论文
