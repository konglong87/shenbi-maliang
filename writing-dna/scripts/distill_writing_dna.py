#!/usr/bin/env python3
"""
Writing DNA Distiller
融合认知蒸馏方法论：七维并行采集 + 三重验证 + 增量更新

使用方式：
  # 全量蒸馏（首次）
  python3 distill_writing_dna.py <文章目录或文件列表>

  # 增量更新（已有DNA档案，追加新文章）
  python3 distill_writing_dna.py --incremental <新文章目录>

  # 查看当前特征库统计
  python3 distill_writing_dna.py --stats

支持格式：.txt  .md  .html（自动提取正文）

输出：
  - 控制台三重验证报告
  - data/features/feature_pool.json（特征库）
  - 可提供给 AI 生成 references/my-writing-dna.md
"""

import sys
import os
import re
import json
import yaml
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Optional, Tuple


# ─── 配置加载 ─────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent  # skill 根目录
CONFIG_PATH = SKILL_DIR / "config.yaml"


def load_config() -> Dict:
    """加载 config.yaml，不存在则返回默认配置"""
    defaults = {
        "validation": {"frequency_threshold": 3, "context_consistency_ratio": 0.6, "conflict_strategy": "flag"},
        "confidence": {"high_threshold": 5, "medium_threshold": 2},
        "collector": {"min_segment_length": 100, "word_min_frequency_per_article": 3,
                      "catchphrase_total_threshold": 10, "metaphor_high_density": 3,
                      "short_paragraph_threshold": 50},
        "incremental": {"enabled": True, "merge_strategy": "accumulate"},
        "anti_pattern": {"negative_catchphrase_threshold": 15, "logic_flaw_threshold": 3},
        "output": {"dna_output_path": "references/my-writing-dna.md",
                   "features_path": "data/features/",
                   "include_source_reference": True,
                   "export_features_json": True,
                   "features_json_path": "data/features/feature_pool.json"},
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            # 合并配置（用户配置覆盖默认值）
            for section, values in user_cfg.items():
                if section in defaults and isinstance(values, dict):
                    defaults[section].update(values)
            return defaults
        except Exception:
            pass
    return defaults


CFG = load_config()


# ─── 文本加载与预处理 ─────────────────────────────────────────────────────────

def load_text(filepath: str) -> str:
    """加载文件内容，自动处理 HTML"""
    path = Path(filepath)
    content = path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() in (".html", ".htm"):
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        content = re.sub(r"<[^>]+>", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
    elif path.suffix.lower() == ".md":
        # 保留 MD 内容但去掉标题标记
        content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)

    return content.strip()


def collect_articles(inputs: List[str]) -> List[Dict]:
    """从文件/目录收集所有文章"""
    articles = []
    idx = 1
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            for ext in ("*.txt", "*.md", "*.html", "*.htm"):
                for f in sorted(p.glob(ext)):
                    text = load_text(str(f))
                    if len(text) > 200:
                        articles.append({
                            "id": f"Article-{idx:02d}",
                            "filename": f.name,
                            "text": text,
                            "hash": hashlib.md5(text.encode()).hexdigest()[:8],
                        })
                        idx += 1
        elif p.is_file():
            text = load_text(str(p))
            if len(text) > 200:
                articles.append({
                    "id": f"Article-{idx:02d}",
                    "filename": p.name,
                    "text": text,
                    "hash": hashlib.md5(text.encode()).hexdigest()[:8],
                })
                idx += 1
    return articles


def split_sentences(text: str) -> List[str]:
    """按中文标点分割句子"""
    sentences = re.split(r"[。！？…]+", text)
    return [s.strip() for s in sentences if len(s.strip()) >= 3]


def split_paragraphs(text: str) -> List[str]:
    """按空行分割段落"""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if len(p.strip()) >= 10]


def split_segments(text: str, min_len: int = None) -> List[str]:
    """话题语义切片：按自然段+长度阈值切分"""
    min_len = min_len or CFG["collector"]["min_segment_length"]
    paragraphs = split_paragraphs(text)
    segments = []
    buffer = ""
    for p in paragraphs:
        buffer += " " + p
        if len(buffer) >= min_len:
            segments.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        segments.append(buffer.strip())
    return segments


# ─── 七路特征采集器 ───────────────────────────────────────────────────────────

class FeatureCollector:
    """七维特征采集器基类"""

    def __init__(self, dimension: str):
        self.dimension = dimension

    def collect(self, article: Dict) -> List[Dict]:
        """返回特征列表，每条特征包含 {key, value, source_id, raw_evidence}"""
        raise NotImplementedError


class ExpressionCollector(FeatureCollector):
    """维度1：表达范式采集"""

    COLLOQUIAL_MARKERS = [
        "其实", "真的", "说真的", "你知道吗", "你有没有", "想想看", "说实话",
        "哈", "嘛", "吧", "诶", "嗯", "哦", "啊", "哟", "呢",
        "反正", "就是说", "对吧", "对不对", "是不是", "怎么说呢",
        "说白了", "不得不说", "我觉得", "感觉", "有点", "蛮", "挺",
    ]

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        features = []

        # 句长分析
        sentences = split_sentences(text)
        if sentences:
            lengths = [len(s) for s in sentences]
            avg = sum(lengths) / len(lengths)
            features.append({
                "key": "avg_sentence_length",
                "value": round(avg, 1),
                "source_id": src,
                "raw_evidence": f"基于{len(sentences)}个句子",
                "dimension": self.dimension,
            })

        # 口语化词统计
        for marker in self.COLLOQUIAL_MARKERS:
            count = text.count(marker)
            if count >= CFG["collector"]["word_min_frequency_per_article"]:
                features.append({
                    "key": f"colloquial_word:{marker}",
                    "value": count,
                    "source_id": src,
                    "raw_evidence": f"出现{count}次",
                    "dimension": self.dimension,
                })

        # 短段落（爆破段）检测
        paras = split_paragraphs(text)
        short_paras = [p for p in paras if len(p) < CFG["collector"]["short_paragraph_threshold"]]
        features.append({
            "key": "short_paragraph_ratio",
            "value": round(len(short_paras) / max(len(paras), 1) * 100, 1),
            "source_id": src,
            "raw_evidence": f"{len(short_paras)}/{len(paras)} 段为短段",
            "dimension": self.dimension,
        })

        return features


class ThinkingCollector(FeatureCollector):
    """维度2：思维逻辑采集"""

    OPENING_PATTERNS = {
        "场景代入型": r"(那天|那个|那年|走进|来到|记得那|有一次|有一天)",
        "问题悬念型": r"(你有没有|为什么|是什么让|有没有想过|你是否|凭什么)",
        "数据冲击型": r"(\d+%|\d+年|\d+个|研究表明|数据显示|调查发现)",
        "结论先行型": r"^(我认为|我觉得|我发现|最近|今天|这件事)",
        "故事钩子型": r"[我他她我们].{0,5}[去来看发现遇到感受经历]",
        "情绪共鸣型": r"(你是不是|你有没有|你会不会|你有时候|我们都)",
    }

    CLOSING_PATTERNS = {
        "行动召唤型": r"(试试|去做|开始|行动|现在就|你可以|建议你)",
        "开放留白型": r"(也许|或许|你觉得呢|不知道你|我不知道|值得思考)",
        "情感升华型": r"(终归|归根结底|本质上|生命|意义|更重要的是|最终)",
        "自我反思型": r"(我意识到|我明白了|这让我|让我重新|回头看)",
        "金句总结型": r"^.{10,40}[。！]$",
    }

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        features = []
        first_para = text[:200]
        last_para = text[-300:]

        for name, pattern in self.OPENING_PATTERNS.items():
            if re.search(pattern, first_para):
                features.append({
                    "key": f"opening_type:{name}",
                    "value": 1,
                    "source_id": src,
                    "raw_evidence": first_para[:80],
                    "dimension": self.dimension,
                })

        for name, pattern in self.CLOSING_PATTERNS.items():
            if re.search(pattern, last_para):
                features.append({
                    "key": f"closing_type:{name}",
                    "value": 1,
                    "source_id": src,
                    "raw_evidence": last_para[-80:],
                    "dimension": self.dimension,
                })

        return features


class KnowledgeCollector(FeatureCollector):
    """维度3：知识体系采集（词汇+领域）"""

    TOPIC_KEYWORDS = {
        "个人成长": ["成长", "习惯", "坚持", "自律", "改变", "目标", "努力"],
        "职场商业": ["工作", "职业", "商业", "创业", "产品", "团队", "效率"],
        "科技互联网": ["技术", "AI", "算法", "产品", "互联网", "代码", "数字"],
        "人际关系": ["关系", "沟通", "朋友", "爱", "家人", "边界", "信任"],
        "思维认知": ["思维", "认知", "逻辑", "框架", "本质", "规律", "底层"],
        "社会观察": ["社会", "时代", "趋势", "现象", "问题", "年轻人", "我们"],
    }

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        features = []

        for topic, keywords in self.TOPIC_KEYWORDS.items():
            count = sum(text.count(kw) for kw in keywords)
            if count >= 3:
                features.append({
                    "key": f"topic_domain:{topic}",
                    "value": count,
                    "source_id": src,
                    "raw_evidence": f"关键词命中共{count}次",
                    "dimension": self.dimension,
                })

        return features


class EmotionCollector(FeatureCollector):
    """维度4：情感决策采集"""

    FRIEND_MARKERS = ["你知道吗", "你有没有", "我觉得", "说真的", "我们", "你也"]
    MENTOR_MARKERS = ["建议你", "推荐你", "你可以", "不妨", "值得一试"]
    COLD_MARKERS = ["据我观察", "数据显示", "研究表明", "可以看出", "事实上"]
    SELF_MARKERS = ["我发现", "我意识到", "我经历", "那时我", "后来我才"]

    def _score(self, text: str, markers: List[str]) -> int:
        return sum(text.count(m) for m in markers)

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        scores = {
            "朋友感": self._score(text, self.FRIEND_MARKERS),
            "导师感": self._score(text, self.MENTOR_MARKERS),
            "记者感": self._score(text, self.COLD_MARKERS),
            "自我剖析感": self._score(text, self.SELF_MARKERS),
        }
        dominant = max(scores, key=scores.get)
        return [{
            "key": f"reader_relationship:{dominant}",
            "value": scores[dominant],
            "source_id": src,
            "raw_evidence": str(scores),
            "dimension": self.dimension,
        }]


class TopicAngleCollector(FeatureCollector):
    """维度5：选题视角采集（标题分析）"""

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        features = []

        # 取第一行作为标题候选
        first_line = text.split("\n")[0].strip()[:50]
        if 5 <= len(first_line) <= 30:
            has_number = bool(re.search(r"\d+", first_line))
            has_question = bool(re.search(r"[？?]", first_line))
            has_you = "你" in first_line

            if has_number:
                features.append({"key": "title_has_number", "value": 1, "source_id": src,
                                  "raw_evidence": first_line, "dimension": self.dimension})
            if has_question:
                features.append({"key": "title_has_question", "value": 1, "source_id": src,
                                  "raw_evidence": first_line, "dimension": self.dimension})
            if has_you:
                features.append({"key": "title_has_you", "value": 1, "source_id": src,
                                  "raw_evidence": first_line, "dimension": self.dimension})

        return features


class RhythmCollector(FeatureCollector):
    """维度6：节奏控制采集"""

    METAPHOR_PATTERNS = [r"就像", r"好比", r"犹如", r"如同", r"像.{1,10}一样", r"仿佛"]

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        features = []

        # 比喻密度
        total_chars = len(text)
        metaphor_count = sum(len(re.findall(p, text)) for p in self.METAPHOR_PATTERNS)
        density = round(metaphor_count / (total_chars / 1000), 2) if total_chars > 0 else 0
        features.append({
            "key": "metaphor_density",
            "value": density,
            "source_id": src,
            "raw_evidence": f"每千字{density}个比喻",
            "dimension": self.dimension,
        })

        return features


class AntiPatternCollector(FeatureCollector):
    """维度7：反模式采集 ⚠️"""

    FORMAL_CONCLUSIONS = ["总之", "综上所述", "由此可见", "总而言之", "综合来看", "综上"]
    LOGIC_FLAW_PATTERNS = [
        (r"所有.{2,8}都", "以偏概全倾向"),
        (r"因为.{2,20}所以.{2,20}一定", "因果过度推断"),
        (r"研究表明.{5,30}[。]", "权威引用但无来源"),
    ]

    def collect(self, article: Dict) -> List[Dict]:
        text = article["text"]
        src = article["id"]
        features = []

        # 负面口头禅候选（书面总结词）
        for word in self.FORMAL_CONCLUSIONS:
            count = text.count(word)
            if count >= 1:
                features.append({
                    "key": f"negative_catchphrase:{word}",
                    "value": count,
                    "source_id": src,
                    "raw_evidence": f'出现{count}次，书面总结词可能显得套路化',
                    "dimension": self.dimension,
                })

        # 逻辑漏洞模式
        for pattern, flaw_name in self.LOGIC_FLAW_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                features.append({
                    "key": f"logic_flaw:{flaw_name}",
                    "value": len(matches),
                    "source_id": src,
                    "raw_evidence": str(matches[:2]),
                    "dimension": self.dimension,
                })

        return features


# ─── 三重验证器 ───────────────────────────────────────────────────────────────

class TripleValidator:
    """三重验证：频次 + 一致性 + 逻辑自洽"""

    def __init__(self, config: Dict):
        self.freq_threshold = config["validation"]["frequency_threshold"]
        self.consistency_ratio = config["validation"]["context_consistency_ratio"]
        self.conflict_strategy = config["validation"]["conflict_strategy"]
        self.high_conf = config["confidence"]["high_threshold"]
        self.med_conf = config["confidence"]["medium_threshold"]

    def validate(self, raw_features: List[Dict], total_articles: int) -> Dict:
        """
        对原始特征池执行三重验证
        返回：{key: {value, sources, confidence, status, evidence}}
        """
        # 按 key 分组
        grouped = defaultdict(list)
        for f in raw_features:
            grouped[f["key"]].append(f)

        validated = {}
        rejected = []
        conflicts = []

        for key, instances in grouped.items():
            source_ids = list({i["source_id"] for i in instances})
            article_count = len(source_ids)
            total_value = sum(i["value"] for i in instances if isinstance(i["value"], (int, float)))

            # ── 验证一：频次验证 ──────────────────────────────
            if article_count < self.freq_threshold:
                rejected.append({
                    "key": key,
                    "reason": f"频次不足（出现{article_count}篇，阈值{self.freq_threshold}篇）",
                    "sources": source_ids,
                })
                continue

            # ── 验证二：语境一致性（简化：出现篇数/总篇数 > ratio）──
            consistency_score = article_count / total_articles
            if consistency_score < self.consistency_ratio:
                status = "[待确认]"
            else:
                status = "稳定"

            # ── 验证三：逻辑自洽（检查与已有验证特征的冲突）──────
            # 简化实现：同一类型特征值差异过大时标记冲突
            if len(instances) > 1:
                values = [i["value"] for i in instances if isinstance(i["value"], (int, float))]
                if values and max(values) > min(values) * 5:  # 极端差异
                    if self.conflict_strategy == "flag":
                        status = "[冲突]"
                    elif self.conflict_strategy == "reject":
                        conflicts.append({"key": key, "reason": "数值差异过大"})
                        continue

            # ── 置信度评定 ────────────────────────────────────
            if article_count >= self.high_conf:
                confidence = "★★★"
                rule_type = "硬规则候选"
            elif article_count >= self.med_conf:
                confidence = "★★"
                rule_type = "软范式候选"
            else:
                confidence = "★"
                rule_type = "[待确认]"

            validated[key] = {
                "total_value": round(total_value, 2),
                "article_count": article_count,
                "sources": source_ids,
                "confidence": confidence,
                "rule_type": rule_type,
                "status": status,
                "dimension": instances[0].get("dimension", "unknown"),
                "evidence_samples": [i["raw_evidence"] for i in instances[:2]],
            }

        return {
            "validated": validated,
            "rejected_count": len(rejected),
            "conflict_count": len(conflicts),
            "rejected": rejected[:10],  # 只显示前10条被拒记录
        }


# ─── 特征聚合与报告输出 ───────────────────────────────────────────────────────

def aggregate_results(validation_result: Dict, articles: List[Dict]) -> Dict:
    """聚合验证后的特征，生成结构化摘要"""
    validated = validation_result["validated"]
    n = len(articles)

    # 按维度分组
    by_dimension = defaultdict(dict)
    for key, feature in validated.items():
        dim = feature["dimension"]
        by_dimension[dim][key] = feature

    # 提取关键统计
    # 句长趋势
    sentence_lengths = [f["total_value"] / f["article_count"]
                        for k, f in validated.items()
                        if k == "avg_sentence_length"]
    avg_sentence = round(sum(sentence_lengths) / len(sentence_lengths), 1) if sentence_lengths else None

    # 开头类型投票
    opening_votes = {k.replace("opening_type:", ""): v["article_count"]
                     for k, v in validated.items() if k.startswith("opening_type:")}

    # 结尾类型投票
    closing_votes = {k.replace("closing_type:", ""): v["article_count"]
                     for k, v in validated.items() if k.startswith("closing_type:")}

    # 口头禅候选
    catchphrases = {k.replace("colloquial_word:", ""): v
                    for k, v in validated.items() if k.startswith("colloquial_word:")}

    # 话题领域
    topics = {k.replace("topic_domain:", ""): v
              for k, v in validated.items() if k.startswith("topic_domain:")}

    # 反模式
    negative_catchphrases = {k.replace("negative_catchphrase:", ""): v
                              for k, v in validated.items() if k.startswith("negative_catchphrase:")}
    logic_flaws = {k.replace("logic_flaw:", ""): v
                   for k, v in validated.items() if k.startswith("logic_flaw:")}

    return {
        "summary": {
            "articles_analyzed": n,
            "avg_sentence_length": avg_sentence,
            "dominant_opening": max(opening_votes, key=opening_votes.get) if opening_votes else "未识别",
            "dominant_closing": max(closing_votes, key=closing_votes.get) if closing_votes else "未识别",
        },
        "hard_rule_candidates": {k: v for k, v in validated.items() if v["confidence"] == "★★★"},
        "soft_paradigm_candidates": {k: v for k, v in validated.items() if v["confidence"] == "★★"},
        "pending_review": {k: v for k, v in validated.items() if v["confidence"] == "★"},
        "catchphrases": catchphrases,
        "topics": topics,
        "anti_patterns": {
            "negative_catchphrases": negative_catchphrases,
            "logic_flaws": logic_flaws,
        },
        "opening_votes": opening_votes,
        "closing_votes": closing_votes,
        "by_dimension": dict(by_dimension),
        "validation_stats": {
            "total_validated": len(validated),
            "rejected": validation_result["rejected_count"],
            "conflicts": validation_result["conflict_count"],
        },
    }


def print_report(result: Dict):
    """打印三重验证报告"""
    s = result["summary"]
    stats = result["validation_stats"]

    print("\n" + "═" * 65)
    print("🧬  Writing DNA 蒸馏报告 v2（三重验证 + 七维分析）")
    print("═" * 65)
    print(f"📊 分析文章数：{s['articles_analyzed']} 篇")
    print(f"✅ 通过验证特征：{stats['total_validated']} 条")
    print(f"❌ 被淘汰特征：{stats['rejected']} 条")
    print(f"⚡ 冲突特征：{stats['conflicts']} 条")

    print("\n── 🔴 硬规则候选（★★★ 置信，可直接作为写作指令）─────────")
    hard = result["hard_rule_candidates"]
    if hard:
        for key, val in list(hard.items())[:10]:
            print(f"  [{val['dimension']}] {key}: 出现{val['article_count']}篇 | {', '.join(val['sources'][:3])}")
    else:
        print("  （样本不足，暂无高置信硬规则）")

    print("\n── 🔵 软范式候选（★★ 置信，需 Few-shot 示例）──────────────")
    soft = result["soft_paradigm_candidates"]
    if soft:
        for key, val in list(soft.items())[:8]:
            print(f"  [{val['dimension']}] {key}: 出现{val['article_count']}篇")
    else:
        print("  （暂无中置信软范式，建议增加样本）")

    print("\n── 开头偏好 ─────────────────────────────────────────────────")
    for t, c in sorted(result["opening_votes"].items(), key=lambda x: -x[1]):
        print(f"  {t}：{c} 篇")

    print("\n── 结尾偏好 ─────────────────────────────────────────────────")
    for t, c in sorted(result["closing_votes"].items(), key=lambda x: -x[1]):
        print(f"  {t}：{c} 篇")

    print("\n── 高频话题领域 ─────────────────────────────────────────────")
    for t, v in sorted(result["topics"].items(), key=lambda x: -x[1]["article_count"]):
        print(f"  {t}：{v['article_count']} 篇文章涉及")

    print("\n── ⚠️  反模式档案 ────────────────────────────────────────────")
    ap = result["anti_patterns"]
    if ap["negative_catchphrases"]:
        print("  负面口头禅（可能本人不自知）：")
        for word, v in ap["negative_catchphrases"].items():
            print(f"    「{word}」出现 {v['article_count']} 篇")
    if ap["logic_flaws"]:
        print("  逻辑漏洞模式：")
        for flaw, v in ap["logic_flaws"].items():
            print(f"    {flaw}：{v['article_count']} 篇中出现")

    print("\n" + "═" * 65)
    print("✅ 蒸馏完成！将此报告提供给 AI，请求生成完整 DNA 档案：")
    print('   「根据这份蒸馏报告和 dna-template.md，为我生成写作 DNA 档案」')
    print("═" * 65 + "\n")


# ─── 增量模式 ─────────────────────────────────────────────────────────────────

def load_existing_features(features_json_path: str) -> List[Dict]:
    """加载已有特征库（用于增量合并）"""
    p = Path(features_json_path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_features(features: List[Dict], features_json_path: str):
    """保存特征库"""
    p = Path(features_json_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)
    print(f"📁 特征库已保存：{p}")


# ─── 主流程 ───────────────────────────────────────────────────────────────────

COLLECTORS = [
    ExpressionCollector("表达范式"),
    ThinkingCollector("思维逻辑"),
    KnowledgeCollector("知识体系"),
    EmotionCollector("情感决策"),
    TopicAngleCollector("选题视角"),
    RhythmCollector("节奏控制"),
    AntiPatternCollector("反模式"),
]


def run_distillation(articles: List[Dict], incremental_features: List[Dict] = None) -> Dict:
    """主蒸馏流程"""
    print(f"⏳ 七路并行采集中（{len(articles)} 篇文章）...")

    all_raw_features = []
    for article in articles:
        for collector in COLLECTORS:
            features = collector.collect(article)
            all_raw_features.extend(features)

    # 增量合并
    if incremental_features:
        print(f"🔀 合并已有特征库（{len(incremental_features)} 条历史特征）...")
        all_raw_features = incremental_features + all_raw_features

    print(f"📦 原始特征池：{len(all_raw_features)} 条 → 开始三重验证...")

    validator = TripleValidator(CFG)
    validation_result = validator.validate(all_raw_features, len(articles))
    result = aggregate_results(validation_result, articles)

    return result, all_raw_features


def main():
    incremental_mode = "--incremental" in sys.argv
    stats_mode = "--stats" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    features_json_path = SKILL_DIR / CFG["output"]["features_json_path"]

    if stats_mode:
        existing = load_existing_features(str(features_json_path))
        print(f"\n📊 当前特征库：{len(existing)} 条特征")
        dim_count = Counter(f.get("dimension", "unknown") for f in existing)
        for dim, cnt in dim_count.most_common():
            print(f"  {dim}：{cnt} 条")
        return

    if not args:
        print("用法：")
        print("  python3 distill_writing_dna.py <文章目录或文件>")
        print("  python3 distill_writing_dna.py --incremental <新文章目录>")
        print("  python3 distill_writing_dna.py --stats")
        sys.exit(1)

    articles = collect_articles(args)
    if not articles:
        print("❌ 未找到有效文章")
        sys.exit(1)

    print(f"✅ 加载 {len(articles)} 篇文章：{[a['id'] for a in articles]}")

    existing_features = []
    if incremental_mode:
        existing_features = load_existing_features(str(features_json_path))
        print(f"🔄 增量模式：已有 {len(existing_features)} 条历史特征")

    result, all_features = run_distillation(articles, existing_features)
    print_report(result)

    # 保存特征库
    if CFG["output"]["export_features_json"]:
        save_features(all_features, str(features_json_path))

    # 保存完整结果
    output_json = Path("distill_result.json")
    with open(output_json, "w", encoding="utf-8") as f:
        # 序列化时去掉无法 JSON 化的部分
        json_result = {k: v for k, v in result.items() if k != "by_dimension"}
        json.dump(json_result, f, ensure_ascii=False, indent=2)
    print(f"📁 详细结果：{output_json.resolve()}")


if __name__ == "__main__":
    main()
