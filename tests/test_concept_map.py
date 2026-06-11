from backend.services.knowledge_graph.concept_map import (
    NINE_DOMAINS,
    CONCEPT_DOMAIN_MAP,
    get_concept_info,
    get_cross_domain_concepts,
    get_related_domains,
)


class TestNineDomains:
    def test_count(self):
        assert len(NINE_DOMAINS) == 9

    def test_members(self):
        expected = {"儒家", "佛家", "道家", "中医", "武术", "哲学", "科学", "气功", "心理学"}
        assert set(NINE_DOMAINS) == expected


class TestConceptDomainMap:
    def test_all_values_are_lists(self):
        for concept, domains in CONCEPT_DOMAIN_MAP.items():
            assert isinstance(domains, list), f"{concept} has non-list value"
            assert len(domains) >= 1, f"{concept} has empty domains"

    def test_all_domains_valid(self):
        valid = set(NINE_DOMAINS)
        for concept, domains in CONCEPT_DOMAIN_MAP.items():
            for d in domains:
                assert d in valid, f"{concept} references invalid domain '{d}'"

    def test_no_duplicate_domains(self):
        for concept, domains in CONCEPT_DOMAIN_MAP.items():
            assert len(domains) == len(set(domains)), f"{concept} has duplicate domains"

    def test_key_concepts_exist(self):
        must_have = ["意元体", "自觉智能", "混元气", "阴阳", "气", "太极", "意识"]
        for c in must_have:
            assert c in CONCEPT_DOMAIN_MAP, f"missing key concept: {c}"


class TestGetRelatedDomains:
    def test_single_concept(self):
        result = get_related_domains("阴阳")
        assert "中医" in result
        assert "哲学" in result

    def test_multi_concept(self):
        result = get_related_domains("意元体和自觉智能")
        assert "气功" in result
        assert "哲学" in result
        assert "心理学" in result

    def test_no_match(self):
        result = get_related_domains("这是一个普通的查询xyz")
        assert result == []

    def test_returns_domain_order(self):
        result = get_related_domains("丹田")
        for d in result:
            assert d in NINE_DOMAINS


class TestGetConceptInfo:
    def test_single_match(self):
        info = get_concept_info("什么是意元体")
        names = [m["concept"] for m in info]
        assert "意元体" in names

    def test_multi_match(self):
        info = get_concept_info("混元气与意元体的关系")
        names = [m["concept"] for m in info]
        assert "混元气" in names
        assert "意元体" in names

    def test_cross_domain_flag(self):
        info = get_concept_info("意元体")
        match = next(m for m in info if m["concept"] == "意元体")
        assert match["cross_domain"] is True
        assert len(match["domains"]) > 1

    def test_single_domain_flag(self):
        info = get_concept_info("伤寒")
        match = next(m for m in info if m["concept"] == "伤寒")
        assert match["cross_domain"] is False

    def test_no_match(self):
        info = get_concept_info("xyz123")
        assert info == []


class TestGetCrossDomainConcepts:
    def test_qigong_has_many(self):
        concepts = get_cross_domain_concepts("气功")
        names = [c for c, _ in concepts]
        assert "意元体" in names
        assert len(concepts) > 5

    def test_single_domain_concepts_excluded(self):
        concepts = get_cross_domain_concepts("中医")
        for _, domains in concepts:
            assert "中医" in domains
            assert len(domains) > 1

    def test_nonexistent_domain(self):
        concepts = get_cross_domain_concepts("不存在的领域")
        assert concepts == []
