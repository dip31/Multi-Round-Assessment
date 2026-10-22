"""
Phase 4A: Comprehensive Topic Taxonomy and Equivalence Normalization.

Maps synonyms, acronyms, and variations to canonical topics:
- e.g. "DSA" / "Data Structures & Algorithms" / "data structures and algorithms" -> "Data Structures & Algorithms"
- e.g. "DP" / "dynamic programming" / "memoization" -> "Dynamic Programming"
- e.g. "OOP" / "OOPs" / "object oriented programming" -> "Object-Oriented Programming"
- e.g. "OS" / "operating system" -> "Operating Systems"
- e.g. "DBMS" / "database management" -> "Database Management Systems"
- e.g. "CN" / "computer networks" -> "Computer Networks"
"""

import re
from typing import Dict, List, Optional, Set, Tuple

# ── 1. CANONICAL TOPIC DEFINITIONS ────────────────────────────────────

TOPIC_TAXONOMY: Dict[str, Dict] = {
    # ── Algorithms & Data Structures ──────────────────────────────────
    "Data Structures & Algorithms": {
        "category": "Data Structures & Algorithms",
        "aliases": ["dsa", "data structures and algorithms", "data structures & algorithms", "data structures", "algorithms"],
        "default_round": "coding",
    },
    "Arrays": {
        "category": "Data Structures & Algorithms",
        "aliases": ["array", "arrays", "vectors", "matrices", "matrix", "prefix sum", "subarray"],
        "default_round": "coding",
    },
    "Strings": {
        "category": "Data Structures & Algorithms",
        "aliases": ["string", "strings", "string manipulation", "anagram", "palindrome", "substring"],
        "default_round": "coding",
    },
    "Linked Lists": {
        "category": "Data Structures & Algorithms",
        "aliases": ["linked list", "linked lists", "singly linked list", "doubly linked list"],
        "default_round": "coding",
    },
    "Stacks & Queues": {
        "category": "Data Structures & Algorithms",
        "aliases": ["stack", "stacks", "queue", "queues", "deque", "monotonic stack"],
        "default_round": "coding",
    },
    "Trees & Binary Search Trees": {
        "category": "Data Structures & Algorithms",
        "aliases": ["tree", "trees", "binary tree", "binary search tree", "bst", "avl tree", "tree traversal"],
        "default_round": "coding",
    },
    "Heaps & Priority Queues": {
        "category": "Data Structures & Algorithms",
        "aliases": ["heap", "heaps", "priority queue", "min-heap", "max-heap"],
        "default_round": "coding",
    },
    "Graphs & Graph Algorithms": {
        "category": "Data Structures & Algorithms",
        "aliases": ["graph", "graphs", "bfs", "dfs", "dijkstra", "topological sort", "shortest path", "spanning tree"],
        "default_round": "coding",
    },
    "Dynamic Programming": {
        "category": "Data Structures & Algorithms",
        "aliases": ["dp", "dynamic programming", "memoization", "tabulation", "knapsack", "lcs", "longest common subsequence"],
        "default_round": "coding",
    },
    "Recursion & Backtracking": {
        "category": "Data Structures & Algorithms",
        "aliases": ["recursion", "backtracking", "recursive", "n-queens"],
        "default_round": "coding",
    },
    "Greedy Algorithms": {
        "category": "Data Structures & Algorithms",
        "aliases": ["greedy", "greedy algorithms", "greedy approach"],
        "default_round": "coding",
    },
    "Searching & Sorting": {
        "category": "Data Structures & Algorithms",
        "aliases": ["binary search", "sorting", "searching", "mergesort", "quicksort", "bubble sort", "insertion sort"],
        "default_round": "coding",
    },
    "Hashing & Hash Tables": {
        "category": "Data Structures & Algorithms",
        "aliases": ["hashmap", "hash table", "hash set", "hashing", "hash maps"],
        "default_round": "coding",
    },
    "Bit Manipulation": {
        "category": "Data Structures & Algorithms",
        "aliases": ["bit manipulation", "bitwise", "bitmask", "bitmasking"],
        "default_round": "coding",
    },
    "Two Pointers & Sliding Window": {
        "category": "Data Structures & Algorithms",
        "aliases": ["two pointers", "sliding window", "two pointer"],
        "default_round": "coding",
    },
    "Tries": {
        "category": "Data Structures & Algorithms",
        "aliases": ["trie", "tries", "prefix tree"],
        "default_round": "coding",
    },
    "Math & Number Theory": {
        "category": "Data Structures & Algorithms",
        "aliases": ["number theory", "prime numbers", "gcd", "lcm", "modular arithmetic", "combinatorics"],
        "default_round": "coding",
    },

    # ── Core CS Fundamentals ──────────────────────────────────────────
    "Operating Systems": {
        "category": "Core CS",
        "aliases": ["os", "operating system", "operating systems", "linux", "unix", "process management", "scheduling", "deadlock", "concurrency", "multithreading", "paging", "virtual memory", "threads", "synchronization", "semaphores"],
        "default_round": "technical_interview",
    },
    "Database Management Systems": {
        "category": "Core CS",
        "aliases": ["dbms", "database management", "database management systems", "databases", "relational databases", "normalization", "acid", "transactions", "indexing", "joins", "foreign keys", "nosql", "mongodb", "postgresql", "mysql"],
        "default_round": "technical_interview",
    },
    "SQL & Querying": {
        "category": "Core CS",
        "aliases": ["sql", "sql queries", "sql database", "complex queries", "subqueries"],
        "default_round": "technical_interview",
    },
    "Computer Networks": {
        "category": "Core CS",
        "aliases": ["cn", "computer network", "computer networks", "networking", "tcp/ip", "tcp", "udp", "http", "https", "osi model", "dns", "ip addressing", "routing", "sockets"],
        "default_round": "technical_interview",
    },
    "Object-Oriented Programming": {
        "category": "Core CS",
        "aliases": ["oops", "oop", "object-oriented programming", "object oriented programming", "inheritance", "polymorphism", "encapsulation", "abstraction", "interfaces", "classes"],
        "default_round": "technical_interview",
    },
    "System Design": {
        "category": "Core CS",
        "aliases": ["system design", "hld", "lld", "high level design", "low level design", "high-level design", "low-level design", "scalability", "microservices", "caching", "load balancing", "cdn", "sharding", "distributed systems", "message queues", "kafka"],
        "default_round": "technical_interview",
    },
    "Software Engineering & Design Patterns": {
        "category": "Core CS",
        "aliases": ["software engineering", "design patterns", "solid principles", "factory pattern", "singleton", "observer pattern", "agile", "scrum", "git", "version control", "ci/cd", "unit testing"],
        "default_round": "technical_interview",
    },

    # ── Programming Languages & Stacks ────────────────────────────────
    "Java": {
        "category": "Programming Languages",
        "aliases": ["java", "jvm", "spring", "spring boot", "hibernate"],
        "default_round": "coding",
    },
    "Python": {
        "category": "Programming Languages",
        "aliases": ["python", "python3", "django", "flask", "fastapi", "numpy", "pandas"],
        "default_round": "coding",
    },
    "C++": {
        "category": "Programming Languages",
        "aliases": ["c++", "cpp", "stl", "standard template library"],
        "default_round": "coding",
    },
    "C": {
        "category": "Programming Languages",
        "aliases": ["c programming", "c language"],
        "default_round": "coding",
    },
    "JavaScript & TypeScript": {
        "category": "Programming Languages",
        "aliases": ["javascript", "js", "typescript", "ts", "es6", "node", "node.js"],
        "default_round": "coding",
    },
    "Web Development & APIs": {
        "category": "Programming Languages",
        "aliases": ["html", "css", "react", "angular", "vue", "rest api", "rest apis", "restful", "graphql", "backend", "frontend", "full stack"],
        "default_round": "technical_interview",
    },

    # ── Data Engineering, Cloud & AI Domains ──────────────────────────
    "Data Warehousing": {
        "category": "Data Engineering & Cloud",
        "aliases": ["data warehousing", "data warehouse", "data warehouses", "snowflake", "redshift", "bigquery", "etl", "data pipeline", "data pipelines", "olap", "star schema", "snow flake schema"],
        "default_round": "technical_interview",
    },
    "MLOps": {
        "category": "AI & Data Science",
        "aliases": ["mlops", "machine learning operations", "model deployment", "model monitoring", "mlflow", "kubeflow", "feature store", "model registry"],
        "default_round": "technical_interview",
    },
    "Big Data": {
        "category": "Data Engineering & Cloud",
        "aliases": ["big data", "hadoop", "spark", "apache spark", "pyspark", "mapreduce", "hive", "hdfs", "apache kafka", "flink"],
        "default_round": "technical_interview",
    },
    "Machine Learning & AI": {
        "category": "AI & Data Science",
        "aliases": ["machine learning", "ml", "artificial intelligence", "deep learning", "nlp", "natural language processing", "computer vision", "tensorflow", "pytorch", "scikit-learn", "llm", "large language models", "generative ai", "neural networks"],
        "default_round": "technical_interview",
    },
    "Cloud Computing & DevOps": {
        "category": "Data Engineering & Cloud",
        "aliases": ["cloud computing", "aws", "amazon web services", "azure", "microsoft azure", "gcp", "google cloud", "devops", "docker", "kubernetes", "k8s", "terraform", "helm", "ansible"],
        "default_round": "technical_interview",
    },
    "Cybersecurity & Cryptography": {
        "category": "Core CS",
        "aliases": ["cybersecurity", "cyber security", "information security", "cryptography", "encryption", "network security", "oauth", "jwt", "authentication", "authorization", "penetration testing"],
        "default_round": "technical_interview",
    },
    "Data Analytics & BI": {
        "category": "AI & Data Science",
        "aliases": ["data analytics", "business intelligence", "power bi", "powerbi", "tableau", "data visualization", "exploratory data analysis", "eda"],
        "default_round": "technical_interview",
    },

    # ── Aptitude & Quantitative Reasoning ─────────────────────────────
    "Quantitative Aptitude": {
        "category": "Aptitude",
        "aliases": ["quantitative", "quants", "quantitative aptitude", "numerical ability", "arithmetic", "averages", "geometry"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Percentages, Profit & Loss": {
        "category": "Aptitude",
        "aliases": ["percentages", "profit and loss", "profit & loss", "simple interest", "compound interest", "ratio and proportion", "ratios"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Time, Speed & Distance": {
        "category": "Aptitude",
        "aliases": ["time speed distance", "time speed and distance", "speed and distance", "trains", "boats and streams"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Time & Work": {
        "category": "Aptitude",
        "aliases": ["time and work", "time & work", "work and wages", "pipes and cisterns"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Probability, Permutations & Combinations": {
        "category": "Aptitude",
        "aliases": ["permutations and combinations", "permutations & combinations", "permutation and combination", "pnc", "probability"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Number Systems & Algebra": {
        "category": "Aptitude",
        "aliases": ["number system", "number systems", "algebra", "equations", "divisibility", "surds", "logarithms"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Data Interpretation": {
        "category": "Aptitude",
        "aliases": ["data interpretation", "di", "charts", "bar graphs", "bar charts", "line charts", "pie charts", "tables", "tables interpretation"],
        "default_round": "aptitude",
        "blueprint_parent": "Quantitative Aptitude",
    },
    "Logical Reasoning": {
        "category": "Aptitude",
        "aliases": ["logical reasoning", "logical", "lr", "analytical reasoning", "deductive reasoning"],
        "default_round": "aptitude",
        "blueprint_parent": "Logical Reasoning",
    },
    "Puzzles & Arrangements": {
        "category": "Aptitude",
        "aliases": ["puzzles", "logical puzzles", "seating arrangement", "circular arrangement", "linear arrangement", "matrix arrangement"],
        "default_round": "aptitude",
        "blueprint_parent": "Logical Reasoning",
    },
    "Blood Relations & Direction Sense": {
        "category": "Aptitude",
        "aliases": ["blood relations", "blood relation", "direction sense", "directions"],
        "default_round": "aptitude",
        "blueprint_parent": "Logical Reasoning",
    },
    "Coding-Decoding & Series": {
        "category": "Aptitude",
        "aliases": ["coding-decoding", "coding decoding", "number series", "letter series", "analogies"],
        "default_round": "aptitude",
        "blueprint_parent": "Logical Reasoning",
    },
    "Syllogisms & Critical Reasoning": {
        "category": "Aptitude",
        "aliases": ["syllogisms", "syllogism", "critical reasoning", "statement and assumption", "statement and conclusion"],
        "default_round": "aptitude",
        "blueprint_parent": "Logical Reasoning",
    },
    "Verbal Ability": {
        "category": "Aptitude",
        "aliases": ["verbal", "verbal ability", "english", "grammar", "vocabulary", "synonyms", "antonyms", "sentence correction", "sentence completion", "fill in the blanks", "spotting errors", "para jumbles"],
        "default_round": "aptitude",
        "blueprint_parent": "Verbal Ability",
    },
    "Reading Comprehension": {
        "category": "Aptitude",
        "aliases": ["reading comprehension", "rc", "comprehension passages"],
        "default_round": "aptitude",
        "blueprint_parent": "Verbal Ability",
    },

    # ── Behavioral & HR ───────────────────────────────────────────────
    "Behavioral & Leadership Principles": {
        "category": "Behavioral",
        "aliases": ["behavioral", "behavioural", "leadership principles", "situational", "star method", "teamwork", "conflict resolution", "cultural fit", "culture fit"],
        "default_round": "hr_interview",
    },
    "HR & Personal Interview": {
        "category": "Behavioral",
        "aliases": ["hr", "hr interview", "hr round", "personal interview", "strengths and weaknesses", "resume walkthrough", "project discussion", "career goals"],
        "default_round": "hr_interview",
    },
}

# ── 2. NON-TOPIC STOP PHRASES / GENERIC HEADINGS FILTER ───────────────

NON_TOPIC_STOP_PHRASES: Set[str] = {
    "expected outcome", "expected outcomes", "outcome", "outcomes",
    "we are looking for", "looking for", "who you are", "what you will do", "what we offer",
    "preferred", "preferred qualifications", "good to have", "nice to have", "must have",
    "mentorship from experienced professionals", "mentorship", "training",
    "job description", "role description", "about the role", "about us", "about company",
    "eligibility criteria", "eligibility", "requirements", "responsibilities",
    "qualifications", "key responsibilities", "perks & benefits", "benefits", "perks",
    "equal opportunity employer", "compensation", "location", "batch",
    "selection process", "hiring process", "interview process", "guidelines", "instructions",
    "overview", "summary", "details", "note", "notes", "feedback", "experience", "work experience",
    "full time", "internship", "remote", "onsite", "hybrid", "package", "ctc", "stipend",
    "candidate profile", "job summary", "company overview", "role overview", "job profile",
}

# ── 3. PRECOMPUTE INVERTED ALIAS MAP ───────────────────────────────────

_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, info in TOPIC_TAXONOMY.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in info["aliases"]:
        _ALIAS_TO_CANONICAL[alias.lower().strip()] = canonical

# Multi-word aliases sorted by length descending so longer phrases match first
_SORTED_ALIASES: List[Tuple[str, str, re.Pattern]] = []
for alias, canonical in sorted(_ALIAS_TO_CANONICAL.items(), key=lambda x: len(x[0]), reverse=True):
    escaped = re.escape(alias)
    if alias == "c++":
        pat = re.compile(r'(?:\b|(?<=\s))c\+\+(?:\b|(?=\s|[.,;:]))', re.IGNORECASE)
    elif alias == "c#":
        pat = re.compile(r'(?:\b|(?<=\s))c\#(?:\b|(?=\s|[.,;:]))', re.IGNORECASE)
    else:
        pat = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
    _SORTED_ALIASES.append((alias, canonical, pat))


# ── 4. NORMALIZATION & EXTRACTION API ─────────────────────────────────

def normalize_topic(raw_text: str) -> str:
    """Normalize any topic string to its canonical name.

    Returns:
        The canonical topic name if matched in the taxonomy, or an empty string ""
        if unrecognized or identified as non-skill/generic text.

    Examples:
        normalize_topic("dsa") -> "Data Structures & Algorithms"
        normalize_topic("DP") -> "Dynamic Programming"
        normalize_topic("OOPS") -> "Object-Oriented Programming"
        normalize_topic("MLOps") -> "MLOps"
        normalize_topic("Expected Outcome") -> ""
        normalize_topic("Mentorship From Experienced Professionals") -> ""
    """
    if not raw_text:
        return ""
    cleaned = raw_text.strip().lower()

    # 1. Quick check against known stop phrases
    if cleaned in NON_TOPIC_STOP_PHRASES:
        return ""
    for stop in NON_TOPIC_STOP_PHRASES:
        if stop in cleaned and (cleaned == stop or len(cleaned.split()) >= 3):
            return ""

    # 2. Direct match in taxonomy alias dictionary
    if cleaned in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[cleaned]

    # 3. Exact alias match with word boundaries
    for alias, canonical, pat in _SORTED_ALIASES:
        if pat.fullmatch(cleaned):
            return canonical
        # Partial match only if the cleaned input closely corresponds to the alias
        if pat.search(cleaned):
            alias_word_count = len(alias.split())
            cleaned_word_count = len(cleaned.split())
            # Do not match if the input is a long sentence containing an alias incidentally
            if cleaned_word_count <= alias_word_count + 1 and len(alias) >= 3:
                return canonical

    # 4. Unknown/unclassified text is NOT treated as a topic
    return ""


def extract_topics_from_text(text: str) -> List[Tuple[str, str]]:
    """Scan free text and extract all matching canonical topics.

    Returns:
        List of (canonical_topic, category) tuples without duplicates.
    """
    if not text:
        return []

    found_topics: Set[str] = set()
    result: List[Tuple[str, str]] = []

    for _, canonical, pat in _SORTED_ALIASES:
        if canonical in found_topics:
            continue
        if pat.search(text):
            found_topics.add(canonical)
            category = TOPIC_TAXONOMY.get(canonical, {}).get("category", "General")
            result.append((canonical, category))

    return result


def get_topic_category(canonical_topic: str) -> str:
    """Return the high-level category for a canonical topic."""
    info = TOPIC_TAXONOMY.get(canonical_topic)
    if info:
        return info.get("category", "General")
    return "General"


def topic_matches_blueprint_group(topic: str, blueprint_group: str) -> bool:
    """Match a seeded topic to a broad blueprint heading through this taxonomy."""
    canonical_topic = normalize_topic(topic) or topic.strip()
    canonical_group = normalize_topic(blueprint_group) or blueprint_group.strip()
    if canonical_topic.casefold() == canonical_group.casefold():
        return True
    topic_info = TOPIC_TAXONOMY.get(canonical_topic, {})
    return str(topic_info.get("blueprint_parent", "")).casefold() == canonical_group.casefold()


def get_default_round_for_topic(canonical_topic: str) -> str:
    """Return the assessment round where this topic is typically evaluated."""
    info = TOPIC_TAXONOMY.get(canonical_topic)
    if info:
        return info.get("default_round", "coding")
    return "coding"
