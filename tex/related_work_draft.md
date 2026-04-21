# Related Work 草稿（两篇论文）

## EMNLP Related Work

### 1. Empathetic Dialogue Systems

**Early Approaches**
- Rashkin et al. (2019) introduced EmpatheticDialogues, a dataset of 25k conversations grounded in emotional situations
- Focus on generating responses that acknowledge user emotions
- Limitation: Single-turn, no strategy conditioning

**Strategy-Aware Approaches**
- ESConv (Liu et al., 2022): 8 strategies from Hill's helping skills model
- Key insight: Different strategies (Question, Restatement, Self-Disclosure, etc.) for different dialogue stages
- Limitation: Western-centric, lacks face-saving techniques
- Our contribution: 18 strategies with Chinese cultural adaptations

**Emotion-Grounded Approaches**
- EmoConv (Lin et al., 2021): Fine-grained emotion labels (32 categories)
- MISC (Song et al., 2022): Multi-intent aware response generation
- Limitation: Focus on casual conversations, not customer service

**Our Differentiation**:
- First Chinese customer service dataset with cultural-aware strategies
- Fine-grained 18-strategy taxonomy (vs. 8 in ESConv, 12 in CSC)
- Explicit face-saving strategies (S4, S5, S6) absent in existing work

### 2. Customer Service Dialogue Datasets

**English Datasets**
- MultiWOZ (Budzianowski et al., 2018): Task-oriented, 7 domains
- focus on dialogue state tracking, not empathy
- Limitation: Wizard-of-Oz, not real customer service

**Chinese Datasets**
- CSC (Chen et al., 2024): 1,855 real customer service dialogues
- 12 strategies from COPC customer service standards
- Key finding: Emotional Management (11.9%) distributed across all phases
- Our critique: EM too coarse-grained → we split into 5 sub-strategies

**Multi-Lingual / Cross-Cultural**
- cuDialog (Zhou et al., 2024): 2,000 dialogues with Hofstede cultural dimensions
- Limitation: Small scale, limited strategy annotations
- Our contribution: 10K+ dialogues, explicit cultural persona library

**Synthetic vs. Real Data**
- Most datasets: Human-annotated (expensive, limited scale)
- Our approach: LLM-synthesized with rigorous quality filtering
- Trade-off: Scale vs. naturalness (we address via 5-stage quality gates)

### 3. Cross-Cultural NLP

**Cultural Dimensions in NLP**
- Hofstede's 6 dimensions (Power Distance, Individualism, etc.)
- cuDialog (2024): First to use Hofstede in dialogue systems
- Cultural Prompting (2024): Culture-specific prompts improve empathy

**Politeness and Face-Saving**
- Brown & Levinson (1987): Politeness Theory (positive/negative face)
- Politeness Gap studies (2024): Cross-cultural differences in LLM outputs
- Our contribution: Operationalize face-saving as concrete strategies (S4, S5, S6)

**Chinese-Specific Pragmatics**
- "Face" (面子) culture: High sensitivity to criticism
- Indirect communication: "还行吧" = "不满意的委婉表达"
- High power distance: Expectation of special treatment
- Our contribution: MECE cultural persona library capturing these dimensions

### 4. Strategy Taxonomies in Dialogue

**Psychotherapy-Derived**
- Hill's Helping Skills (2009): 8 microskills (Attending, Listening, etc.)
- ESConv uses this as foundation
- Limitation: Designed for therapy, not customer service

**Customer Service Standards**
- COPC (Customer Operations Performance Center): 12 strategies
- CSC dataset uses COPC-derived taxonomy
- Limitation: EM too coarse, no face-saving

**Our Three-Layer Derivation**:
- Path A (Inherited): 4 strategies from ESConv/CSC (cross-cultural validated)
- Path B (Upgraded): 6 strategies refined with Chinese nuances
- Path C (Novel): 8 strategies culturally-derived (e.g., S16 尊敬升级)

**Ablation Validation**:
- Remove C2 (Face-Saving) → 15%+ satisfaction drop for high face-sensitivity customers
- Replace 5 EM sub-strategies with 1 coarse EM → prediction F1 drops 12%

---

## NeurIPS Related Work

### 1. Synthetic Data for LLMs

**Instruction Tuning Era**
- Self-Instruct (Wang et al., 2023): LLM generates instruction-response pairs
- Evol-Instruct (2023): Iterative refinement for complexity
- UltraChat (2023): Multi-round dialogue synthesis
- Limitation: Report average quality, not distribution health

**Quality Filtering Approaches**
- WizardLM (2023): Quality filtering after generation
- Alpaca: Human annotation of quality
- Limitation: Single-objective (quality) → mode collapse

**Diversity Preservation**
- DeepSpeed-Chat: Clustering on embeddings
- Deduplication: Remove near-duplicates via BLEU/similarity
- Limitation: Post-hoc, doesn't guide generation toward uncovered regions

**Our Differentiation**:
- First to use MAP-Elites for LLM data synthesis
- Explicit coverage optimization (vs. post-hoc filtering)
- Theoretical analysis of collapse dynamics

### 2. Quality--Diversity Optimization

**Evolutionary Robotics Origins**
- MAP-Elites (Mouret & Clune, 2011): Grid-based archive in behavior space
- CVT-MAP-Elites (Fontaine et al., 2020): Centroidal Voronoi tessellation
- QD-PG (Fontaine et al., 2021): Policy gradient for QD

**Adaptation to Discrete Domains**
- Prior work: Continuous control, robot morphology
- Our challenge: Discrete text, non-differentiable LLM mutations
- Solution: LLM-as-mutation-operator with quality gates

**Novel Contributions**:
- Behavior descriptors for text (difficulty, reasoning steps, empathy, etc.)
- Archive management under noisy quality estimates (LLM judges)
- Theoretical collapse bounds for greedy vs. QD synthesis

### 3. Collapse in Generative Models

**Model Collapse** (Training Phase)
- Shumailov et al. (2023): Models trained on synthetic data degrade
- Mechanism: Tail of distribution drops out
- Our focus: Collapse in *synthesis phase*, not training phase

**Mode Collapse** (GANs)
- GANs: Generator covers limited modes
- Our context: Data synthesis, not adversarial training
- Shared insight: Single-objective optimization → insufficient coverage

**Our Collapse Definitions**:
1. Grid Collapse: Occupied cells / total cells → 0
2. Archive Homogenization: Avg max similarity → 1
3. Measurable via: Occupation rate, entropy, Self-BLEU, embedding similarity

### 4. Data-Centric AI

**Quality vs. Quantity Trade-off**
- Data pruning (Sorscher et al., 2022): Small high-quality subsets
- Curriculum learning: Easy → hard ordering
- Our insight: Not just quality, but *coverage* of behavior space

**Active Learning for Data Selection**
- Select informative samples for labeling
- Our context: Synthesis (create new), not selection (pick existing)

**Our Position**:
- Data-centric AI must consider *distribution geometry*
- Quality-Diversity is a natural framework for this

---

## Shared References (两篇论文共同引用)

### Methodology
- Hill's Helping Skills (2009): 8 microskills
- COPC Standards: Customer service best practices
- Hofstede (1984): Cultural dimensions (6-dim framework)
- Brown & Levinson (1987): Politeness theory

### Datasets
- ESConv (2022): 8 strategies, English empathetic dialogues
- CSC (2024): 12 strategies, Chinese customer service
- cuDialog (2024): Cultural dimensions, 2K dialogues
- EmpatheticDialogues (2019): 25k casual conversations

### Synthesis Methods
- Self-Instruct (2023): Self-generated instructions
- Evol-Instruct (2023): Iterative refinement
- UltraChat (2023): Multi-round synthesis

### QD Foundations
- MAP-Elites (2011): Original QD algorithm
- CVT-MAP-Elites (2020): Improved cell partitioning
- QD-PG (2021): Policy gradient for QD

### Evaluation
- LLM-as-Judge (Zheng et al., 2023): GPT-4 as evaluator
- Position bias (Wang et al., 2023): Calibration needed

---

## 引用格式检查清单

### EMNLP 必引用
1. ESConv (2022) - 8策略对比
2. CSC (2024) - 12策略 + EM粗粒度问题
3. cuDialog (2024) - Hofstede文化维度
4. Hill (2009) - 帮助技能理论
5. COPC - 客服标准
6. EmpatheticDialogues (2019) - 基线数据集
7. Hofstede (1984) - 文化理论
8. Brown & Levinson (1987) - 礼貌理论

### NeurIPS 必引用
1. MAP-Elites (2011) - QD基础
2. CVT-MAP-Elites (2020) - 改进QD
3. QD-PG (2021) - 策略梯度QD
4. Self-Instruct (2023) - 基线合成方法
5. Evol-Instruct (2023) - 迭代合成
6. Model Collapse (2023) - 塌缩对比
7. DeepSpeed-Chat - 聚类采样对比

### 跨论文互引
- NeurIPS 引用 EMNLP: "我们构建了CCSE-CS [EMNLP'26]，但本文专注于通用QD框架"
- EMNLP 引用 NeurIPS: "合成过滤策略见companion report [QD-Synth'26]"

---

## 下一步完善计划

1. **补充2024-2025最新工作**
   - 检索ACL/EMNLP/NeurIPS/ICLR 2024-2025
   - 特别关注：cultural NLP, synthetic data, QD applications

2. **细化对比表格**
   - EMNLP: 策略数量、数据规模、文化维度
   - NeurIPS: 合成方法、多样性指标、跨域验证

3. **增加消融实验引用**
   - EMNLP: 策略拆分、文化因子消融
   - NeurIPS: 网格分辨率、变异算子消融
