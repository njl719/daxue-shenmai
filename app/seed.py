# -*- coding: utf-8 -*-
"""首次初始化:写入配置占位、大纲骨架与少量示例数据。

所有示例条目 seed=true,界面中可识别、可删除。
示例内容均为经典教材中可核验的基础内容,并注明出处。
考试年份/院校/数一数二等留空,待用户确认后填写——不擅自锁定。
"""
import datetime

TODAY = datetime.date.today().isoformat()


def DEFAULT_SETTINGS():
    return {
        "exam_year": None,
        "exam_date": None,
        "target_school": None,
        "math_type": None,
        "daily_minutes": 240,
        "subjects": {
            "math": {"enabled": True, "priority": 1, "minutes": 90},
            "cs408": {"enabled": True, "priority": 2, "minutes": 90},
            "english": {"enabled": True, "priority": 3, "minutes": 45},
        },
        "weekly_review_weekday": 6,
        "backup_on_start": True,
        "max_backups": 14,
        # AI 默认走本地 Ollama:无需 API Key,模型在设置页从已下载列表中选择
        "ai": {"mode": "local", "base_url": "", "model": "", "vision_model": ""},
    }


def DEFAULT_CATALOG():
    """大纲骨架。note 标注适用范围(数一/数二未确认,不锁定)。"""
    return {
        "tracks": {
            "math-gaoshu": {"name": "高等数学", "subject": "math", "chapters": [
                {"id": "math-gs-ch1", "name": "函数、极限、连续"},
                {"id": "math-gs-ch2", "name": "一元函数微分学"},
                {"id": "math-gs-ch3", "name": "一元函数积分学"},
                {"id": "math-gs-ch4", "name": "多元函数微分学"},
                {"id": "math-gs-ch5", "name": "多元函数积分学", "note": "数一为主"},
                {"id": "math-gs-ch6", "name": "常微分方程"},
                {"id": "math-gs-ch7", "name": "无穷级数", "note": "数一、数三"},
            ]},
            "math-xian dai": {"name": "线性代数", "subject": "math", "chapters": [
                {"id": "math-xd-ch1", "name": "行列式"},
                {"id": "math-xd-ch2", "name": "矩阵"},
                {"id": "math-xd-ch3", "name": "向量组"},
                {"id": "math-xd-ch4", "name": "线性方程组"},
                {"id": "math-xd-ch5", "name": "特征值与特征向量"},
                {"id": "math-xd-ch6", "name": "二次型"},
            ]},
            "math-gailv": {"name": "概率论与数理统计", "subject": "math", "chapters": [
                {"id": "math-gl-ch1", "name": "随机事件与概率"},
                {"id": "math-gl-ch2", "name": "一维随机变量及其分布"},
                {"id": "math-gl-ch3", "name": "多维随机变量及其分布"},
                {"id": "math-gl-ch4", "name": "随机变量的数字特征"},
                {"id": "math-gl-ch5", "name": "大数定律与中心极限定理"},
                {"id": "math-gl-ch6", "name": "数理统计", "note": "数一、数三"},
            ]},
            "cs408-ds": {"name": "数据结构", "subject": "cs408", "chapters": [
                {"id": "ds-ch1", "name": "绪论与复杂度分析"},
                {"id": "ds-ch2", "name": "线性表"},
                {"id": "ds-ch3", "name": "栈、队列和数组"},
                {"id": "ds-ch4", "name": "串(KMP)"},
                {"id": "ds-ch5", "name": "树与二叉树"},
                {"id": "ds-ch6", "name": "图"},
                {"id": "ds-ch7", "name": "查找"},
                {"id": "ds-ch8", "name": "排序"},
            ]},
            "cs408-zy": {"name": "计算机组成原理", "subject": "cs408", "chapters": [
                {"id": "zy-ch1", "name": "计算机系统概述"},
                {"id": "zy-ch2", "name": "数据的表示和运算"},
                {"id": "zy-ch3", "name": "存储系统"},
                {"id": "zy-ch4", "name": "指令系统"},
                {"id": "zy-ch5", "name": "中央处理器"},
                {"id": "zy-ch6", "name": "总线和输入输出系统"},
            ]},
            "cs408-os": {"name": "操作系统", "subject": "cs408", "chapters": [
                {"id": "os-ch1", "name": "操作系统概述"},
                {"id": "os-ch2", "name": "进程与线程"},
                {"id": "os-ch3", "name": "内存管理"},
                {"id": "os-ch4", "name": "文件管理"},
                {"id": "os-ch5", "name": "输入输出管理"},
            ]},
            "cs408-net": {"name": "计算机网络", "subject": "cs408", "chapters": [
                {"id": "net-ch1", "name": "计算机网络体系结构"},
                {"id": "net-ch2", "name": "物理层"},
                {"id": "net-ch3", "name": "数据链路层"},
                {"id": "net-ch4", "name": "网络层"},
                {"id": "net-ch5", "name": "传输层"},
                {"id": "net-ch6", "name": "应用层"},
            ]},
            "english-rd": {"name": "英语", "subject": "english", "chapters": [
                {"id": "en-ch1", "name": "核心词汇"},
                {"id": "en-ch2", "name": "长难句与语法"},
                {"id": "en-ch3", "name": "阅读理解方法"},
                {"id": "en-ch4", "name": "写作"},
            ]},
        }
    }


def _kp(i, subject, chapter, name, content, source, tags=None, formulas=None,
        comparisons=None, prerequisites=None, status="not_started"):
    return {
        "id": "kp-%s-%04d" % (subject if subject != "cs408" else "408", i),
        "subject": subject, "chapter_id": chapter, "name": name,
        "prerequisites": prerequisites or [], "tags": tags or [],
        "content_md": content, "formulas": formulas or [],
        "comparisons": comparisons or [], "source": source,
        "status": status, "seed": True,
        "created": TODAY, "updated": TODAY,
    }


def SEED_KNOWLEDGE():
    return [
        _kp(1, "math", "math-gs-ch1", "洛必达法则",
            "处理 $\\frac{0}{0}$ 或 $\\frac{\\infty}{\\infty}$ 型未定式的基本工具,"
            "将函数比转化为导数比。使用前必须先验证类型。",
            "同济《高等数学》第七版 §3.2",
            tags=["计算", "易错"],
            formulas=[{
                "latex": "\\lim_{x\\to a}\\frac{f(x)}{g(x)}=\\lim_{x\\to a}\\frac{f'(x)}{g'(x)}",
                "condition": "① $\\frac{0}{0}$ 或 $\\frac{\\infty}{\\infty}$ 型;"
                             "② 分子分母在 $a$ 附近可导且 $g'(x)\\neq 0$;"
                             "③ 导数比的极限存在(或为 $\\infty$)",
                "misuse": "① 不验证未定式类型直接用;"
                          "② 数列极限不能直接用(须先离散化或用归结原则);"
                          "③ 导数比极限不存在时不能断言原极限不存在(此时法则失效而非结论为否)",
            }]),
        _kp(2, "math", "math-gs-ch1", "等价无穷小替换",
            "乘除因子中可用等价无穷小替换;加减运算中不可随意替换,"
            "需保证替换后不发生主部相消。",
            "同济《高等数学》第七版 §3.3",
            tags=["计算", "易错"],
            formulas=[{
                "latex": "x\\to 0:\\ e^x-1\\sim x,\\ \\ln(1+x)\\sim x,\\ "
                         "1-\\cos x\\sim \\tfrac{x^2}{2},\\ (1+x)^a-1\\sim ax",
                "condition": "仅在乘除因子位置替换;加减位置替换需用泰勒展开到足够阶验证",
                "misuse": "$e^x-1-x$ 中把 $e^x-1$ 换成 $x$ 得极限 0 —— 错误,"
                          "正确答案是 $\\tfrac12$(泰勒:$e^x=1+x+\\tfrac{x^2}{2}+o(x^2)$)",
            }], prerequisites=["kp-math-0001"]),
        _kp(3, "cs408", "ds-ch8", "快速排序",
            "分治排序:选主元(pivot)划分,使左侧元素均不大于主元、右侧均不小于主元,"
            "再递归两侧。平均性能最好的内部排序之一。",
            "严蔚敏《数据结构(C 语言版)》§10.3;王道《数据结构》排序章",
            tags=["计算", "综合应用", "高频"],
            comparisons=[{
                "with": "归并排序",
                "table": {
                    "平均时间": ["O(n log n)", "O(n log n)"],
                    "最坏时间": ["O(n²)(序列已基本有序且取端点为主元)", "O(n log n)"],
                    "空间": ["O(log n)(递归栈,平均)", "O(n)(辅助数组)"],
                    "稳定性": ["不稳定", "稳定"],
                },
            }],
            formulas=[{
                "latex": "T(n)=T(k)+T(n-k-1)+\\Theta(n)",
                "condition": "k 为划分后一侧元素数;最好/平均 k≈n/2 → O(n log n);最坏 k=0 → O(n²)",
                "misuse": "把“最坏情况是输入已有序”记成归并排序;忽略快排空间是递归栈 O(log n) 而非 O(1)",
            }]),
        _kp(4, "cs408", "net-ch5", "TCP 连接建立与释放(三次握手/四次挥手)",
            "建立连接需三次报文握手;释放连接需四次挥手,因为 TCP 全双工,"
            "两个方向的数据传输需分别关闭。",
            "谢希仁《计算机网络》第七版 §5.9;RFC 9293",
            tags=["概念", "高频", "易混"],
            comparisons=[{
                "with": "三次握手 vs 四次挥手",
                "table": {
                    "次数": ["3 次(SYN → SYN+ACK → ACK)", "4 次(FIN → ACK → FIN → ACK)"],
                    "关键状态": ["SYN_SENT / SYN_RCVD / ESTABLISHED",
                                 "FIN_WAIT_1/2, CLOSE_WAIT, LAST_ACK, TIME_WAIT"],
                    "为何不能合并": ["SYN 与 ACK 可随同一个报文发送",
                                     "被动方收到 FIN 后可能还有数据要发,"
                                     "ACK 与 FIN 分开发送"],
                },
            }],
            formulas=[{
                "latex": "\\text{TIME_WAIT} = 2\\,\\text{MSL}",
                "condition": "主动关闭方进入 TIME_WAIT,等待 2MSL 后才真正关闭",
                "misuse": "把 TIME_WAIT 记在被动关闭方;"
                          "以为三次挥手足够(忽略半关闭状态下被动方仍可发数据)",
            }]),
        _kp(5, "cs408", "os-ch2", "进程与线程",
            "进程是资源分配的基本单位,线程是处理机调度的基本单位。"
            "同进程内线程共享进程的地址空间和资源,但各自拥有独立的栈与寄存器上下文。",
            "汤小丹《计算机操作系统》第四版 §2.2;王道《操作系统》进程章",
            tags=["概念", "易混"],
            comparisons=[{
                "with": "进程 vs 线程",
                "table": {
                    "定位": ["资源分配的基本单位", "调度的基本单位"],
                    "切换开销": ["大(需切换地址空间等)", "小(同进程内仅切栈和寄存器)"],
                    "共享性": ["独立地址空间", "共享所属进程的代码、数据、打开文件等"],
                },
            }]),
    ]


def SEED_MISTAKES():
    return [
        {
            "id": "mk-0001", "subject": "math",
            "knowledge_ids": ["kp-math-0002"],
            "qtype": "计算", "difficulty": 2,
            "question_md": "求极限:$\\lim_{x\\to 0}\\dfrac{e^x-1-x}{x^2}$",
            "my_answer_md": "把 $e^x-1$ 等价替换为 $x$,得到 $\\dfrac{x-x}{x^2}=0$",
            "correct_answer_md": "$\\dfrac{1}{2}$",
            "error_reason": "等价无穷小在加减中误用",
            "solution_md": "泰勒展开:$e^x = 1 + x + \\dfrac{x^2}{2} + o(x^2)$,"
                           "故分子 $e^x-1-x = \\dfrac{x^2}{2}+o(x^2)$,"
                           "原式 $= \\lim \\dfrac{\\tfrac{x^2}{2}+o(x^2)}{x^2} = \\dfrac12$。\n\n"
                           "另法(两次洛必达):$\\dfrac{e^x-1-x}{x^2} \\to \\dfrac{e^x-1}{2x}"
                           " \\to \\dfrac{e^x}{2} \\to \\dfrac12$(均为 0/0 型,可逐次使用)。",
            "source": "示例题(经典极限,同济高数 §3.3 习题类型),可删除",
            "reviews": [], "interval_days": 0, "ease": 2.5, "lapses": 0,
            "next_review": None, "archived": False,
            "seed": True, "created": TODAY,
        },
        {
            "id": "mk-0002", "subject": "cs408",
            "knowledge_ids": ["kp-408-0003"],
            "qtype": "概念", "difficulty": 1,
            "question_md": "对序列 1,2,3,…,n 做(以第一个元素为主元的)快速排序,"
                           "比较次数的量级是?",
            "my_answer_md": "O(n log n)",
            "correct_answer_md": "O(n²)",
            "error_reason": "混淆平均与最坏情形",
            "solution_md": "序列已有序时,每次划分主元为最小元素,一侧为空,"
                           "划分极不平衡:第 i 趟划分需比较 n-i 次,"
                           "总比较次数 $\\sum_{i=1}^{n}(n-i)=\\dfrac{n(n-1)}{2}=O(n^2)$。\n\n"
                           "避免方法:随机选取主元、三数取中。"
                           "平均情形才是 O(n log n)。",
            "source": "示例题(王道数据结构排序章常见题型),可删除",
            "reviews": [], "interval_days": 0, "ease": 2.5, "lapses": 0,
            "next_review": None, "archived": False,
            "seed": True, "created": TODAY,
        },
    ]


def SEED_VOCAB():
    return [
        {
            "id": "vb-0001", "kind": "word",
            "text": "yield",
            "context_md": "示例:Foreign investors yield to pressure. / a high yield on bonds",
            "meaning_md": "v. 屈服,让步(yield to);产出,产生;n. 产量,收益。"
                          "考研阅读高频多义词,注意在上下文中区分“屈服”与“产出”。",
            "source": "示例(常见多义词,释义可在任意权威词典核验),可删除",
            "reviews": [], "interval_days": 0, "ease": 2.5, "lapses": 0,
            "next_review": None, "seed": True, "archived": False,
            "created": TODAY,
        },
    ]


def seed_if_empty(store):
    """仅在对应文件不存在时写入,绝不覆盖已有数据。"""
    defaults = {
        "settings": DEFAULT_SETTINGS(),
        "catalog": DEFAULT_CATALOG(),
        "knowledge": SEED_KNOWLEDGE(),
        "mistakes": SEED_MISTAKES(),
        "vocab": SEED_VOCAB(),
        "records": [],
        "plan": {"generated_at": None, "days": {}},
    }
    created = []
    import os
    for name, data in defaults.items():
        path = os.path.join(store.data_dir, name + ".json")
        if not os.path.exists(path):
            store.save(name, data)
            created.append(name)
    return created
