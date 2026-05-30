"""12 类病虫害 × 5 物候期 = 60 条三位一体绿色防治种子方案

依据：
  NY/T 393-2020 《绿色食品 农药使用准则》
  GB 2763-2021 食品安全国家标准 食品中农药最大残留限量
  廉江红橙产业园常规防治经验

所有方案为产业园建议性参考，最终用药须遵循当地农业农村部门最新指导。
"""

from __future__ import annotations

from itertools import product
from typing import Iterator

from .. import config as C


# ---------- 化学药剂常用项 ----------
# 严禁推荐高毒、违禁农药；以下均为低毒低残留登记药剂示例
CHEM_MITICIDE_SPIROMESIFEN = {
    "name": "螺螨酯 240 g/L 悬浮剂",
    "dosage": "稀释 2000~3000 倍液，叶面均匀喷雾",
    "phi": "21 天",
    "notes": "请勿与碱性农药混用；高温正午避免施药",
}
CHEM_AVERMECTIN = {
    "name": "阿维菌素 1.8% 乳油",
    "dosage": "稀释 1500~2000 倍液",
    "phi": "14 天",
    "notes": "蜜蜂敏感，开花期慎用；避免日间高温施药",
}
CHEM_IMIDACLOPRID = {
    "name": "吡虫啉 10% 可湿性粉剂",
    "dosage": "稀释 1500~2500 倍液",
    "phi": "21 天",
    "notes": "蜜蜂期慎用；勿与碱性农药混用",
}
CHEM_CHLORANTRANILIPROLE = {
    "name": "氯虫苯甲酰胺 20% 悬浮剂",
    "dosage": "每亩 10~15 mL 兑水 30~45 L",
    "phi": "14 天",
    "notes": "兼治潜叶蛾、卷叶蛾；安全间隔期内禁止采摘",
}
CHEM_COPPER_HYDROXIDE = {
    "name": "氢氧化铜 53.8% 干悬浮剂（可杀得叁千）",
    "dosage": "稀释 800~1000 倍液",
    "phi": "10 天",
    "notes": "高温(>32℃)及花期慎用；与酸性农药存隔期",
}
CHEM_THIOPHANATE_METHYL = {
    "name": "甲基硫菌灵 70% 可湿性粉剂",
    "dosage": "稀释 800~1000 倍液",
    "phi": "14 天",
    "notes": "勿与铜制剂同时混用",
}
CHEM_DIFENOCONAZOLE = {
    "name": "苯醚甲环唑 10% 水分散粒剂",
    "dosage": "稀释 2000~3000 倍液",
    "phi": "14 天",
    "notes": "幼果期慎用，避免药害",
}
CHEM_PYRACLOSTROBIN = {
    "name": "吡唑醚菌酯 25% 悬浮剂",
    "dosage": "稀释 1500~2500 倍液",
    "phi": "21 天",
    "notes": "保护性 + 治疗性双效；勿连续 3 次使用同种成分",
}
CHEM_HIGH_EFFICIENT_CYHALOTHRIN = {
    "name": "高效氯氟氰菊酯 2.5% 乳油",
    "dosage": "稀释 1500~2000 倍液",
    "phi": "14 天",
    "notes": "对水生生物剧毒，远离水域；蜜蜂期禁用",
}
CHEM_BUPROFEZIN = {
    "name": "噻嗪酮 25% 可湿性粉剂",
    "dosage": "稀释 1000~1500 倍液",
    "phi": "21 天",
    "notes": "对若虫高效，对成虫无效；蚕区慎用",
}
CHEM_MINERAL_OIL = {
    "name": "矿物油（机油乳剂）99%",
    "dosage": "稀释 150~200 倍液",
    "phi": "无强制 PHI（绿色推荐）",
    "notes": "气温 >32℃ 或低于 5℃ 禁用；花期勿用",
}
CHEM_BT = {
    "name": "苏云金杆菌 BT 16000 IU/mg 可湿性粉剂",
    "dosage": "稀释 800~1000 倍液",
    "phi": "无残留期",
    "notes": "傍晚施药；勿与碱性、铜制剂混用",
}


# ---------- 物理 & 生物 通用条目 ----------
PHY_YELLOW_BOARD = "每亩悬挂诱虫黄板 20~30 张，挂高 1.5 m，10~15 天更换"
PHY_LIGHT_TRAP = "果园核心区域布置频振式杀虫灯 2~3 盏/30 亩，傍晚开启"
PHY_PRUNE_BURN = "及时剪除发病枝叶并集中烧毁，禁止堆肥"
PHY_NET = "幼苗期及关键物候期使用 40~60 目防虫网隔离"
PHY_CLEAN = "冬剪后清园：刮除老粗皮、清扫落叶落果、统一无害化处理"
PHY_HAND_PICK = "局部少量虫体人工摘除集中销毁"

BIO_PREDATOR_MITE = "释放胡瓜钝绥螨等捕食螨，1~2 万头/亩，分批悬挂繁殖袋"
BIO_PARASITOID_WASP = "释放赤眼蜂 / 跳小蜂等寄生蜂，按 1 万头/亩"
BIO_BT_BIO = "傍晚喷施苏云金杆菌（BT），生物源、对人畜安全"
BIO_BEAUVERIA = "喷施球孢白僵菌 1×10⁸ 孢子/g 制剂，1500~2000 倍液"
BIO_NATURAL_ENEMY = "保护瓢虫、草蛉、食蚜蝇等本地天敌，禁用广谱杀虫剂"


# ---------- 12 类 × 5 物候期 处方表 ----------
# 结构：disease_key -> phenophase_key -> {physical, biological, chemical[], severity_amplifier}
# 关键化学药剂确保符合 §8.8.2 强制字段：药剂名 / 稀释倍数 / PHI / 注意
PRESCRIPTIONS: dict[str, dict[str, dict]] = {

    # --- 1 黄龙病（毁灭性） ---
    "huanglongbing": {
        "sprout": {
            "physical": (
                "立即标记并隔离染病植株；定期清除疑似病株周围杂草；"
                "新苗采购须确认无毒苗木，禁止接穗交叉。"
            ),
            "biological": "保护本地天敌；释放木虱寄生蜂；强化抗逆树体管理。",
            "chemical": [CHEM_IMIDACLOPRID, CHEM_HIGH_EFFICIENT_CYHALOTHRIN],
            "severity_amplifier": "确诊黄龙病的植株必须立即砍除并就地烧毁，不可化学治疗",
        },
        "flower": {
            "physical": "悬挂木虱黄板诱杀媒介；剪除花期出现明显黄化的疑似病枝",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "确诊植株立即砍除，严禁化学治疗",
        },
        "young_fruit": {
            "physical": PHY_YELLOW_BOARD + "；同时砍除已确诊的红鼻果植株",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID, CHEM_HIGH_EFFICIENT_CYHALOTHRIN],
            "severity_amplifier": "全园普查并填写黄龙病树清单上报合作社",
        },
        "enlargement": {
            "physical": "对红鼻果、青果及斑驳叶植株定点标记 → 集中砍除",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "禁止生病植株果实用于陈皮加工",
        },
        "harvest": {
            "physical": "采收后立即全园普查，砍除挖根销毁所有确诊植株；"
                        "翻耕消毒病株坑后空置至少 6 个月再补种健康苗",
            "biological": "新苗采购走脱毒苗渠道，定期复检无毒认证",
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "重病果园建议申请产业园应急扶持，集中改造",
        },
    },

    # --- 2 溃疡病 ---
    "canker": {
        "sprout": {
            "physical": PHY_PRUNE_BURN + "；萌芽前 3 天全园施铜剂保护",
            "biological": "保护内生拮抗菌，避免广谱杀菌剂全园连用",
            "chemical": [CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "重发园区萌芽期增加 1 次铜制剂喷施",
        },
        "flower": {
            "physical": PHY_PRUNE_BURN,
            "biological": "落花后保护木霉菌等拮抗菌种",
            "chemical": [CHEM_THIOPHANATE_METHYL, CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "重病期 7~10 天复喷一次，连续不超过 3 次",
        },
        "young_fruit": {
            "physical": "及时疏除明显病果；雨后 48 小时内补喷",
            "biological": "保护落叶层中天然拮抗微生物群",
            "chemical": [CHEM_COPPER_HYDROXIDE, CHEM_PYRACLOSTROBIN],
            "severity_amplifier": "暴雨后强制补喷一次",
        },
        "enlargement": {
            "physical": "果园通风修剪，避免郁闭高湿环境",
            "biological": "保护拮抗菌",
            "chemical": [CHEM_PYRACLOSTROBIN, CHEM_THIOPHANATE_METHYL],
            "severity_amplifier": "重病树减产 30% 以上时联系农技顾问会诊",
        },
        "harvest": {
            "physical": PHY_CLEAN + "；冬剪后全园石硫合剂清园 1 次",
            "biological": "保留益生微生物",
            "chemical": [CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "彻底清园避免次年春季暴发",
        },
    },

    # --- 3 疮痂病 ---
    "scab": {
        "sprout": {
            "physical": "剪除上年病枝病叶，集中烧毁；萌芽前喷石硫合剂",
            "biological": "保护拮抗菌群",
            "chemical": [CHEM_DIFENOCONAZOLE, CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "重病园萌芽前必须保护性喷药 1 次",
        },
        "flower": {
            "physical": PHY_PRUNE_BURN,
            "biological": "—",
            "chemical": [CHEM_DIFENOCONAZOLE],
            "severity_amplifier": "花瓣脱落 2/3 时强制补喷",
        },
        "young_fruit": {
            "physical": "疏除明显病果，避免病菌再侵染",
            "biological": "—",
            "chemical": [CHEM_PYRACLOSTROBIN, CHEM_DIFENOCONAZOLE],
            "severity_amplifier": "雨季 7~10 天间隔轮换药剂",
        },
        "enlargement": {
            "physical": "通风修剪，控氮增钾",
            "biological": "—",
            "chemical": [CHEM_PYRACLOSTROBIN],
            "severity_amplifier": "建议引入耐病品种作为补植",
        },
        "harvest": {
            "physical": PHY_CLEAN,
            "biological": "—",
            "chemical": [CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "彻底清园，避免菌源越冬",
        },
    },

    # --- 4 炭疽病 ---
    "anthracnose": {
        "sprout": {
            "physical": "剪除病枝病叶，集中烧毁",
            "biological": BIO_BEAUVERIA,
            "chemical": [CHEM_DIFENOCONAZOLE, CHEM_THIOPHANATE_METHYL],
            "severity_amplifier": "干旱后突降雨 → 立即喷药保护",
        },
        "flower": {
            "physical": PHY_PRUNE_BURN,
            "biological": "—",
            "chemical": [CHEM_THIOPHANATE_METHYL, CHEM_PYRACLOSTROBIN],
            "severity_amplifier": "花腐严重时减产风险大",
        },
        "young_fruit": {
            "physical": "疏除病果",
            "biological": "—",
            "chemical": [CHEM_PYRACLOSTROBIN, CHEM_DIFENOCONAZOLE],
            "severity_amplifier": "高温高湿期间隔 7 天复喷",
        },
        "enlargement": {
            "physical": "强壮树势，控氮增钾",
            "biological": "—",
            "chemical": [CHEM_PYRACLOSTROBIN],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": PHY_CLEAN + "；采收伤口及时干燥",
            "biological": "—",
            "chemical": [CHEM_THIOPHANATE_METHYL],
            "severity_amplifier": "贮藏期注意通风，防止采后腐烂",
        },
    },

    # --- 5 黑斑病 ---
    "black_spot": {
        "sprout": {
            "physical": "清除上年带菌落叶",
            "biological": "—",
            "chemical": [CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "—",
        },
        "flower": {
            "physical": PHY_PRUNE_BURN,
            "biological": "—",
            "chemical": [CHEM_THIOPHANATE_METHYL, CHEM_DIFENOCONAZOLE],
            "severity_amplifier": "—",
        },
        "young_fruit": {
            "physical": "疏除病果",
            "biological": "—",
            "chemical": [CHEM_DIFENOCONAZOLE, CHEM_PYRACLOSTROBIN],
            "severity_amplifier": "雨季加密用药频率",
        },
        "enlargement": {
            "physical": "通风通光，避免果实表面长期附水",
            "biological": "—",
            "chemical": [CHEM_PYRACLOSTROBIN],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": PHY_CLEAN,
            "biological": "—",
            "chemical": [CHEM_COPPER_HYDROXIDE],
            "severity_amplifier": "—",
        },
    },

    # --- 6 红蜘蛛 ---
    "red_mite": {
        "sprout": {
            "physical": PHY_HAND_PICK + "；萌芽前喷矿物油 100 倍清园",
            "biological": BIO_PREDATOR_MITE,
            "chemical": [CHEM_MINERAL_OIL],
            "severity_amplifier": "—",
        },
        "flower": {
            "physical": "—",
            "biological": BIO_PREDATOR_MITE,
            "chemical": [CHEM_MITICIDE_SPIROMESIFEN, CHEM_AVERMECTIN],
            "severity_amplifier": "花期禁用广谱杀虫剂",
        },
        "young_fruit": {
            "physical": "—",
            "biological": BIO_PREDATOR_MITE,
            "chemical": [CHEM_MITICIDE_SPIROMESIFEN],
            "severity_amplifier": "虫口 >5 头/叶 立即施药",
        },
        "enlargement": {
            "physical": "—",
            "biological": BIO_PREDATOR_MITE,
            "chemical": [CHEM_MITICIDE_SPIROMESIFEN, CHEM_AVERMECTIN],
            "severity_amplifier": "持续高温干旱发生率上升",
        },
        "harvest": {
            "physical": PHY_CLEAN + "；采收前 21 天起停止杀螨剂",
            "biological": BIO_PREDATOR_MITE,
            "chemical": [CHEM_MINERAL_OIL],
            "severity_amplifier": "—",
        },
    },

    # --- 7 木虱（HLB 媒介） ---
    "psyllid": {
        "sprout": {
            "physical": PHY_YELLOW_BOARD + "；嫩梢期定期巡查",
            "biological": "保护亮腹釉小蜂等寄生蜂；释放草蛉",
            "chemical": [CHEM_IMIDACLOPRID, CHEM_HIGH_EFFICIENT_CYHALOTHRIN],
            "severity_amplifier": "见虫即治；木虱是黄龙病唯一媒介，零容忍",
        },
        "flower": {
            "physical": PHY_YELLOW_BOARD,
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "young_fruit": {
            "physical": PHY_YELLOW_BOARD,
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID, CHEM_HIGH_EFFICIENT_CYHALOTHRIN],
            "severity_amplifier": "确认成虫尾翘 45° 特征 → 立即全园施药",
        },
        "enlargement": {
            "physical": PHY_YELLOW_BOARD,
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": "采收后清园除尽嫩梢避免越冬",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "全园普查并配合产业园上报",
        },
    },

    # --- 8 潜叶蛾 ---
    "leaf_miner": {
        "sprout": {
            "physical": "及时摘除被害嫩叶",
            "biological": BIO_BT_BIO,
            "chemical": [CHEM_CHLORANTRANILIPROLE],
            "severity_amplifier": "嫩梢抽发期 7 天检查 1 次",
        },
        "flower": {
            "physical": "—",
            "biological": BIO_BT_BIO,
            "chemical": [CHEM_CHLORANTRANILIPROLE],
            "severity_amplifier": "—",
        },
        "young_fruit": {
            "physical": "—",
            "biological": BIO_BT_BIO,
            "chemical": [CHEM_CHLORANTRANILIPROLE, CHEM_AVERMECTIN],
            "severity_amplifier": "—",
        },
        "enlargement": {
            "physical": "—",
            "biological": "保护寄生蜂",
            "chemical": [CHEM_CHLORANTRANILIPROLE],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": PHY_CLEAN,
            "biological": "—",
            "chemical": [CHEM_CHLORANTRANILIPROLE],
            "severity_amplifier": "—",
        },
    },

    # --- 9 蚜虫 ---
    "aphids": {
        "sprout": {
            "physical": PHY_YELLOW_BOARD + "；嫩梢期人工抹芽",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "flower": {
            "physical": PHY_YELLOW_BOARD,
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "young_fruit": {
            "physical": "—",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID, CHEM_HIGH_EFFICIENT_CYHALOTHRIN],
            "severity_amplifier": "—",
        },
        "enlargement": {
            "physical": "—",
            "biological": BIO_NATURAL_ENEMY,
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": PHY_CLEAN,
            "biological": "—",
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
    },

    # --- 10 介壳虫 ---
    "scale_insects": {
        "sprout": {
            "physical": "刮除粗皮老干越冬虫体；萌芽前喷矿物油",
            "biological": BIO_PARASITOID_WASP,
            "chemical": [CHEM_MINERAL_OIL],
            "severity_amplifier": "重病树主干涂抹石硫合剂",
        },
        "flower": {
            "physical": "—",
            "biological": BIO_PARASITOID_WASP,
            "chemical": [CHEM_BUPROFEZIN],
            "severity_amplifier": "若虫盛发期施药效率最佳",
        },
        "young_fruit": {
            "physical": "—",
            "biological": BIO_PARASITOID_WASP,
            "chemical": [CHEM_BUPROFEZIN, CHEM_MINERAL_OIL],
            "severity_amplifier": "—",
        },
        "enlargement": {
            "physical": "—",
            "biological": BIO_PARASITOID_WASP,
            "chemical": [CHEM_BUPROFEZIN],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": PHY_CLEAN + "；冬季喷石硫合剂",
            "biological": "—",
            "chemical": [CHEM_MINERAL_OIL],
            "severity_amplifier": "—",
        },
    },

    # --- 11 花蕾蛆 ---
    "flower_bud_midge": {
        "sprout": {
            "physical": "翻耕园土深翻 10 cm 减少越冬蛹",
            "biological": "保护蛹期寄生蜂",
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "重病园在花蕾露白前立即土壤施药 1 次",
        },
        "flower": {
            "physical": "及时摘除灯笼状膨大花蕾，集中烧毁",
            "biological": "—",
            "chemical": [CHEM_IMIDACLOPRID, CHEM_HIGH_EFFICIENT_CYHALOTHRIN],
            "severity_amplifier": "花蕾露白前后用药效果最佳",
        },
        "young_fruit": {
            "physical": "—",
            "biological": "—",
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "enlargement": {
            "physical": "—",
            "biological": "—",
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": "采后翻耕灭蛹",
            "biological": "—",
            "chemical": [CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
    },

    # --- 12 黑刺粉虱 ---
    "blackfly": {
        "sprout": {
            "physical": PHY_YELLOW_BOARD + "；修剪过密枝条改善通风",
            "biological": "保护粉虱座壳孢菌等自然天敌",
            "chemical": [CHEM_BUPROFEZIN],
            "severity_amplifier": "—",
        },
        "flower": {
            "physical": PHY_YELLOW_BOARD,
            "biological": "释放丽蚜小蜂 1~2 万头/亩",
            "chemical": [CHEM_BUPROFEZIN, CHEM_IMIDACLOPRID],
            "severity_amplifier": "—",
        },
        "young_fruit": {
            "physical": "—",
            "biological": "—",
            "chemical": [CHEM_BUPROFEZIN, CHEM_MINERAL_OIL],
            "severity_amplifier": "煤烟病严重时配合喷洗刷除",
        },
        "enlargement": {
            "physical": "—",
            "biological": "—",
            "chemical": [CHEM_BUPROFEZIN],
            "severity_amplifier": "—",
        },
        "harvest": {
            "physical": PHY_CLEAN + "；冬剪后喷矿物油 100 倍",
            "biological": "—",
            "chemical": [CHEM_MINERAL_OIL],
            "severity_amplifier": "—",
        },
    },
}


def iter_seed_rows() -> Iterator[dict]:
    """生成所有 60 条种子数据行"""
    for disease in C.DISEASE_CLASSES:
        d_key = disease["key"]
        d_id = disease["id"]
        d_name = disease["name_cn"]
        by_phase = PRESCRIPTIONS.get(d_key, {})
        for phase in C.PHENOPHASES:
            p_key = phase["key"]
            p_name = phase["name_cn"]
            rx = by_phase.get(p_key)
            if rx is None:
                continue
            yield {
                "disease_id": d_id,
                "disease_name_cn": d_name,
                "phenophase_key": p_key,
                "phenophase_name_cn": p_name,
                "physical": rx["physical"],
                "biological": rx["biological"],
                "chemical": rx["chemical"],
                "severity_amplifier": rx.get("severity_amplifier", ""),
            }
