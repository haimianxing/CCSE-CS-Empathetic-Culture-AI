# QD-Synth 实验设计方案（NeurIPS SAC 审稿人视角）

## 审稿结论：Strong Reject（2.2/10）→ 需彻底重构

### 因果链断裂诊断
```
声称解决的问题          实际验证的内容         断裂点
─────────────────────────────────────────────────
迭代合成→分布收窄  ≠  静态pool的top-k筛选  ← 实验场景错位
覆盖率提升→性能提升  ≠  只有分布指标        ← 缺下游验证
理论保证（Lipschitz）≠  LLM评分不连续       ← 假设不成立
公式(2)有λ         ≠  算法1无λ            ← 方法-公式脱节
QD优于所有基线     ≠  vs去重仅0.8%差距     ← 核心优势不成立
```

---

## 环境资源
- GPU: 3×A800-SXM4-80GB (GPU0已占74GB, GPU1/2空闲)
- 内存: 1.8TB
- API: Qwen3.5-122B via DashScope ($DASHSCOPE_API_KEY)
- 已有模型: deepseek-vl-1.3b-chat
- 依赖: transformers 4.57.6, peft 0.17.1, trl 0.7.1, accelerate 1.10.1, modelscope
- 需下载: Qwen2.5-1.5B-Instruct (~3GB)

---

## 用户决策
- 理论修复: 方案B（约束优化框架，改公式匹配算法）
- 下游模型: Qwen2.5-1.5B + LoRA
- 迭代轮数: T=5轮

---

## 实验1：迭代合成坍塌实验（#7，最核心）

### 目标
证明高频相似数据的迭代累积导致分布坍塌，QD-Synth能缓解。

### 设计
```
模型: Qwen3.5-122B (DashScope API)
种子: 20条CCSE-CS对话
每轮生成: 100条新样本
迭代轮数: T=5

两条线路:
  Greedy-Iter: 每轮选top-k by quality → 作为下轮few-shot
  QD-Iter: 每轮用QD archive选样本 → 作为下轮示例

记录指标(每轮):
  - Coverage(t): 网格覆盖率
  - Entropy(t): 存档熵
  - Self-BLEU(t): 生成样本间重复度
  - Strategy(t): 策略覆盖率 (18-strategy)
  - Vocab(t): 词汇多样性 (unique tokens / total tokens)
```

### 预期结果
| 指标 | Greedy-Iter趋势 | QD-Iter趋势 |
|------|-----------------|-------------|
| Coverage | 下降(收敛到窄区) | 稳定/上升 |
| Entropy | →0(坍塌) | 保持 |
| Self-BLEU | ↑(越来越像) | 稳定 |
| Strategy | 丢失策略 | 保持18/18 |

### 产出
- Figure: 迭代坍塌曲线 (5轮×2方法×4指标, 2×2子图)
- Table: 每轮指标数值

### 耗时
~2.5小时 (5轮 × 30min/轮)

---

## 实验2：下游微调实验（#11，证明动机成立）

### 目标
证明QD选出的数据微调的模型在下游任务上优于Greedy数据微调的模型。

### 设计
```
模型: Qwen2.5-1.5B-Instruct (下载~3GB)
微调: LoRA (r=16, alpha=32), 3 epochs, lr=2e-4
GPU: 1×A800

数据准备 (4种配置):
  - Greedy-57: 从542条中greedy quality选57条
  - QD-57: 从542条中QD-Synth选57条
  - Random-57: 随机选57条
  - Full-542: 全部数据 (上界)

任务: 客服对话生成 (agent response作为target)

评估指标:
  1. Strategy Coverage: 模型生成能否覆盖18种策略
  2. Empathy Score: LLM-judge评估共情质量 (1-5分)
  3. Conflict Balance: 生成对话在高/中/低冲突的分布
  4. Diversity: 生成样本Self-BLEU
  5. Perplexity: 困惑度 (语言流畅性)
```

### 产出
- Table: 下游微调结果 (4种数据 × 5个指标)
- Figure: 雷达图 (4种训练数据综合能力对比)

### 耗时
下载模型 ~20min + 4次微调 × ~30min + 评估 ~1h ≈ 4小时

---

## 实验3：高频坍塌可视化（#12，直观证据）

### 设计
```
从Dialogue域Greedy和QD各57条样本:

a) 策略分布热力图 (18 strategies × 2 methods)
b) 冲突级别饼图 (高/中/低 × 2 methods)
c) 语义嵌入t-SNE/UMAP (sentence-transformer编码)
d) Case Study: 3条Greedy高度相似 vs 3条QD多样化
e) 词频Top-20对比
```

### 产出
- Figure: (a)策略热力图 (b)冲突饼图 (c)t-SNE散点图
- Figure: Case Study对比

---

## 实验4：完整消融（#13）

### 当前缺失 → 需补充
| 消融项 | 变量 | 指标 |
|-------|------|------|
| 变异策略 | Targeted / Random / No-mutation | Coverage, Quality |
| 种子集大小 | |S0|∈{5,10,20,50} | Coverage at T=5 |
| k值选择 | k∈{20,40,60,80,100} | Coverage, Strategy |
| 质量评分函数 | LLM-judge / rule-based / uniform | Coverage, Quality |
| 迭代轮数 | T∈{1,2,3,5,8} | Coverage饱和曲线 |

### 产出
- Table: 变异策略消融
- Figure: k值消融 (coverage vs k)
- Figure: 迭代轮数饱和曲线

---

## 实验5：理论修复（#8 #9）

### 方案B: 约束优化框架

#### 公式修改
```
旧: max_A sum(q(x)) + λ*H(φ(A))     ← λ未在算法中体现
新: max_A Coverage(φ(A))
    subject to ∀g∈A: q(A[g]) ≥ q_threshold  ← quality gate就是约束
```

#### 理论重构
```
旧假设（不成立）:
  - q是单峰的（LLM评分不存在唯一最优）
  - q是Lipschitz连续的（LLM评分是离散有噪声的）

新框架（更现实）:
  - 假设1: q在descriptor space上有有限个局部最优 (比单峰弱)
  - 假设2: q在每个grid cell内的方差有界 σ²_cell ≤ σ²_max
  - 针对实际top-k greedy证明:
    Claim 1': "对任何top-k选择, 存在行为区域B使得B中被选样本数为0"
    Claim 2': "QD archive保证每个非空cell至少1个质量≥q_threshold的样本"
```

---

## 执行路线图

```
Phase 1 (Day 1-2): 理论修复 + 可视化（不需等实验）
  → #8 修复公式-算法脱节 (改论文LaTeX)
  → #12 高频坍塌可视化 (从已有数据画图)
  → #9 重写理论分析

Phase 2 (Day 2-4): 核心实验
  → #7 迭代合成实验 (API调用, ~2.5h)
  → #11 下游微调实验 (下载模型+微调+评估, ~4h)
  → #13 消融实验 (部分可并行)

Phase 3 (Day 4-5): 补充实验 + 论文重写
  → #10 加强基线对比
  → #15 相关工作完善
  → 全面重写论文整合新数据
```

---

## 文件位置
- 论文: /mnt/data2/zcz/neurIps-emnlp/neurips/main.tex
- 实验数据: /mnt/data2/zcz/neurIps-emnlp/neurips/results/
- 实验脚本: /mnt/data2/zcz/neurIps-emnlp/neurips/scripts/ (待创建)
- 原始数据: /mnt/data2/zcz/neurIps-emnlp/data/raw/all_dialogues_final.json (581条)
