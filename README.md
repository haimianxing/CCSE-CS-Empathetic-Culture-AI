# CCSE-CS: Culturally-Aware Empathetic Dialogue Dataset for Chinese Customer Service

A large-scale Chinese customer service dialogue dataset with culturally-aware empathy strategies, targeting **EMNLP 2026**.

**Author:** Chengzhe Zhang (Beihang University)

---

## Key Contributions

1. **9,478 dialogues, 76,847 turns** across 4 domains (e-commerce, banking, telecommunications, healthcare)
2. **4-dimensional cultural framework** (relationship orientation, face sensitivity, euphemism level, conflict intensity) — dominant quality contributor (p<0.001; +1.06 overall gain)
3. **6-category, 18-substrategy taxonomy** with domain-specific strategic diversity
4. **Five-fold quality filter** validated as safety mechanism (44% adversarial catch rate, 0% false positives)
5. **4-dimensional LLM-as-judge evaluation protocol** (r=0.969 with certified customer service trainers)

## Quick Start

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

## Project Structure

```
configs/
├── strategy_ontology.py           # 6-category 18-substrategy taxonomy
└── strategy_trigger_matrix.py     # Strategy-trigger mapping

scripts/
├── generate_dialogues.py          # Dialogue generation
├── generate_10k_safe.py           # Large-scale batch generation
├── generate_batch_200.py          # Medium-scale generation
├── privacy_filter.py              # PII redaction
├── llm_judge.py                   # LLM-as-judge evaluation
├── quick_eval.py                  # Quick evaluation
├── analyze_coverage.py            # Strategy coverage analysis
├── calculate_statistics.py        # Statistical analysis
├── priority4_llm_annotation_system.py   # LLM annotation system
├── priority5_llm_judge_validation.py    # LLM judge validation
└── priority6_statistical_analysis.py    # Statistical validation

tex/emnlp/
├── main.tex                       # EMNLP 2026 paper
├── main_submission.tex            # Submission version
├── references.bib                 # Bibliography
├── acl.sty / acl_natbib.bst       # ACL style files
└── figures/                       # Paper figures

prompts/
└── llm_iaa_annotation_prompt.md   # IAA annotation prompt

llm_judge.py                       # Multi-dimensional LLM evaluator
```

## 18 Empathetic Strategies

| Category | Strategies |
|----------|-----------|
| **Emotion Recognition** | Reflective Listening, Emotion Validation |
| **Emotional Support** | Reassurance, Empathic Concern, Encouragement |
| **Practical Solutions** | Direct Solution, Alternative Options, Step-by-step Guidance |
| **Face Preservation** | Indirect Correction, Selective Honesty, Compromise |
| **Cultural Sensitivity** | Honorific Language, Collective Framing, Proverb/Analogy |
| **Conflict Resolution** | De-escalation, Boundary Setting, Constructive Redirection |

## Setup

```bash
pip install openai transformers datasets

# Set API key
export DASHSCOPE_API_KEY="your-api-key"

# Generate dataset
python scripts/generate_dialogues.py --num-dialogues 100 --domains all

# Run evaluation
python scripts/llm_judge.py --input data/dialogues.json
```

## Citation

```bibtex
@inproceedings{zhang2026ccse,
  title={CCSE-CS: A Culturally-Aware Empathetic Dialogue Dataset for Chinese Customer Service},
  author={Zhang, Chengzhe},
  booktitle={Proceedings of EMNLP},
  year={2026}
}
```

## License

MIT License
