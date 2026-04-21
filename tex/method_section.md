# Method Section 详细草稿

## EMNLP: CCSE-CS Method

### 3.1 Problem Setup

**任务定义**：
中文客服共情对话生成，输入为用户查询 $u$，输出为客服回复 $a$，同时预测使用的客服策略 $s \in \{S_1, \ldots, S_{18}\}$。

**关键挑战**：
1. **文化敏感性**：相同策略在中英文语境下效果不同
   - 例：S2 (情感映射) - 中文需要"听话听音"（间接情绪识别）
2. **策略粒度**：粗粒度策略（如EM）无法指导细粒度生成
3. **质量-多样性权衡**：合成数据需要同时保证质量和策略覆盖

### 3.2 Three-Stage Synthesis Pipeline

#### Stage A: Seed Scenario Generation

**输入**：
- 领域 $d \in \mathcal{D} = \{$电商, 银行, 电信, 医疗$\}$
- 场景 $s_d$（领域相关，如"物流延迟"、"账单异议"）
- 冲突强度 $\kappa \in \{$低, 中, 高$\}$

**输出**：对话骨架 $S = (d, s_d, \kappa, P, T, \pi)$
- $P$: 用户画像（情绪、潜在需求、面子敏感度、沟通风格）
- $T$: 对话轮次计划（4-8轮）
- $\pi_d$: 领域政策约束

**Prompt设计**：
```
你是专业的客服对话场景设计专家。
请为{domain}设计对话骨架，冲突强度{conflict_level}。
要求：
1. 策略从S1-S18中选择
2. 高冲突场景必须包含S8(降温化解)
3. 所有个人信息必须虚构（张三/李四/138xxxx0001）
```

**关键约束**：
- 策略预分配：根据场景特征预先分配策略路径
  - 例：高冲突 → S2 → S7 → S8 → S10
- 虚构信息强制：在prompt中明确要求虚构格式

#### Stage B: Strategy-Aware Dialogue Expansion

**输入**：
- 骨架 $S$
- 文化因子 $c =$(关系取向, 面子维护, 委婉度)
- 策略路径 $s \subset \{S_1, \ldots, S_{18}\}$

**输出**：完整对话 $D = \{(u_1, a_1), \ldots, (u_T, a_T)\}$

**Prompt设计**：
```
你是资深的中文{domain}客服对话编写专家。

## 场景信息
- 领域：{domain}
- 冲突强度：{conflict_level}
- 客户画像：{user_profile}

## 文化因子约束
- 关系取向：{relationship_orientation}
- 面子维护：{face_sensitivity}
- 委婉度：{euphemism_level}

## 必须使用的策略
{strategy_reference}

## 对话骨架
{dialogue_skeleton}

要求：
1. 严格按照骨架展开
2. 每句agent回复必须体现标注的策略
3. 不能越权承诺（"保证一定"、"100%"）
4. 不能操纵情感（"你应该感到"、"后果严重"）
5. 所有个人信息虚构（张三/138xxxx0001）
```

**Few-Shot示例**：
```
user: "我上周买的衣服还没到，订单号JD20240315001，叫张三。"
agent: "张三您好，我帮您查一下订单JD20240315001的情况..."
```

#### Stage C: Multi-Dimensional Quality Filtering

**5重质量门**：

1. **PolicyGuard**（越权承诺检测）：
   - 关键词：`["保证一定", "绝对没问题", "100%", "肯定会", "我承诺"]`
   - 规则：如包含 → 拒绝

2. **EmpathySanity**（情感操纵检测）：
   - 关键词：`["你应该感到", "你不觉得", "别人都", "你再不", "后果会很严重"]`
   - 规则：如包含 → 拒绝

3. **CoverageCheck**（策略覆盖检查）：
   - 规则：$\ge$ 2种策略
   - 规则：每轮agent必须有策略标注

4. **FaceCheck**（面子检查）：
   - 规则：高冲突场景必须包含S8（降温化解）
   - 规则：不能有直接指责（"您没有按说明" → 改为"系统可能没提醒"）

5. **PrivacyRedact**（隐私检查）：
   - 规则：连续11位数字且不含xxxx → 真实手机号 → 拒绝
   - 规则：连续18位数字 → 身份证号 → 拒绝

**过滤率统计**：
- 第一批200条：通过率82%
- 主要拒绝原因：PolicyGuard (8%), CoverageCheck (6%), PrivacyRedact (4%)

### 3.3 Cultural Persona Library

**四维MECE文化因子**：

| 维度 | 取值 | 对生成的影响 | 示例 |
|------|------|-------------|------|
| 关系取向 | 正式尊称/亲切随和/专业礼貌 | 敬语层级、称呼方式 | "尊敬的XXX会员" vs "亲" |
| 面子维护 | 高/中/低 | S5/S6策略使用频率 | 高 → 更多肯定价值/避免指责 |
| 委婉度 | 高/中/低 | 拒绝/坏消息包装程度 | 高 → "可能需要一些时间" vs "不能" |
| 冲突强度 | 低/中/高 | 情绪曲线、策略选择 | 高 → S8降温 + S9认同 |

**采样策略**：
- 每条对话独立采样4个维度
- 确保覆盖所有组合（$3 \times 3 \times 3 \times 3 = 81$种）
- 在大规模生成时分层采样保证均衡

**理论基础**：
- Hofstede权力距离（中国80分 vs 西方40分）→ 高面子敏感
- 集体主义（中国20分）→ 重视关系/面子
- 长期取向（中国87分）→ 重视长期关系维护

### 3.4 6×18 Strategy Taxonomy

**推导路径总结**：

```
来源                    路径A继承    路径B升级    路径C新增
--------------------------------------------------------
ESConv (8策略)           S1          S2, S7      S4, S8
CSC (12策略)             S10, S14, S15  S3, S9, S11  S5, S6, S12, S13
文化/场景驱动            -           -           S16, S17, S18
```

**关键拆分：EM → 5个子策略**

| 原EM | 拆分为 | 依据 |
|------|--------|------|
| Emotional Management | S2 (情感映射) | 识别情绪 |
| | S4 (委婉致歉) | 维护面子 |
| | S7 (共情表达) | 表达共情 |
| | S8 (降温化解) | 化解冲突 |
| | S9 (价值认同) | 认同立场 |

**证据**：
- CSC数据：EM占11.9%且均匀分布 → 太粗
- TransESC：策略间平滑转移比单一策略重要
- MISC：细粒度情感理解效果更好

### 3.5 Data Format

```json
{
  "dialogue": [
    {
      "turn": 1,
      "speaker": "user|agent",
      "content": "对话内容（已脱敏）",
      "emotion": "情绪标签",
      "intent": "意图",
      "strategies_used": ["S1", "S4"],
      "strategy_descriptions": ["策略描述"],
      "emotion_response": "情绪回应说明"
    }
  ],
  "quality_self_check": {
    "has_empathy": true,
    "policy_compliant": true,
    "no_overcommitment": true,
    "no_emotion_manipulation": true,
    "cultural_appropriate": true,
    "natural": true
  },
  "metadata": {
    "session_id": "...",
    "domain": "电商|银行|电信|医疗",
    "scenario": "具体场景",
    "conflict_level": "低|中|高",
    "cultural_profile": {...},
    "strategies_needed": [...],
    "model": "qwen3.5-122b-a10b"
  }
}
```

---

## NeurIPS: QD-Synth Method

### 3.1 Problem Formulation

**传统合成的问题建模**：
$$
\max_{x \in \mathcal{X}} q(x)
$$
其中$q(x)$是质量分数（LLM judge打分）。

**问题**：单目标优化导致分布塌缩
- 某些行为区域$\mathcal{B} \subset \mathcal{X}$永远不会被采样
- 样本间语义重复度高

**QD-Synth的建模**：
$$
\max_{\mathcal{A} \subset \mathcal{X}} \left[ \underbrace{\sum_{x \in \mathcal{A}} q(x)}_{\text{质量}} + \lambda \underbrace{\mathcal{H}(\phi(\mathcal{A}))}_{\text{多样性}} \right]
$$
其中$\phi(x)$是行为描述子，$\mathcal{H}$是熵。

### 3.2 Behavior Descriptors

**设计原则**：
1. **低维**（$d \in [2,4]$）：避免维度灾难
2. **可计算**：规则、小模型或LLM裁判可估计
3. **语义有意义**：每个维度对应任务的关键行为

**三域示例**：

| 域 | 描述子 $\phi(x)$ | 计算方法 |
|----|----------------|---------|
| Math | (难度, 步数, 多步) | 难度=GPT-4打分, 步数=CoT长度 |
| Code | (难度, API数, 调试) | API数=AST解析, 调试=规则 |
| Dialogue | (共情, 策略, 冲突) | 共情=(S2+S7+S8)/轮次 |

**Dialogue域详细实现**：
```python
def compute_dialogue_descriptor(dialogue):
    # 共情强度
    empathy_strategies = {"S2", "S7", "S8"}
    empathy_count = sum(1 for t in dialogue if s in empathy_strategies)
    empathy = empathy_count / len(dialogue)

    # 策略类型（6类one-hot的主类）
    category_counts = {cat: 0 for cat in CATEGORIES}
    for turn in dialogue:
        for s in turn.strategies:
            cat = get_category(s)
            category_counts[cat] += 1
    main_category = argmax(category_counts) / 5.0  # 归一化

    # 冲突强度
    conflict = {"低": 0.25, "中": 0.5, "高": 0.75}[dialogue.conflict_level]

    return (empathy, main_category, conflict)
```

### 3.3 MAP-Elites for LLM Synthesis

**算法伪代码**：

```
Algorithm: QD-Synth
Input: 种子集S_0, 迭代次数T, 描述子φ, 质量q, 网格分辨率r
Output: 档案库A_T

1: A_0 ← InitializeArchive(S_0, φ, q)
2: for t = 1 to T do
3:     x_parent ← SampleFromArchive(A_{t-1})
4:     x' ← Mutate(x_parent) via LLM
5:     b ← φ(x')
6:     q_val ← q(x')
7:     g ← Discretize(b, r)
8:     if g not in A_{t-1} or q_val > q(A_{t-1}[g]) then
9:         A_t[g] ← (x', q_val)  // MAP-Elites更新
10:    else
11:        A_t ← A_{t-1}
12: end for
13: return FlattenArchive(A_T)
```

**关键组件**：

1. **变异算子（Mutation Operators）**：
   - Math域："Make this problem harder/easier"
   - Code域："Refactor using different APIs"
   - Dialogue域："Increase conflict intensity"

2. **网格离散化**：
   - 输入：$\phi(x) \in [0,1]^d$
   - 输出：$g = (\lfloor \phi_1 \cdot r \rfloor, \ldots, \lfloor \phi_d \cdot r \rfloor)$
   - 默认：$r=10$（每维10个区间）

3. **精英替换**：
   - 条件1：新格（$g \notin \mathcal{A}$）→ 直接加入
   - 条件2：已存在格但质量更高 → 替换
   - 否则 → 拒绝

### 3.4 Theoretical Analysis

**定义1（网格塌缩）**：
$$
\lim_{t \to \infty} \frac{|\{g \in \mathcal{G} : \exists x, \phi(x) \in g\}|}{|\mathcal{G}|} = 0
$$

**定义2（精英同质化）**：
$$
\lim_{t \to \infty} \mathbb{E}_{x_i \in \mathcal{A}} \left[ \max_{j \neq i} \text{sim}(x_i, x_j) \right] = 1
$$

**命题（示意）**：
> 若候选生成器在固定格上单峰且贪心只接受全局$q$提升，则存在行为区域永不被访问。

**证明草图**：
1. 假设质量函数$q$在行为空间上单峰
2. 贪心算法收敛到全局最优$x^*$
3. 对于远离$x^*$的行为区域$B$，所有$x \in B$满足$q(x) < q(x^*)$
4. 因此$B$永远不会被采样 → 覆盖空集

**QD优势**：
- 每格保留局部最优 → 下界覆盖
- 跨格多样性 → 避免同质化

### 3.5 Complexity Analysis

**时间复杂度**：
- 单次迭代：$O(T_{\text{mutate}} + T_{\phi} + T_q)$
  - $T_{\text{mutate}}$: LLM API调用（~1-10秒）
  - $T_{\phi}$: 描述子计算（~0.1-1秒）
  - $T_q$: 质量评估（~1-10秒，LLM judge）
- 总迭代：$O(T \cdot (T_{\text{mutate}} + T_{\phi} + T_q))$

**空间复杂度**：
- 档案库：$O(|\mathcal{G}| \cdot \text{size}(x))$
- 网格大小：$r^d$（$r=10, d=3$ → 1000格）

**超参数敏感性**：
- 网格分辨率$r$：太粗→低多样性，太细→空格震荡
- 变异强度：太弱→局部探索，太强→低质量
- 裁判噪声：$\sigma_q$影响替换稳定性

---

## 实验设计（两篇论文）

### EMNLP 实验设计

**基线**：
1. ESConv-finetuned: 在ESConv上微调
2. CSC-finetuned: 在CSC CSConv上微调
3. Zero-shot GPT-4: 直接提示

**模型**：
- Qwen-7B, ChatGLM-6B（中文优化）
- GPT-3.5（对比）

**评测协议**：
1. **人工评测**（500条）：
   - 4维评分（1-5分）
   - 3个标注员，ICC一致性
2. **LLM-as-Judge**（全量）：
   - Judge-A (偏共情): Emp-App, Nat
   - Judge-B (偏合规): Pol-Comp, Cul-Fit
   - 在Gold子集标定position bias

**消融实验**：
1. 去掉C2(面子维护) → 高面子客户满意度↓?
2. 用CSC原版EM替代5个子策略 → F1↓?
3. 去掉文化因子 → Cul-Fit↓?

**主结果表设计**：
```
| Model | Emp-App | Pol-Comp | Cul-Fit | Nat | Overall |
|-------|---------|----------|---------|-----|---------|
| ESConv | 3.2 | 3.5 | 2.8 | 3.0 | 3.13 |
| CSC | 3.5 | 4.0 | 3.2 | 3.3 | 3.50 |
| CCSE-CS (Ours) | 4.2 | 4.1 | 4.3 | 4.0 | 4.15 |
```

### NeurIPS 实验设计

**基线**：
1. Greedy-Quality: 保留高q样本
2. Random-Subset: 随机采样
3. Cluster-Sampling: K-means后采样
4. Deduplication: 去重后保留

**任务**：
1. Math: GSM8K风格，5K样本
2. Code: HumanEval风格，3K样本
3. Dialogue: 共情对话，3K样本（含小规模CCSE）

**指标**：
1. **下游**：
   - Math: GSM8K/MATH accuracy
   - Code: HumanEval/MBPP pass@1
   - Dialogue: Empathy任务评分
2. **塌缩**：
   - 网格占用率
   - 档案熵
   - Self-BLEU
   - 嵌入相似度

**消融实验**：
1. 去掉多样性（退化为贪心）
2. 改变网格分辨率$r$
3. 改变描述子维度$d$

**主结果表设计**：
```
| Method | Math Acc | Code Pass@1 | Dialogue Emp | Coverage | Entropy | Self-BLEU |
|--------|----------|-------------|--------------|----------|---------|-----------|
| Greedy | 42.3% | 28.5% | 3.2 | 15% | 1.2 | 0.42 |
| Cluster | 45.1% | 30.2% | 3.5 | 38% | 2.1 | 0.35 |
| QD-Synth | 58.0% | 41.3% | 4.1 | 72% | 3.8 | 0.21 |
```

---

## 下一步完善

1. **补充算法框图**：
   - 三阶段管线流程图
   - MAP-Elites更新规则可视化

2. **补充案例**：
   - 完整对话示例（带策略标注）
   - 过滤前后对比

3. **补充统计表**：
   - 策略分布统计
   - 文化因子分布
   - 过滤原因分布

4. **交叉引用**：
   - Method ↔ Experiment
   - Theory ↔ Results
