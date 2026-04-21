#!/usr/bin/env python3
"""
CCSE-CS Data Scaling Experiment
Fine-tune Qwen2.5-1.5B on 100, 522, 9478 dialogues, evaluate with LLM Judge.
"""
import json
import os
import sys
import re
import time
import random
import numpy as np
import torch
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

OUTPUT_DIR = Path("/mnt/data2/zcz/neurIps-emnlp/data/experiments/scaling")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_PATH = "/mnt/data2/zcz/neurIps-emnlp/data/raw/ccse_cs_clean.json"
MODEL_PATH = "/home/zcz/.cache/modelscope/hub/Qwen/Qwen2___5-1___5B-Instruct"
API_CONFIG = {
    "model_name": "qwen3.5-122b-a10b",
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
}

# ============================================================
# 1. Data Loading & Subset Creation
# ============================================================

def load_data():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data)} dialogues")
    return data

def format_dialogue(d):
    """Format a single dialogue for training"""
    text = ""
    dialogue = d.get("dialogue", [])
    if not dialogue:
        return None

    for turn in dialogue:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role", turn.get("speaker", ""))
        content = turn.get("content", turn.get("text", ""))
        if role == "user":
            text += f"客户: {content}\n"
        elif role == "agent":
            text += f"客服: {content}\n"

    if len(text.strip()) < 50:
        return None

    meta = d.get("metadata", {})
    strategies = meta.get("strategies_needed", [])
    conflict = meta.get("conflict_intensity", "中")
    domain = meta.get("domain", "电商")

    return {
        "text": text[:1024],
        "strategy": strategies[0] if strategies else "S1",
        "conflict": conflict,
        "domain": domain,
        "quality": min(len(text) / 2000.0, 1.0)
    }

def create_subsets(samples, sizes=[100, 522, 9478]):
    """Create subsets of different sizes"""
    subsets = {}
    for size in sizes:
        actual_size = min(size, len(samples))
        # Stratified by domain
        random.shuffle(samples)
        subset = samples[:actual_size]
        subsets[f"n{size}"] = subset
        print(f"  n={actual_size}: {len(subset)} samples")
    return subsets

# ============================================================
# 2. Fine-tuning with LoRA
# ============================================================

def finetune_lora(train_data, config_name, epochs=3):
    """Fine-tune Qwen2.5-1.5B with LoRA"""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model
    from trl import SFTTrainer, SFTConfig
    from datasets import Dataset

    print(f"\n{'='*60}")
    print(f"Fine-tuning: {config_name} ({len(train_data)} samples)")
    print(f"{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0",
        trust_remote_code=True
    )

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    def format_sample(sample):
        return (
            f"<|im_start|>system\n你是专业的中文客服人员，需要用共情和策略回应客户。<|im_end|>\n"
            f"<|im_start|>user\n处理一个{sample['conflict']}冲突级别的{sample['domain']}客户问题。<|im_end|>\n"
            f"<|im_start|>assistant\n{sample['text'][:512]}<|im_end|>"
        )

    train_texts = [format_sample(s) for s in train_data]
    train_dataset = Dataset.from_dict({"text": train_texts})

    output_dir = OUTPUT_DIR / f"model_{config_name}"

    sft_config = SFTConfig(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="no",
        bf16=True,
        report_to="none",
        max_length=512,
        dataset_text_field="text",
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        processing_class=tokenizer,
    )

    t0 = time.time()
    trainer.train()
    train_time = time.time() - t0
    print(f"  Training completed in {train_time:.1f}s")

    # Save
    model.save_pretrained(output_dir / "lora")
    tokenizer.save_pretrained(output_dir / "lora")

    # Clean up
    del model, trainer
    torch.cuda.empty_cache()

    return output_dir / "lora"

# ============================================================
# 3. Generation
# ============================================================

def generate_responses(model_path, n=50):
    """Generate responses from fine-tuned model"""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    print(f"\nGenerating {n} responses from {model_path}...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, torch_dtype=torch.bfloat16, device_map="cuda:0", trust_remote_code=True
    )
    model = PeftModel.from_pretrained(base_model, model_path)
    model.eval()

    domains = ["电商", "电信", "银行", "医疗"]
    conflicts = ["低", "中", "高"]

    responses = []
    for i in range(n):
        domain = domains[i % len(domains)]
        conflict = conflicts[i % len(conflicts)]
        prompt = (
            f"<|im_start|>system\n你是专业的中文客服人员，需要用共情和策略回应客户。<|im_end|>\n"
            f"<|im_start|>user\n处理一个{conflict}冲突级别的{domain}客户投诉问题。客户非常不满意，请用合适的策略回应。<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda:0")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.85,
                top_p=0.9,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        responses.append({"response": response, "domain": domain, "conflict": conflict})

    del model, base_model
    torch.cuda.empty_cache()

    return responses

# ============================================================
# 4. LLM Judge Evaluation
# ============================================================

def call_qwen_api(messages, temperature=0.3, max_retries=2):
    import requests
    headers = {"Authorization": f"Bearer {API_CONFIG['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": API_CONFIG["model_name"],
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": 1024
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_CONFIG["url"], headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if "<think" in content:
                content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
    return None

JUDGE_PROMPT = """你是专业的客服对话评测专家。请评估以下客服回复，给出1-5分评分：

**维度**:
1. 共情适时性 (Emp-App): 共情是否及时、适度、自然
2. 自然度 (Nat): 是否流畅、无翻译腔
3. 政策合规性 (Pol-Comp): 是否遵守规则，无过度承诺
4. 文化适切性 (Cul-Fit): 委婉/面子/尊敬是否得体

**客服回复**：
{response}

**评分标准**: 1=很差, 2=差, 3=一般, 4=好, 5=很好

请严格以JSON格式输出：
{{"Emp-App": {{"score": 0}}, "Nat": {{"score": 0}}, "Pol-Comp": {{"score": 0}}, "Cul-Fit": {{"score": 0}}}}
只输出JSON。"""

def evaluate_single(response_text):
    prompt = JUDGE_PROMPT.format(response=response_text)
    result = call_qwen_api([{"role": "user", "content": prompt}])
    if result is None:
        return None
    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
        parsed = json.loads(result)
        scores = {
            "Emp-App": parsed.get("Emp-App", {}).get("score", 0),
            "Nat": parsed.get("Nat", {}).get("score", 0),
            "Pol-Comp": parsed.get("Pol-Comp", {}).get("score", 0),
            "Cul-Fit": parsed.get("Cul-Fit", {}).get("score", 0),
        }
        if all(s > 0 for s in scores.values()):
            scores["Overall"] = sum(scores.values()) / 4.0
            return scores
    except:
        pass
    return None

def evaluate_batch(responses, workers=4):
    """Evaluate all responses with LLM Judge"""
    print(f"\nEvaluating {len(responses)} responses with LLM Judge...")
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(evaluate_single, r["response"]): i for i, r in enumerate(responses)}
        for future in as_completed(futures):
            try:
                score = future.result()
                if score:
                    results.append(score)
            except:
                pass
    return results

# ============================================================
# 5. Main
# ============================================================

def main():
    print("="*60)
    print("CCSE-CS Data Scaling Experiment")
    print("="*60)

    # Load data
    raw_data = load_data()
    samples = [format_dialogue(d) for d in raw_data]
    samples = [s for s in samples if s is not None]
    print(f"Valid samples: {len(samples)}")

    # Create subsets
    subsets = create_subsets(samples, sizes=[100, 522, 9478])

    all_results = {}

    for name, data in subsets.items():
        print(f"\n{'='*60}")
        print(f"Config: {name} ({len(data)} samples)")
        print(f"{'='*60}")

        # Fine-tune
        model_path = finetune_lora(data, name, epochs=3)

        # Generate responses
        responses = generate_responses(model_path, n=50)

        # Evaluate with LLM Judge
        eval_results = evaluate_batch(responses, workers=4)

        if eval_results:
            dims = ["Emp-App", "Nat", "Pol-Comp", "Cul-Fit", "Overall"]
            stats = {}
            for dim in dims:
                scores = [r[dim] for r in eval_results if r.get(dim, 0) > 0]
                if scores:
                    mean = np.mean(scores)
                    std = np.std(scores)
                    ci = 1.96 * std / (len(scores) ** 0.5)
                    stats[dim] = {"mean": round(mean, 2), "std": round(std, 3),
                                  "ci95": [round(mean - ci, 2), round(mean + ci, 2)],
                                  "n": len(scores)}

            all_results[name] = {"n_train": len(data), "n_eval": len(eval_results), "metrics": stats}

            print(f"\nResults for {name}:")
            for dim, s in stats.items():
                print(f"  {dim}: {s['mean']:.2f} ± {s['std']:.3f} [{s['ci95'][0]:.2f}, {s['ci95'][1]:.2f}]")

        # Save checkpoint
        with open(OUTPUT_DIR / "scaling_results.json", "w") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    # Final comparison
    print(f"\n{'='*60}")
    print("SCALING COMPARISON")
    print(f"{'='*60}")
    print(f"{'Config':<10} {'Emp-App':>10} {'Nat':>10} {'Pol-Comp':>10} {'Cul-Fit':>10} {'Overall':>10}")
    print("-" * 60)
    for name in ["n100", "n522", "n9478"]:
        if name in all_results:
            m = all_results[name]["metrics"]
            print(f"{name:<10} {m.get('Emp-App',{}).get('mean',0):>10.2f} "
                  f"{m.get('Nat',{}).get('mean',0):>10.2f} "
                  f"{m.get('Pol-Comp',{}).get('mean',0):>10.2f} "
                  f"{m.get('Cul-Fit',{}).get('mean',0):>10.2f} "
                  f"{m.get('Overall',{}).get('mean',0):>10.2f}")

    print(f"\nResults saved to {OUTPUT_DIR / 'scaling_results.json'}")

if __name__ == "__main__":
    main()
