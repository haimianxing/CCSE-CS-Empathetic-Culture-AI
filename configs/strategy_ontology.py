"""
CCSE 6类×18子策略本体定义
来源: emnlp_18strategies_derivation.md

6大类 (C1-C6):
  C1 倾听确认 (Active Listening & Acknowledgment)
  C2 面子维护 (Face-Saving & Dignity Preservation) — ★全部新增
  C3 情绪安抚 (Emotional Soothing & De-escalation)
  C4 方案推进 (Solution Advancement)
  C5 关系修复 (Relationship Repair & Continuation)
  C6 文化适配 (Cultural Adaptation) — ★全部新增
"""

STRATEGY_ONTOLOGY = {
    "C1_倾听确认": {
        "id": "C1",
        "name_en": "Active Listening & Acknowledgment",
        "sub_strategies": {
            "S1_复述确认": {
                "id": "S1",
                "name_en": "Restatement & Confirmation",
                "source": "继承: ESConv Restatement + CSC RP",
                "description": "复述客户问题核心，确认理解无误",
                "examples": [
                    "您是说在3月15日购买的商品还没收到对吗？我帮您核实一下",
                    "我理解一下，您反映的是退款金额不对，差额是15元对吗？",
                    "也就是说您的银行卡被扣了两次费用，我来帮您查一下明细"
                ]
            },
            "S2_情感映射": {
                "id": "S2",
                "name_en": "Emotion Reflection",
                "source": "升级: 从CSC EM拆出(识别情绪)",
                "description": "识别并映射客户隐藏情绪，特别是中文委婉表达背后的真实情绪",
                "examples": [
                    "听起来您对这次体验感到非常失望",
                    "我能感觉到您对这个结果很着急",
                    "您似乎对反复出现这个问题有些无奈"
                ]
            },
            "S3_需求提炼": {
                "id": "S3",
                "name_en": "Need Refinement",
                "source": "升级: ESConv Question + CSC PR + 意图推断",
                "description": "在客户委婉表达基础上推断真实意图",
                "examples": [
                    "您提到'不太方便'，是不是指配送时间需要调整？",
                    "听您的意思，是希望我们给一个书面的处理结果对吗？",
                    "您说'算了'，但我感觉您其实还是希望我们能解决这个问题，是这样吗？"
                ]
            }
        }
    },
    "C2_面子维护": {
        "id": "C2",
        "name_en": "Face-Saving & Dignity Preservation",
        "note": "★全部新增 — 现有体系完全缺失",
        "sub_strategies": {
            "S4_委婉致歉": {
                "id": "S4",
                "name_en": "Tactful Apology",
                "source": "★新增: Brown & Levinson消极面子理论",
                "description": "用保护客户消极面子的方式致歉，避免暗示客户是弱者",
                "examples": [
                    "给您带来不便，我们深感抱歉",
                    "这次体验确实没有达到我们对服务标准的期望，非常遗憾",
                    "让您久等了，这是我们工作需要改进的地方"
                ]
            },
            "S5_肯定价值": {
                "id": "S5",
                "name_en": "Value Affirmation",
                "source": "升级: ESConv Affirmation → 面子维护功能",
                "description": "肯定客户的配合/判断/建议，给客户台阶和面子",
                "examples": [
                    "非常感谢您的耐心等待",
                    "您说得对，这个情况确实不应该发生",
                    "您的建议非常好，我们会认真改进"
                ]
            },
            "S6_避免指责": {
                "id": "S6",
                "name_en": "Blame Avoidance",
                "source": "★新增: 高权力距离→客户期待被尊重",
                "description": "用中性语言或'我们'共担，避免暗示客户有过错",
                "examples": [
                    "系统可能没有及时提醒到您",
                    "让我再给您详细说明一下",
                    "这个环节确实容易让人困惑，我来帮您理清楚"
                ]
            }
        }
    },
    "C3_情绪安抚": {
        "id": "C3",
        "name_en": "Emotional Soothing & De-escalation",
        "sub_strategies": {
            "S7_共情表达": {
                "id": "S7",
                "name_en": "Empathy Expression",
                "source": "继承+细化: ESConv Self-Disclosure → 专业共情",
                "description": "专业简短的共情表达，不过多涉及个人信息",
                "examples": [
                    "换作是我也会很着急的",
                    "我非常理解您的心情",
                    "遇到这种情况确实让人很头疼"
                ]
            },
            "S8_降温化解": {
                "id": "S8",
                "name_en": "De-escalation",
                "source": "★新增: CSConv投诉场景(14.2%)需求",
                "description": "结构化降温: 承接情绪→行动承诺→时间预期→转移焦点",
                "examples": [
                    "我完全理解您的心情，让我马上帮您查一下，大约需要2分钟",
                    "您先别着急，我现在就为您处理这件事，给您一个满意的答复",
                    "您的反馈我收到了，这个问题我来负责跟进，预计今天内给您结果"
                ]
            },
            "S9_价值认同": {
                "id": "S9",
                "name_en": "Value Alignment",
                "source": "升级: 侧重诉求合理性认同（区别于S5的面子）",
                "description": "认同客户立场和诉求的合理性",
                "examples": [
                    "您的诉求非常合理",
                    "您说得对，每个消费者都值得被尊重",
                    "换做任何人遇到这种情况都会有同样的感受"
                ]
            }
        }
    },
    "C4_方案推进": {
        "id": "C4",
        "name_en": "Solution Advancement",
        "sub_strategies": {
            "S10_明确方案": {
                "id": "S10",
                "name_en": "Clear Solution",
                "source": "继承: CSC ID(14.9%最高) + RI",
                "description": "清晰传达解决方案和政策依据",
                "examples": [
                    "根据我们的退换货政策，您这种情况可以享受7天无理由退货",
                    "我已经为您提交了退款申请，金额198元将在3-5个工作日内退回原支付账户",
                    "现在的方案是：先由我为您办理换货，同时补偿您一张20元的优惠券"
                ]
            },
            "S11_选项呈现": {
                "id": "S11",
                "name_en": "Choice Presentation",
                "source": "升级: CSC PS + 赋予客户选择权",
                "description": "给客户提供选择而非单一方案，增强控制感",
                "examples": [
                    "您看是希望换货还是退款呢？",
                    "有两种方案供您选择：一是补发同款商品，二是办理退款并赠送优惠券",
                    "您更倾向于我们上门取件，还是您自己寄回？"
                ]
            },
            "S12_预期管理": {
                "id": "S12",
                "name_en": "Expectation Management",
                "source": "★新增: 管理客户对时间线和结果的心理预期",
                "description": "提前告知处理流程、时间线和可能的结果",
                "examples": [
                    "通常处理时间是1-3天，如果超时我会主动跟进",
                    "我帮您先做个登记，最迟明天上午会有专人联系您",
                    "这个情况比较特殊，我需要请示主管，可能需要多等一会儿"
                ]
            }
        }
    },
    "C5_关系修复": {
        "id": "C5",
        "name_en": "Relationship Repair & Continuation",
        "sub_strategies": {
            "S13_补偿关怀": {
                "id": "S13",
                "name_en": "Compensatory Care",
                "source": "★新增: 中国'人情'文化需求",
                "description": "在适当场景下主动提供补偿，表达诚意",
                "examples": [
                    "为了表达我们的歉意，给您申请了一张30元的无门槛优惠券",
                    "考虑到给您造成的不便，这次运费由我们来承担",
                    "这次的问题是我们不对，我会为您申请一份小礼品表示歉意"
                ]
            },
            "S14_跟进闭环": {
                "id": "S14",
                "name_en": "Follow-up Closure",
                "source": "继承: CSC FR (CSConv第4常见2-hop转移)",
                "description": "确认问题是否解决，征求反馈",
                "examples": [
                    "请问您还有其他问题需要我帮助吗？",
                    "您看这样处理您还满意吗？",
                    "如果后续还有任何问题，欢迎随时联系我们"
                ]
            },
            "S15_长期维护": {
                "id": "S15",
                "name_en": "Long-term Relationship",
                "source": "继承: CSC RC + 中国人情表达",
                "description": "建立长期关系，温情收尾",
                "examples": [
                    "祝您生活愉快，期待下次为您服务",
                    "感谢您选择我们，希望下次能给您带来更好的体验",
                    "后续有任何需要随时找我，我的工号是8023"
                ]
            }
        }
    },
    "C6_文化适配": {
        "id": "C6",
        "name_en": "Cultural Adaptation",
        "note": "★全部新增 — cuDialog + Cultural Prompting 理论支撑",
        "sub_strategies": {
            "S16_尊敬升级": {
                "id": "S16",
                "name_en": "Respectful Escalation",
                "source": "★新增: Hofstede权力距离(中国80分)",
                "description": "根据客户身份/年龄调整敬语层级和沟通风格",
                "examples": [
                    "叔叔/阿姨您好，您放心我来帮您处理",
                    "尊敬的VIP会员，感谢您的来电",
                    "亲~这边给您看一下哦"
                ]
            },
            "S17_节日关怀": {
                "id": "S17",
                "name_en": "Festival Care",
                "source": "★新增: 长期取向(87)+集体主义(20)",
                "description": "在节日场景中加入人文关怀",
                "examples": [
                    "快过年了，提前祝您新年快乐，这个问题我加急处理",
                    "中秋节快乐，希望这个问题解决后您能好好过节",
                    "双11辛苦了，感谢您的耐心等待"
                ]
            },
            "S18_语境适配": {
                "id": "S18",
                "name_en": "Contextual Adaptation",
                "source": "★新增: 地域沟通风格差异",
                "description": "根据客户的地域/表达风格调整回复策略",
                "examples": [
                    # 根据客户直率程度调整
                    "我直接给您说结果",  # 对直率型客户
                    "您说得有道理，我再帮您看看其他方案",  # 对委婉型客户
                ]
            }
        }
    }
}

# 领域定义
DOMAINS = {
    "电商": {
        "scenarios": [
            "退货退款", "商品质量问题", "物流延迟", "商品与描述不符",
            "优惠券使用问题", "售后维修", "换货", "虚假宣传",
            "发票问题", "会员权益"
        ],
        "policies": [
            "7天无理由退货政策", "15天换货政策", "三包政策",
            "假一赔三", "价格保护", "运费险"
        ]
    },
    "银行": {
        "scenarios": [
            "账户异常", "信用卡盗刷", "转账失败", "利率咨询",
            "贷款审批进度", "手续费争议", "理财产品投诉", "卡片年费",
            "短信通知费", "ATM取款异常"
        ],
        "policies": [
            "盗刷赔付政策", "免年费条件", "72小时挂失保障",
            "贷款审批流程", "理财风险提示"
        ]
    },
    "电信": {
        "scenarios": [
            "话费异常", "套餐变更", "信号问题", "宽带故障",
            "流量超标", "号码携转", "增值业务退订", "合约机问题",
            "骚扰电话投诉", "SIM卡故障"
        ],
        "policies": [
            "套餐变更规则", "靓号协议", "宽带安装承诺",
            "携号转网条件", "投诉处理时限"
        ]
    },
    "医疗": {
        "scenarios": [
            "挂号预约问题", "检查报告查询", "药品退换", "费用异议",
            "医保报销咨询", "门诊排队投诉", "医生态度投诉",
            "住院流程咨询", "转院手续", "术后随访"
        ],
        "policies": [
            "预约挂号规则", "退号政策", "医保报销比例",
            "药品管理规定", "患者投诉处理流程"
        ]
    }
}

# 文化因子维度 (MECE)
CULTURAL_FACTORS = {
    "关系取向": {
        "values": ["正式尊称", "亲切随和", "专业礼貌"],
        "description": "客服与客户的关系定位"
    },
    "面子维护": {
        "values": ["高面子敏感(先肯定再说明)", "中面子敏感", "低面子敏感(直接沟通)"],
        "description": "对话中的面子维护程度"
    },
    "委婉度": {
        "values": ["高委婉(缓冲语+分步说明)", "中委婉", "低委婉(直截了当)"],
        "description": "拒绝/坏消息的包装程度"
    },
    "冲突强度": {
        "values": ["低(咨询为主)", "中(有不满情绪)", "高(强烈投诉/威胁升级)"],
        "description": "客户情绪和冲突级别"
    }
}

# 导出所有策略ID列表
ALL_STRATEGY_IDS = []
ALL_CATEGORY_IDS = []
for cat_name, cat_data in STRATEGY_ONTOLOGY.items():
    ALL_CATEGORY_IDS.append(cat_data["id"])
    for s_name, s_data in cat_data["sub_strategies"].items():
        ALL_STRATEGY_IDS.append(s_data["id"])

# 策略来源统计
STRATEGY_SOURCE_STATS = {
    "直接继承": ["S1", "S10", "S14", "S15"],
    "升级细化": ["S2", "S3", "S6", "S7", "S9", "S11"],
    "全新新增": ["S4", "S5", "S8", "S12", "S13", "S16", "S17", "S18"]
}

# 补充场景模板：确保S13/S16/S17/S18被覆盖
SUPPLEMENTARY_SCENARIOS = {
    "S13_补偿关怀": {
        "domains": ["电商", "银行", "电信"],
        "scenarios": ["退货退款", "手续费争议", "话费异常"],
        "extra_prompt": "\n## 特别要求\n- 对话中必须包含S13(补偿关怀)策略：客服主动提供补偿（优惠券、话费券、减免费用等）\n- 补偿应合理合规，不能越权\n- 补偿触发条件应自然（因服务失误导致客户不便）\n- 确保在strategies_used中标注S13"
    },
    "S16_尊敬升级": {
        "domains": ["银行", "医疗"],
        "scenarios": ["贷款审批进度", "术后随访", "住院流程咨询"],
        "extra_prompt": "\n## 特别要求\n- 对话中必须包含S16(尊敬升级)策略：客服根据客户身份/年龄调整敬语层级\n- 客户为老年人或VIP客户\n- 客服使用更尊敬的称呼和更耐心的语气\n- 例如：'叔叔/阿姨您放心' 或 '尊敬的VIP会员'\n- 确保在strategies_used中标注S16"
    },
    "S17_节日关怀": {
        "domains": ["电商", "电信"],
        "scenarios": ["物流延迟", "信号问题", "售后服务"],
        "extra_prompt": "\n## 特别要求\n- 对话中必须包含S17(节日关怀)策略：解决技术问题时融入节日问候\n- 场景设定在特定节日前后（春节、中秋、双11等）\n- 节日关怀应自然融入，不突兀\n- 例如：'快过年了，提前祝您新年快乐，这个问题我加急处理'\n- 确保在strategies_used中标注S17"
    },
    "S18_语境适配": {
        "domains": ["电商", "电信"],
        "scenarios": ["售后服务", "套餐变更", "商品质量问题"],
        "extra_prompt": "\n## 特别要求\n- 对话中必须包含S18(语境适配)策略：客服根据客户沟通风格调整回复方式\n- 客户有明显的地域/风格特征（如北方人直率，南方人委婉）\n- 客服根据客户风格匹配回复的直率/委婉程度\n- 确保在strategies_used中标注S18"
    }
}
