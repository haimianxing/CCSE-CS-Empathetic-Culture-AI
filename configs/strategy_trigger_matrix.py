"""
策略触发矩阵：18策略 × 场景特征映射

用于：
1. 生成时强制包含对应策略
2. 评测时检查策略-场景一致性
3. QD框架用描述子控制分布
"""

STRATEGY_TRIGGER_MATRIX = {
    # C1: 倾听确认
    "S1": {
        "trigger_conditions": {
            "turn_position": "early",  # 对话早期
            "min_exchanges": 2,  # 至少2轮交互
        },
        "required_in_all_scenarios": True,  # 所有场景都需要
        "examples": [
            "您是说在3月15日购买的商品还没收到对吗？",
            "我帮您确认一下，您反映的问题是订单金额有误，对吗？"
        ]
    },

    "S2": {
        "trigger_conditions": {
            "user_emotion": ["失望", "愤怒", "焦虑", "不满"],
            "emotion_intensity": "medium_or_high"
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "投诉", "退款", "故障", "账单异议", "服务不满"
        ],
        "examples": [
            "听起来您对这次体验感到非常失望",
            "您现在很着急，我完全理解"
        ]
    },

    "S3": {
        "trigger_conditions": {
            "intent_ambiguity": "high",  # 意图模糊
            "user_communication_style": ["委婉", "含蓄"]
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "咨询", "一般问题", "模糊诉求"
        ],
        "examples": [
            "您说的'还行吧'是不是指商品有些小问题？",
            "能否详细说明一下您遇到的具体情况？"
        ]
    },

    # C2: 面子维护
    "S4": {
        "trigger_conditions": {
            "error_type": ["agent_error", "policy_limit", "system_error"],
            "post_acknowledgment": True  # 在确认问题后
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "退款", "换货", "投诉", "延误"
        ],
        "examples": [
            "给您带来不便，我们深感抱歉",
            "这次是我们工作没做到位，让您费心了"
        ]
    },

    "S5": {
        "trigger_conditions": {
            "face_sensitivity": "high",  # 面子敏感度高
            "user_cooperation": ["等待", "配合", "理解"]
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "长时间等待", "复杂问题", "老年客户", "VIP客户"
        ],
        "examples": [
            "非常感谢您的耐心等待",
            "您的理解对我们很重要"
        ]
    },

    "S6": {
        "trigger_conditions": {
            "needs_correction": True,  # 需要纠正客户误解
            "blame_avoidance": "high"
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "操作错误", "误解政策", "信息不对称"
        ],
        "examples": [
            "系统可能没有及时提醒到您",  # 而非"您没看"
            "让我再给您详细说明一下"  # 而非"您理解错了"
        ]
    },

    # C3: 情绪安抚
    "S7": {
        "trigger_conditions": {
            "emotion_peak": True,  # 情绪高点
            "user_emotion": ["非常失望", "愤怒", "委屈"]
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "高冲突", "投诉升级", "威胁投诉"
        ],
        "examples": [
            "换作是我也会很着急的",
            "我非常理解您的心情"
        ]
    },

    "S8": {
        "trigger_conditions": {
            "conflict_level": "high",  # 高冲突
            "escalation_detected": True  # 检测到升级
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "威胁投诉", "情绪失控", "反复投诉"
        ],
        "examples": [
            "我完全理解您的心情，让我马上帮您查一下",
            "大约需要2分钟，请您稍等，我立即处理"
        ]
    },

    "S9": {
        "trigger_conditions": {
            "appeal_reasonable": True,  # 诉求合理
            "value_affirmation_needed": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "原则性问题", "公道诉求", "说法型投诉"
        ],
        "examples": [
            "您的诉求非常合理",
            "您说得对，每个消费者都值得被尊重"
        ]
    },

    # C4: 方案推进
    "S10": {
        "trigger_conditions": {
            "conversation_stage": "action",  # 解决阶段
            "has_solution": True  # 有解决方案
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "故障", "退款", "换货", "咨询"
        ],
        "examples": [
            "您可以点击'申请退款'按钮，填写原因后提交",
            "我们为您安排换货，3天内送达"
        ]
    },

    "S11": {
        "trigger_conditions": {
            "has_multiple_solutions": True,  # 有多个可行方案
            "user_autonomy_respect": "high"
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "退款换货", "补偿方案", "多种解决方案"
        ],
        "examples": [
            "您看是希望换货还是退款呢？",
            "我们有两个方案：一是补发商品，二是退款，您看哪个更合适？"
        ]
    },

    "S12": {
        "trigger_conditions": {
            "solve_time_long": True,  # 解决时间>1天
            "uncertainty_exists": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "跨部门协调", "复杂调查", "供应商对接"
        ],
        "examples": [
            "通常处理时间是1-3天，如果超时我会主动跟进",
            "我们需要和仓储部门核实，预计24小时内给您答复"
        ]
    },

    # C5: 关系修复
    "S13": {
        "trigger_conditions": {
            "scenario_type": ["complaint", "dispute"],  # 投诉/争议场景
            "dissatisfaction_high": True,
            "compensation_appropriate": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "投诉", "严重失误", "高价值客户"
        ],
        "examples": [
            "为了表示歉意，我们为您申请了20元优惠券",
            "我们为您加急处理，并赠送您积分作为补偿"
        ]
    },

    "S14": {
        "trigger_conditions": {
            "conversation_stage": "closing",  # 收尾阶段
            "solution_implemented": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "问题已解决", "服务完成", "咨询结束"
        ],
        "examples": [
            "还有其他问题需要我帮您解决吗？",
            "请您对我的服务进行评价"
        ]
    },

    "S15": {
        "trigger_conditions": {
            "conversation_stage": "final",  # 最后阶段
            "relationship_maintenance": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "所有场景（收尾）"
        ],
        "examples": [
            "后续有任何问题随时联系我们",
            "祝您生活愉快，期待下次为您服务"
        ]
    },

    # C6: 文化适配
    "S16": {
        "trigger_conditions": {
            "power_distance_high": True,
            "user_profile": ["elderly", "VIP", "formal"]  # 老年/VIP/正式
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "老年客户", "VIP客户", "正式场合"
        ],
        "examples": [
            "叔叔/阿姨您好，您放心我来帮您处理",
            "尊敬的XXX会员，感谢您的来电"
        ]
    },

    "S17": {
        "trigger_conditions": {
            "date_near_holiday": True,  # 接近节日
            "relationship_building": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "节日前后", "情感连接"
        ],
        "examples": [
            "快过年了，提前祝您新年快乐",
            "中秋节快乐，希望这个问题解决后您能好好过节"
        ]
    },

    "S18": {
        "trigger_conditions": {
            "regional_features": True,  # 有地域特征
            "context_adaptation_needed": True
        },
        "required_in_all_scenarios": False,
        "scenarios": [
            "地域明显", "方言相关", "文化差异"
        ],
        "examples": [
            "北方客户：更直接，说'我不满意'就是真的不满意",
            "南方客户：更委婉，说'还可以吧'可能已经很不满"
        ]
    }
}

# 场景-策略推荐映射
SCENARIO_STRATEGY_MAPPING = {
    "电商退款": {
        "core_strategies": ["S1", "S2", "S4", "S10"],
        "optional_strategies": ["S7", "S11", "S12", "S14", "S15"],
        "high_conflict_add": ["S8", "S9"],
        "face_sensitive_add": ["S5", "S6"]
    },
    "银行账单异议": {
        "core_strategies": ["S1", "S3", "S2"],
        "optional_strategies": ["S4", "S6", "S10", "S12"],
        "high_conflict_add": ["S8", "S9"],
        "vip_add": ["S5", "S16"]
    },
    "电信故障": {
        "core_strategies": ["S2", "S7", "S12"],
        "optional_strategies": ["S1", "S4", "S10", "S14"],
        "high_conflict_add": ["S8", "S13"],
        "long_wait_add": ["S5", "S12"]
    },
    "医疗预约": {
        "core_strategies": ["S1", "S3", "S10"],
        "optional_strategies": ["S4", "S6", "S12", "S14"],
        "elderly_add": ["S5", "S16"],
        "urgent_add": ["S7", "S8"]
    }
}

def get_recommended_strategies(domain, scenario, conflict_level, user_profile=None):
    """
    根据场景特征推荐策略列表

    Args:
        domain: 领域（电商/银行/电信/医疗）
        scenario: 具体场景
        conflict_level: 冲突强度（低/中/高）
        user_profile: 用户画像（可选）

    Returns:
        推荐策略列表 [S1, S2, ...]
    """
    # 基础策略（所有对话都需要）
    recommended = ["S1"]

    # 根据场景查找映射
    scenario_key = None
    for key in SCENARIO_STRATEGY_MAPPING:
        if key in scenario or scenario in key:
            scenario_key = key
            break

    if scenario_key:
        mapping = SCENARIO_STRATEGY_MAPPING[scenario_key]
        recommended.extend(mapping["core_strategies"])

        # 根据冲突强度添加策略
        if conflict_level == "高":
            recommended.extend(mapping.get("high_conflict_add", []))

        # 根据用户画像添加策略
        if user_profile:
            if user_profile.get("face_sensitivity") == "高":
                recommended.extend(mapping.get("face_sensitive_add", mapping.get("vip_add", [])))

            if user_profile.get("age_group") == "老年":
                recommended.extend(mapping.get("elderly_add", []))

        # 随机添加可选策略（增加多样性）
        import random
        optional = mapping.get("optional_strategies", [])
        if optional:
            num_optional = min(2, len(optional))
            recommended.extend(random.sample(optional, num_optional))

    # 去重并保持顺序
    seen = set()
    result = []
    for s in recommended:
        if s not in seen:
            seen.add(s)
            result.append(s)

    return result

# 检查策略是否应该在场景中触发
def should_trigger_strategy(strategy_id, scenario_features):
    """
    检查给定策略是否应该在特定场景中触发

    Args:
        strategy_id: 策略ID（S1-S18）
        scenario_features: 场景特征字典

    Returns:
        bool: 是否应该触发
    """
    if strategy_id not in STRATEGY_TRIGGER_MATRIX:
        return False

    trigger_config = STRATEGY_TRIGGER_MATRIX[strategy_id]

    # 如果标记为"所有场景都需要"
    if trigger_config.get("required_in_all_scenarios", False):
        return True

    # 检查场景匹配
    scenarios = trigger_config.get("scenarios", [])
    if scenarios:
        # 如果是"所有场景（收尾）"等特殊描述
        if "所有场景" in str(scenarios):
            conditions = trigger_config.get("trigger_conditions", {})
            if conditions.get("conversation_stage") == scenario_features.get("conversation_stage"):
                return True
        elif any(s in scenario_features.get("scenario", "") for s in scenarios):
            return True

    # 检查触发条件
    conditions = trigger_config.get("trigger_conditions", {})
    for key, value in conditions.items():
        if scenario_features.get(key) != value and isinstance(value, str):
            continue
        return True

    return False

if __name__ == "__main__":
    # 测试策略推荐
    print("=== 策略推荐测试 ===\n")

    test_cases = [
        {
            "domain": "电商",
            "scenario": "商品退款",
            "conflict_level": "高",
            "user_profile": {"face_sensitivity": "高", "age_group": "中年"}
        },
        {
            "domain": "银行",
            "scenario": "账单异议",
            "conflict_level": "中",
            "user_profile": {"face_sensitivity": "中"}
        },
        {
            "domain": "医疗",
            "scenario": "预约挂号",
            "conflict_level": "低",
            "user_profile": {"age_group": "老年", "face_sensitivity": "高"}
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"测试用例 {i}:")
        print(f"  领域: {case['domain']}")
        print(f"  场景: {case['scenario']}")
        print(f"  冲突: {case['conflict_level']}")
        print(f"  用户: {case['user_profile']}")

        strategies = get_recommended_strategies(
            case['domain'],
            case['scenario'],
            case['conflict_level'],
            case['user_profile']
        )

        print(f"  推荐策略: {', '.join(strategies)}")
        print()
