"""
隐私脱敏过滤器
处理生成数据中的个人隐私信息：手机号、身份证号、银行卡号、姓名、地址等
"""

import re
import json
import copy
from pathlib import Path


# 隐私模式匹配规则
PRIVACY_PATTERNS = [
    # 手机号（中国大陆）
    (r'1[3-9]\d{9}', '[PHONE]'),
    # 身份证号
    (r'\d{17}[\dXx]', '[ID_CARD]'),
    # 银行卡号（13-19位连续数字）
    (r'(?<!\d)\d{13,19}(?!\d)', '[BANK_CARD]'),
    # 邮箱
    (r'[\w.-]+@[\w.-]+\.\w+', '[EMAIL]'),
    # 具体地址（含省市区的地址描述）
    (r'[\u4e00-\u9fff]+省[\u4e00-\u9fff]+市[\u4e00-\u9fff]+区[\u4e00-\u9fff]+路?\d*号?',
     '[ADDRESS]'),
    # 订单号（纯数字+尾号格式）
    (r'订单[尾号]?\s*(?:号\s*)?(?:：|:)?\s*\d{4,}', '[ORDER_ID]'),
    # 工号
    (r'工号[是]?\s*\d{3,}', '[AGENT_ID]'),
]

# 替换规则（基于语义上下文的替换）
CONTEXT_REPLACEMENTS = [
    # 姓名脱敏：王先生 → [NAME]先生
    (r'([\u4e00-\u9fff])先生', '[NAME]先生'),
    (r'([\u4e00-\u9fff])女士', '[NAME]女士'),
    (r'([\u4e00-\u9fff]{2,3})(?=，|。|你好|您好)', '[NAME]'),
    # 身份证后四位提示
    (r'身份证[号]?[（(]?后四位[)）]?\s*[：:]*\s*\d{4}', '身份证后四位[****]'),
    (r'身份证号[是]?\s*[：:]*\s*[A-Za-z]*\d{4}', '身份证号[****]'),
    (r'身份证号后四位\s*[\dXx]{4}', '身份证号后四位[****]'),
    # 验证码
    (r'验证码[是]?\s*\d{4,6}', '验证码[****]'),
    # 具体金额（保留但标记为示例）
    (r'(\d{3,})\s*元', r'[AMT]元'),
    # 具体日期脱敏（保留相对时间）
    (r'\d{4}年\d{1,2}月\d{1,2}日', '[DATE]'),
    (r'\d{1,2}月\d{1,2}日', '[DATE]'),
]


def redact_text(text):
    """对单条文本进行隐私脱敏"""
    if not text or not isinstance(text, str):
        return text

    result = text

    # 1. 先做上下文替换
    for pattern, replacement in CONTEXT_REPLACEMENTS:
        result = re.sub(pattern, replacement, result)

    # 2. 再做通用模式匹配
    for pattern, replacement in PRIVACY_PATTERNS:
        result = re.sub(pattern, replacement, result)

    return result


def redact_dialogue(dialogue_data):
    """对一条完整对话进行隐私脱敏"""
    data = copy.deepcopy(dialogue_data)

    if "dialogue" not in data:
        return data

    for turn in data["dialogue"]:
        if "content" in turn:
            turn["content"] = redact_text(turn["content"])

        # 脱敏strategy_descriptions中的内容
        if "strategy_descriptions" in turn:
            turn["strategy_descriptions"] = [
                redact_text(desc) for desc in turn["strategy_descriptions"]
            ]

        # 脱敏emotion_response
        if "emotion_response" in turn:
            turn["emotion_response"] = redact_text(turn["emotion_response"])

    # 脱敏dialogue_summary
    if "dialogue_summary" in data:
        data["dialogue_summary"] = redact_text(data["dialogue_summary"])

    # 脱敏resolution
    if "resolution" in data:
        data["resolution"] = redact_text(data["resolution"])

    return data


def redact_batch_file(input_file, output_file=None):
    """对整个批处理文件进行脱敏"""
    with open(input_file, "r", encoding="utf-8") as f:
        batch_data = json.load(f)

    redacted_dialogues = []
    for dialogue in batch_data.get("dialogues", []):
        redacted = redact_dialogue(dialogue)
        redacted_dialogues.append(redacted)

    batch_data["dialogues"] = redacted_dialogues
    batch_data["metadata"]["privacy_redacted"] = True

    if output_file is None:
        input_path = Path(input_file)
        output_file = str(input_path.parent / f"{input_path.stem}_redacted{input_path.suffix}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(batch_data, f, ensure_ascii=False, indent=2)

    print(f"隐私脱敏完成: {len(redacted_dialogues)} 条对话")
    print(f"输出: {output_file}")
    return output_file


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        redact_batch_file(sys.argv[1])
    else:
        # 默认处理最新的raw文件
        raw_dir = Path(__file__).parent.parent / "data" / "raw"
        files = sorted(raw_dir.glob("ccse_batch_*.json"))
        if files:
            redact_batch_file(str(files[-1]))
        else:
            print("未找到待处理的文件")
