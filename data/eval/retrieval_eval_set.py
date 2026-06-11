"""检索精度评估集

50条标注query + 期望类别/概念，支持κ值计算。
评估集覆盖9领域×3类型(精确/模糊/跨领域)。
"""

EVAL_QUERIES = [
    # === 气功 (6) ===
    {"id": "q001", "query": "混元气的本质是什么", "category": "气功", "type": "精确",
     "expected_concepts": ["混元气"], "expected_categories": ["气功", "哲学"]},
    {"id": "q002", "query": "练功时杂念很多怎么办", "category": "气功", "type": "模糊",
     "expected_concepts": ["调心", "运用意识"], "expected_categories": ["气功", "心理学"]},
    {"id": "q003", "query": "气功与中医经络的关系", "category": "气功", "type": "跨领域",
     "expected_concepts": ["经络", "气血"], "expected_categories": ["气功", "中医"]},
    {"id": "q004", "query": "捧气贯顶法的要领", "category": "气功", "type": "精确",
     "expected_concepts": ["捧气贯顶"], "expected_categories": ["气功"]},
    {"id": "q005", "query": "形神庄功法详解", "category": "气功", "type": "精确",
     "expected_concepts": ["形神庄"], "expected_categories": ["气功", "武术"]},
    {"id": "q006", "query": "组场的科学原理", "category": "气功", "type": "跨领域",
     "expected_concepts": ["组场"], "expected_categories": ["气功", "科学"]},

    # === 中医 (6) ===
    {"id": "q007", "query": "五脏六腑的功能", "category": "中医", "type": "精确",
     "expected_concepts": ["脏腑"], "expected_categories": ["中医"]},
    {"id": "q008", "query": "体质虚寒如何调理", "category": "中医", "type": "模糊",
     "expected_concepts": ["寒热", "虚实"], "expected_categories": ["中医"]},
    {"id": "q009", "query": "中医与哲学阴阳五行", "category": "中医", "type": "跨领域",
     "expected_concepts": ["阴阳五行", "五行"], "expected_categories": ["中医", "哲学", "道家"]},
    {"id": "q010", "query": "针灸治疗的基本原理", "category": "中医", "type": "精确",
     "expected_concepts": ["针灸", "穴位", "经络"], "expected_categories": ["中医"]},
    {"id": "q011", "query": "中药四气五味", "category": "中医", "type": "精确",
     "expected_concepts": ["本草"], "expected_categories": ["中医"]},
    {"id": "q012", "query": "治未病的理念和实践", "category": "中医", "type": "模糊",
     "expected_concepts": ["治未病"], "expected_categories": ["中医", "哲学"]},

    # === 儒家 (6) ===
    {"id": "q013", "query": "仁义礼智信的含义", "category": "儒家", "type": "精确",
     "expected_concepts": ["仁", "义", "礼"], "expected_categories": ["儒家", "哲学"]},
    {"id": "q014", "query": "如何修身齐家", "category": "儒家", "type": "模糊",
     "expected_concepts": ["修身"], "expected_categories": ["儒家", "道家"]},
    {"id": "q015", "query": "儒家思想对现代教育的影响", "category": "儒家", "type": "跨领域",
     "expected_concepts": ["修身", "中庸"], "expected_categories": ["儒家", "哲学"]},
    {"id": "q016", "query": "中庸之道的人生智慧", "category": "儒家", "type": "精确",
     "expected_concepts": ["中庸"], "expected_categories": ["儒家", "哲学"]},
    {"id": "q017", "query": "论语中关于学习的论述", "category": "儒家", "type": "精确",
     "expected_concepts": ["论语"], "expected_categories": ["儒家", "哲学"]},
    {"id": "q018", "query": "儒家伦理与现代价值观", "category": "儒家", "type": "跨领域",
     "expected_concepts": ["伦理"], "expected_categories": ["儒家", "哲学"]},

    # === 佛家 (6) ===
    {"id": "q019", "query": "四圣谛八正道", "category": "佛家", "type": "精确",
     "expected_concepts": ["觉悟"], "expected_categories": ["佛家", "哲学"]},
    {"id": "q020", "query": "禅修入门方法", "category": "佛家", "type": "模糊",
     "expected_concepts": ["禅定", "正念"], "expected_categories": ["佛家", "气功", "心理学"]},
    {"id": "q021", "query": "佛教与心理学正念", "category": "佛家", "type": "跨领域",
     "expected_concepts": ["正念", "冥想"], "expected_categories": ["佛家", "心理学"]},
    {"id": "q022", "query": "金刚经的核心思想", "category": "佛家", "type": "精确",
     "expected_concepts": ["金刚经"], "expected_categories": ["佛家", "哲学"]},
    {"id": "q023", "query": "六祖坛经的禅宗思想", "category": "佛家", "type": "精确",
     "expected_concepts": ["坛经", "觉悟"], "expected_categories": ["佛家", "哲学"]},
    {"id": "q024", "query": "佛家慈悲与儒家仁的对比", "category": "佛家", "type": "跨领域",
     "expected_concepts": ["仁", "心性"], "expected_categories": ["佛家", "儒家", "哲学"]},

    # === 道家 (6) ===
    {"id": "q025", "query": "道德经第一章解读", "category": "道家", "type": "精确",
     "expected_concepts": ["道德经", "道"], "expected_categories": ["道家", "哲学"]},
    {"id": "q026", "query": "无为而治在管理中的应用", "category": "道家", "type": "模糊",
     "expected_concepts": ["无为"], "expected_categories": ["道家", "哲学"]},
    {"id": "q027", "query": "道家养生与气功", "category": "道家", "type": "跨领域",
     "expected_concepts": ["养生", "丹田"], "expected_categories": ["道家", "气功", "中医"]},
    {"id": "q028", "query": "庄子逍遥游的哲学意蕴", "category": "道家", "type": "精确",
     "expected_concepts": ["庄子"], "expected_categories": ["道家", "哲学"]},
    {"id": "q029", "query": "小周天功法详解", "category": "道家", "type": "精确",
     "expected_concepts": ["小周天", "任督二脉"], "expected_categories": ["道家", "气功"]},
    {"id": "q030", "query": "道家内丹术修炼方法", "category": "道家", "type": "模糊",
     "expected_concepts": ["精气神", "丹田"], "expected_categories": ["道家", "气功"]},

    # === 武术 (6) ===
    {"id": "q031", "query": "太极拳的基本功法", "category": "武术", "type": "精确",
     "expected_concepts": ["太极拳", "太极"], "expected_categories": ["武术", "道家", "气功"]},
    {"id": "q032", "query": "如何提高武术实战能力", "category": "武术", "type": "模糊",
     "expected_concepts": ["内功"], "expected_categories": ["武术", "气功"]},
    {"id": "q033", "query": "武术与中医筋骨理论", "category": "武术", "type": "跨领域",
     "expected_concepts": ["气血", "经络"], "expected_categories": ["武术", "中医"]},
    {"id": "q034", "query": "八卦掌的步法特点", "category": "武术", "type": "精确",
     "expected_concepts": ["八卦掌"], "expected_categories": ["武术", "道家"]},
    {"id": "q035", "query": "易筋经功法详解", "category": "武术", "type": "精确",
     "expected_concepts": ["易筋经"], "expected_categories": ["武术", "气功", "中医"]},
    {"id": "q036", "query": "武术内功与气功的关系", "category": "武术", "type": "跨领域",
     "expected_concepts": ["内功", "精气神"], "expected_categories": ["武术", "气功", "道家"]},

    # === 哲学 (5) ===
    {"id": "q037", "query": "存在主义的核心观点", "category": "哲学", "type": "精确",
     "expected_concepts": ["存在主义"], "expected_categories": ["哲学", "心理学"]},
    {"id": "q038", "query": "意识与物质的关系", "category": "哲学", "type": "模糊",
     "expected_concepts": ["意识", "本体论"], "expected_categories": ["哲学", "科学"]},
    {"id": "q039", "query": "中西方哲学比较", "category": "哲学", "type": "跨领域",
     "expected_concepts": ["辩证", "逻辑"], "expected_categories": ["哲学"]},
    {"id": "q040", "query": "易经的哲学思想", "category": "哲学", "type": "精确",
     "expected_concepts": ["易经", "阴阳"], "expected_categories": ["哲学", "道家", "儒家"]},
    {"id": "q041", "query": "天人合一思想的现代意义", "category": "哲学", "type": "跨领域",
     "expected_concepts": ["天人合一"], "expected_categories": ["哲学", "道家", "儒家", "中医"]},

    # === 科学 (5) ===
    {"id": "q042", "query": "量子力学基本原理", "category": "科学", "type": "精确",
     "expected_concepts": ["量子"], "expected_categories": ["科学", "哲学"]},
    {"id": "q043", "query": "人工智能的发展趋势", "category": "科学", "type": "模糊",
     "expected_concepts": ["认知", "思维"], "expected_categories": ["科学"]},
    {"id": "q044", "query": "科学与哲学的认识论", "category": "科学", "type": "跨领域",
     "expected_concepts": ["认识论", "方法论"], "expected_categories": ["科学", "哲学"]},
    {"id": "q045", "query": "系统论与复杂系统", "category": "科学", "type": "精确",
     "expected_concepts": ["系统论", "复杂系统"], "expected_categories": ["科学", "哲学"]},
    {"id": "q046", "query": "脑科学与意识研究", "category": "科学", "type": "跨领域",
     "expected_concepts": ["脑科学", "意识"], "expected_categories": ["科学", "心理学", "哲学"]},

    # === 心理学 (4) ===
    {"id": "q047", "query": "认知行为疗法CBT原理", "category": "心理学", "type": "精确",
     "expected_concepts": ["认知行为", "认知"], "expected_categories": ["心理学", "科学"]},
    {"id": "q048", "query": "如何缓解焦虑情绪", "category": "心理学", "type": "模糊",
     "expected_concepts": ["情绪", "压力", "放松"], "expected_categories": ["心理学", "气功"]},
    {"id": "q049", "query": "心理学与佛学冥想", "category": "心理学", "type": "跨领域",
     "expected_concepts": ["冥想", "正念"], "expected_categories": ["心理学", "佛家", "气功"]},
    {"id": "q050", "query": "正念减压疗法MBSR", "category": "心理学", "type": "精确",
     "expected_concepts": ["正念减压", "正念"], "expected_categories": ["心理学", "佛家"]},
]

assert len(EVAL_QUERIES) == 50, f"Expected 50 queries, got {len(EVAL_QUERIES)}"
