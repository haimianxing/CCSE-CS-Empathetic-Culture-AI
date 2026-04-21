# CCSE-SynthCollapse: Cultural Customer Service Empathy & Synthesis Collapse

Two complementary research projects on **LLM-based synthetic data quality** and **culturally-aware dialogue systems**.

**Author:** Chengzhe Zhang (Beihang University)

---

## Project 1: Synthesis Collapse (NeurIPS 2026)

**Paper:** *Synthesis Collapse: How Greedy Selection Narrows LLM Data Synthesis*

### Key Findings

1. **Collapse is real, persistent, and conditionally invisible.** Greedy selection retains only 25–31 cells across 4 rounds (Code domain), while cell-aware selection maintains 62–68 cells — a **2.4x coverage gap** (Wilcoxon p=0.004).

2. **The mechanism is per-cell deduplication, not quality–diversity optimization.** A cell-deduplicated greedy baseline achieves identical downstream performance to full MAP-Elites (pass@1 68.1%, p=0.98).

3. **When diversity matters, and when it does not.** At scale (4,563-solution pool, k=500), cell-aware selection achieves **+13.4pp higher HumanEval pass@1** (30.5% vs 17.1%).

### Core Algorithm: MAP-Elites for Synthetic Data (QD-Synth)

```python
from qd_synth import QDSynth, QualityFunction, BehaviorDescriptor

# Define quality and behavior dimensions
qd = QDSynth(
    quality_fn=QualityFunction(),     # LLM-as-judge quality scoring
    behavior_desc=BehaviorDescriptor(  # 3D behavioral characterization
        dims=["empathy", "strategy", "conflict"]
    ),
    grid_resolution=5,
    max_iterations=10
)

# Run synthesis
archive = qd.synthesize(seed_data, llm_client)
```

### Project Structure

```
neurips/
├── main.tex              # NeurIPS 2026 paper (1129 lines)
├── references.bib        # Bibliography
├── neurips_2026.sty      # Style file
├── figures/              # 25+ figures (PDF)
├── generate_figures.py   # Figure generation scripts
└── EXPERIMENT_DESIGN.md  # Experiment design document
```

---

## Project 2: CCSE-CS (EMNLP 2026)

**Paper:** *CCSE-CS: A Culturally-Aware Empathetic Dialogue Dataset for Chinese Customer Service*

### Key Contributions

1. **9,478 dialogues, 76,847 turns** across 4 domains (e-commerce, banking, telecom, healthcare)
2. **4-dimensional cultural framework** (relationship orientation, face sensitivity, euphemism level, conflict intensity) — dominant quality contributor (p<0.001)
3. **6-category, 18-substrategy taxonomy** with domain-specific strategic diversity
4. **Five-fold quality filter** (44% adversarial catch rate, 0% false positives)
5. **4-dimensional LLM-as-judge protocol** (r=0.969 with certified trainers)

### Quick Start

```python
from configs.strategy_ontology import STRATEGY_TAXONOMY
from configs.strategy_trigger_matrix import TRIGGER_MATRIX

# 18 substrategies across 6 categories
for category, strategies in STRATEGY_TAXONOMY.items():
    print(f"{category}: {strategies}")

# Generate dialogues
python scripts/generate_dialogues.py --num-dialogues 100 --domains all

# Evaluate with LLM-as-judge
python scripts/llm_judge.py --input data/dialogues.json --dimensions all
```

### Project Structure

```
configs/
├── strategy_ontology.py        # 6-category 18-substrategy taxonomy
└── strategy_trigger_matrix.py  # Strategy-trigger mapping

scripts/
├── generate_dialogues.py       # Dialogue generation
├── generate_10k_safe.py        # Large-scale generation
├── privacy_filter.py           # PII redaction
├── llm_judge.py                # LLM-as-judge evaluation
├── analyze_coverage.py         # Strategy coverage analysis
├── baseline_eval.py            # Baseline comparisons
├── qd_synth_experiments.py     # QD-Synth experiments
└── calculate_statistics.py     # Statistical analysis

tex/emnlp/
├── main.tex                    # EMNLP 2026 paper (1032 lines)
└── references.bib              # Bibliography
```

---

## Shared Components

| File | Description |
|------|-------------|
| `qd_synth.py` | MAP-Elites QD synthesis framework (405 lines) |
| `llm_judge.py` | Multi-dimensional LLM-as-judge evaluator |
| `configs/` | Strategy taxonomy and trigger matrices |
| `prompts/` | IAA annotation prompts |

---

## Citation

```bibtex
@inproceedings{zhang2026ccse,
  title={CCSE-CS: A Culturally-Aware Empathetic Dialogue Dataset for Chinese Customer Service},
  author={Zhang, Chengzhe},
  booktitle={Proceedings of EMNLP},
  year={2026}
}

@inproceedings{zhang2026collapse,
  title={Synthesis Collapse: How Greedy Selection Narrows LLM Data Synthesis},
  author={Zhang, Chengzhe},
  booktitle={Proceedings of NeurIPS},
  year={2026}
}
```

## License

MIT License
