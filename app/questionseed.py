# -*- coding: utf-8 -*-
"""自主原创种子题(平台原创,人工编写,答案与解析经人工核验)。

来源标注为「平台原创题」,共 45 题:数学 12 / 408 18 / 英语 10 / 政治 5。
全部为原创编写,不含任何版权材料;公式类均经过手工验算。
"""
TODAY = "2026-10-25"

ORIG = []


def q(subject, question_md, options, answer, exp, qtype="选择", diff=3, year=None):
    ORIG.append({
        "subject": subject, "source_type": "自录题",
        "qtype": qtype, "year": year, "question_md": question_md,
        "options": options, "answer": answer, "solution_md": exp,
        "source_desc": "平台原创题(人工编写与核验)",
        "copyright_status": "自述/本人记录", "difficulty": diff,
    })


# ================= 数学一(12) =================
q("math", "设 $f(x)$ 在 $x=0$ 处可导,且 $f(0)=0$,$\\lim_{x\\to 0}\\dfrac{f(x)}{x}=2$,则 $f'(0)$ 等于?",
  ["0", "1", "2", "不存在"], "C",
  "$f'(0)=\\lim_{x\\to0}\\frac{f(x)-f(0)}{x-0}=\\lim_{x\\to0}\\frac{f(x)}{x}=2$。", diff=2)
q("math", "函数 $f(x)=|x|$ 在 $x=0$ 处?",
  ["连续且可导", "连续但不可导", "可导但不连续", "不连续"], "B",
  "左右导数分别为 -1 与 1,不相等,故不可导;但 $\\lim_{x\\to0}|x|=0=f(0)$,连续。", diff=1)
q("math", "$\\lim_{x\\to 0^+} x\\ln x$ 的值为?",
  ["$0$", "$1$", "$-\\infty$", "$+\\infty$"], "A",
  "$x\\ln x=\\frac{\\ln x}{1/x}$,洛必达得 $\\frac{1/x}{-1/x^2}=-x\\to 0$。", diff=2)
q("math", "若级数 $\\sum a_n$ 收敛而 $\\sum b_n$ 发散,则 $\\sum(a_n+b_n)$?",
  ["必收敛", "必发散", "可能收敛也可能发散", "绝对收敛"], "B",
  "若 $\\sum(a_n+b_n)$ 收敛,则 $\\sum b_n=\\sum(a_n+b_n)-\\sum a_n$ 收敛,矛盾。", diff=2)
q("math", "矩阵 $A$ 可逆的充要条件是?",
  ["$A$ 的行列式非零", "$A$ 是对称矩阵", "$A$ 的迹非零", "$A$ 的所有元素非零"], "A",
  "$A^{-1}$ 存在 $\\iff \\det A \\neq 0$。B/C/D 均既不充分也不必要。", diff=1)
q("math", "设 $A$ 为 $n$ 阶实对称矩阵,则下列说法错误的是?",
  ["$A$ 的特征值全是实数", "$A$ 必可对角化", "$A$ 的不同特征值的特征向量正交",
   "$A$ 的特征值必定互不相同"], "D",
  "实对称矩阵特征值为实数、必可正交对角化、不同特征值特征向量正交;但特征值可以有重根,例如单位矩阵。", diff=2)
q("math", "设随机变量 $X\\sim B(n,p)$,则 $D(X)$ 等于?",
  ["$np$", "$np(1-p)$", "$p(1-p)$", "$n^2p(1-p)$"], "B",
  "二项分布期望 $np$,方差 $np(1-p)$。注意 $E(X)=np$ 是干扰项。", diff=1)
q("math", "设 $X$ 与 $Y$ 相互独立,$D(X)=2$,$D(Y)=3$,则 $D(2X-Y)$ 等于?",
  ["1", "5", "11", "7"], "C",
  "独立时 $D(2X-Y)=4D(X)+D(Y)=4\\times2+3=11$(方差不服从线性性,系数要平方)。", diff=3)
q("math", "$\\int_{-1}^{1} x^3 \\cos x \\,dx$ 的值为?",
  ["$2\\int_0^1 x^3\\cos x\\,dx$", "0", "$2\\sin 1$", "$2\\cos 1$"], "B",
  "$x^3\\cos x$ 是奇函数,对称区间上积分为 0。", diff=2)
q("math", "交换 $\\int_0^1\\int_{y}^{1} f(x,y)\\,dx\\,dy$ 的积分次序后为?",
  ["$\\int_0^1\\int_0^{x} f\\,dy\\,dx$", "$\\int_0^1\\int_x^1 f\\,dy\\,dx$",
   "$\\int_0^1\\int_0^1 f\\,dy\\,dx$", "$\\int_0^1\\int_{1-x}^{1} f\\,dy\\,dx$"], "A",
  "原区域 $0\\le y\\le x\\le 1$,交换后先 $y$ 从 0 到 $x$,再 $x$ 从 0 到 1。", diff=3)
q("math", "向量组 $\\alpha_1=(1,2)$,$\\alpha_2=(2,4)$ 的秩为?",
  ["0", "1", "2", "不确定"], "B",
  "$\\alpha_2=2\\alpha_1$ 线性相关,极大无关组只含 1 个向量。", diff=1)
q("math", "设 $f(x)$ 连续,则 $\\dfrac{d}{dx}\\int_0^{x^2} f(t)\\,dt$ 等于?",
  ["$f(x^2)$", "$2x f(x^2)$", "$f(x)$", "$2x f(x)$"], "B",
  "变上限积分求导链式法则:$F'(x)=f(x^2)\\cdot(x^2)'=2x f(x^2)$。", diff=2)

# ================= 408(18) =================
q("cs408", "在一个长度为 n 的有序数组中进行折半查找,最坏情况下的时间复杂度为?",
  ["$O(n)$", "$O(\\log_2 n)$", "$O(n\\log_2 n)$", "$O(1)$"], "B",
  "每比较一次排除一半区间,最多比较 $\\lceil\\log_2(n+1)\\rceil$ 次。", diff=1)
q("cs408", "一棵有 n 个结点的二叉树,其叶结点个数为 n0,度为 2 的结点个数为 n2,则 n0 与 n2 的关系是?",
  ["$n_0=n_2+1$", "$n_0=n_2-1$", "$n_0=2n_2$", "无确定关系"], "A",
  "由结点数与度数关系 $n_0+n_1+n_2=n$ 与 $n=n_1+2n_2+1$ 联立得 $n_0=n_2+1$。", diff=2)
q("cs408", "在哈夫曼树中,若叶结点(权值)个数为 n,则树中总结点数为?",
  ["$2n$", "$2n-1$", "$2n+1$", "$n+1$"], "B",
  "哈夫曼树没有度为 1 的结点,n 个叶结点合并 n-1 次产生 n-1 个内部结点,共 2n-1。", diff=2)
q("cs408", "对含有 n 个元素的完全二叉堆(大根堆)执行一次删除堆顶操作的时间复杂度为?",
  ["$O(1)$", "$O(\\log_2 n)$", "$O(n)$", "$O(n\\log_2 n)$"], "B",
  "堆顶出堆后,末元素下沉,最多经过树高 $\\lfloor\\log_2 n\\rfloor$ 次交换。", diff=1)
q("cs408", "快速排序在下列哪种输入下性能最接近其最坏情况?",
  ["随机打乱的数组", "已经升序的数组(取首元素为主元)", "元素全部相等的数组(三向分区)", "大小交替的数组"], "B",
  "有序输入+首元素主元导致每次划分极不平衡,$O(n^2)$。三向分区处理全等数组是 $O(n)$。", diff=2)
q("cs408", "拓扑排序只能作用于?",
  ["任何有向图", "无环有向图", "无向连通图", "带权图"], "B",
  "存在环时环上顶点无法排出先后;拓扑排序是 DAG 上按偏序线性化的过程。", diff=1)
q("cs408", "n 个顶点的无向完全图边数为?",
  ["$n(n-1)$", "$\\frac{n(n-1)}{2}$", "$n^2$", "$n-1$"], "B",
  "每对顶点连一条边,组合数 $C_n^2=n(n-1)/2$。注意有向完全图才是 $n(n-1)$。", diff=1)
q("cs408", "Dijkstra 算法不能正确求解带负权边的单源最短路,其根本原因是?",
  ["实现过于复杂", "贪心策略假设已确定的最短路径不会再被更短路径替代",
   "负权边导致图不连通", "队列无法存储负数"], "B",
  "Dijkstra 按非递减顺序确定各点最短路;负权边可能让后确定的点回过头来缩短已确定的路径,违背贪心前提。", diff=3)
q("cs408", "采用补码表示 8 位整数,其可表示的整数范围是?",
  ["$-128\\sim127$", "$-127\\sim127$", "$0\\sim255$", "$-128\\sim128$"], "A",
  "补码 8 位范围 $-2^7\\sim2^7-1$,负数比正数多一个。", diff=1)
q("cs408", "Cache 写策略中,write-through(写穿透)的特点是?",
  ["写 Cache 的同时写主存,一致性强但写开销大", "只写 Cache,替换时写回主存",
   "只写主存不写 Cache", "由硬件随机决定"], "A",
  "写穿透保证 Cache 与主存一致,但每次写都要访问主存;write-back(B 项)减少主存写但存在不一致窗口。", diff=2)
q("cs408", "IEEE 754 单精度浮点数的尾数位宽(不含隐含位)与阶码位宽分别是?",
  ["23 位与 8 位", "52 位与 11 位", "24 位与 7 位", "16 位与 8 位"], "A",
  "单精度 1+8+23;双精度 1+11+52(B 是双精度)。隐含的前导 1 不占位。", diff=2)
q("cs408", "指令流水线中,「结构相关」指的是?",
  ["数据尚未就绪引起的相关", "指令争用同一硬件资源引起的相关",
   "转移指令改变 PC 引起的相关", "寄存器命名冲突"], "B",
  "结构相关=资源冲突;数据相关=A;控制相关=C。", diff=2)
q("cs408", "信号量机制中,P 操作(wait)的语义是?",
  ["申请资源:值减 1,若结果小于 0 则阻塞", "释放资源:值加 1,若有等待者则唤醒",
   "读信号量值但不修改", "将信号量置 0"], "A",
  "P=down=wait(申请);V=up=signal(释放)。B 是 V 操作的语义。", diff=1)
q("cs408", "产生死锁的四个必要条件中,不包括?",
  ["互斥", "占有并等待", "可抢占(可剥夺)", "循环等待"], "C",
  "必要条件是不可抢占;「可抢占」恰恰是破坏死锁的手段之一。", diff=2)
q("cs408", "LRU 页面置换算法淘汰的是?",
  ["最近最少使用的页面", "最先进入内存的页面", "最长时间未被访问的页面", "随机页面"], "A",
  "LRU=Least Recently Used。B 是 FIFO;C 的表述与 A 等价但标准名称是 LRU,本题选最准确说法 A。", diff=1)
q("cs408", "TCP 三次握手中,第二次握手报文携带的标志位是?",
  ["SYN", "ACK", "SYN+ACK", "FIN"], "C",
  "服务端以 SYN+ACK 同时确认客户端并同步自身序号。", diff=1)
q("cs408", "主机 IP 为 192.168.1.100/26,其所在子网的广播地址是?",
  ["192.168.1.127", "192.168.1.255", "192.168.1.63", "192.168.1.64"], "A",
  "/26 块大小 64;100 位于 64–127 块,网络地址 64,广播地址 127。", diff=3)
q("cs408", "在 OSI 参考模型中,路由器主要工作在?",
  ["物理层", "数据链路层", "网络层", "传输层"], "C",
  "路由器基于 IP(网络层)地址转发;交换机工作在数据链路层。", diff=1)

# ================= 英语一(10) =================
q("english", "Choose the word closest in meaning to \"abundant\":",
  ["scarce", "plentiful", "barren", "vague"], "B",
  "abundant = 大量的、丰富的,与 plentiful 同义;scarce(稀缺)反义;barren(贫瘠);vague(模糊)。", diff=1)
q("english", "\"The evidence is compelling.\" 中 compelling 最接近:",
  ["unconvincing", "convincing", "irrelevant", "confidential"], "B",
  "compelling evidence = 令人信服的证据。unconvincing 是反义干扰。", diff=1)
q("english", "选词填空:She ___ her success to years of hard work.",
  ["contributed", "attributed", "devoted", "dedicated"], "B",
  "attribute A to B 把 A 归因于 B。contribute to 直接接宾语;devote/dedicate to 表示献身于。", diff=2)
q("english", "选词填空:The new policy will take ___ next month.",
  ["affect", "effect", "effort", "afford"], "B",
  "take effect 生效(名词);affect 是动词「影响」。", diff=2)
q("english", "\"Not until yesterday did he realize the mistake.\" 该句使用的语法结构是:",
  ["强调句", "部分倒装", "虚拟语气", "省略句"], "B",
  "not until 置于句首,主句需部分倒装(did he realize)。", diff=2)
q("english", "选出正确的虚拟语气:If I ___ you, I would accept the offer.",
  ["am", "was", "were", "be"], "C",
  "与现在事实相反的虚拟条件句,be 动词一律用 were。", diff=1)
q("english", "\"The book, which was written in 1990, still sells well.\" 定语从句中 which 指代:",
  ["1990", "The book", "sells well", "整个主句"], "B",
  "非限制性定语从句的 which 指代先行词 The book。", diff=1)
q("english", "选词填空:He is indifferent ___ criticism.",
  ["of", "to", "with", "for"], "B",
  "be indifferent to 对…漠不关心,固定搭配。", diff=2)
q("english", "\"Were it not for your help, we would have failed.\" 该句省略了:",
  ["if", "that", "which", "when"], "A",
  "虚拟条件句省略 if 后需倒装:Were it not for... = If it were not for...", diff=3)
q("english", "选词填空:The manager ___ the report before the meeting started.",
  ["has reviewed", "had reviewed", "reviews", "is reviewing"], "B",
  "「会议开始前已完成」——过去之过去,用过去完成时 had reviewed。", diff=2)

# ================= 政治(5) =================
q("politics", "马克思主义哲学认为,世界的本原是?",
  ["物质", "精神", "实践", "运动"], "A",
  "唯物主义一元论主张物质第一性、意识第二性,物质是世界的本原。", diff=1)
q("politics", "矛盾的两种基本属性是?",
  ["普遍性与特殊性", "同一性与斗争性", "绝对性与相对性", "必然性与偶然性"], "B",
  "同一性与斗争性是矛盾自身的两种基本属性;A 是矛盾问题的精髓,注意区分。", diff=2)
q("politics", "实践是检验真理的唯一标准,其根本原因是?",
  ["实践具有直接现实性", "实践具有客观物质性", "实践具有社会历史性", "真理具有绝对性"], "A",
  "实践能把主观认识变为客观现实,通过对照结果直接检验认识是否正确,即直接现实性。", diff=2)
q("politics", "社会存在与社会意识的关系是?",
  ["社会意识决定社会存在", "社会存在决定社会意识,社会意识具有相对独立性",
   "二者互相决定", "二者没有关系"], "B",
  "历史唯物主义:社会存在决定社会意识;社会意识相对独立并可反作用于社会存在。", diff=1)
q("politics", "新民主主义革命的领导阶级是?",
  ["农民阶级", "民族资产阶级", "无产阶级", "小资产阶级"], "C",
  "新民主主义革命由无产阶级(经由中国共产党)领导,这是区别于旧民主主义革命的根本标志。", diff=1)


def seed_original_questions(store):
    """导入原创题(幂等:按哈希去重)。返回新增数。"""
    from app import questionbank as QB
    valid, _report = QB.import_questions(ORIG)
    existing = {q["content_hash"] for q in store.load("questions")}
    added = 0
    for v in valid:
        if v["content_hash"] in existing:
            continue
        items = store.load("questions")
        items.append(QB.new_question_record(v, len(items) + 1))
        store.save("questions", items)
        existing.add(v["content_hash"])
        added += 1
    return added
