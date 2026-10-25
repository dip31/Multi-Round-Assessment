"""
Canonical Skill Taxonomy for EDI5 Portfolio Builder Assessment.

Defines the supported skills, their competencies, and normalization rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum


class SkillCategory(str, Enum):
    """High-level categories for skills."""
    APTITUDE = "Aptitude"
    CORE_CS = "Core CS"
    PROGRAMMING = "Programming"
    FRONTEND = "Frontend"
    BACKEND = "Backend"
    DATABASE = "Database"
    CLOUD_DEVOPS = "Cloud & DevOps"
    SYSTEM_DESIGN = "System Design"


@dataclass(frozen=True)
class Competency:
    """A specific competency within a skill."""
    code: str
    name: str
    description: str
    category: SkillCategory


@dataclass(frozen=True)
class Skill:
    """A canonical skill with its competencies."""
    code: str
    name: str
    category: SkillCategory
    description: str
    competencies: List[Competency] = field(default_factory=list)
    aliases: Set[str] = field(default_factory=set)


# ============================================================================
# COMPETENCY DEFINITIONS
# ============================================================================

# Aptitude Competencies
QUANT_EASY = Competency("QUANT_EASY", "Basic Arithmetic & Number Systems", "Fundamental arithmetic operations, percentages, ratios", SkillCategory.APTITUDE)
QUANT_MEDIUM = Competency("QUANT_MEDIUM", "Algebra & Word Problems", "Linear equations, profit/loss, time/work/distance", SkillCategory.APTITUDE)
QUANT_HARD = Competency("QUANT_HARD", "Advanced Quantitative Concepts", "Permutations, probability, advanced word problems", SkillCategory.APTITUDE)

LOGIC_EASY = Competency("LOGIC_EASY", "Basic Logical Patterns", "Series completion, odd one out, simple analogies", SkillCategory.APTITUDE)
LOGIC_MEDIUM = Competency("LOGIC_MEDIUM", "Analytical Reasoning", "Blood relations, coding-decoding, direction sense", SkillCategory.APTITUDE)
LOGIC_HARD = Competency("LOGIC_HARD", "Complex Logical Deduction", "Syllogisms, logical puzzles, critical reasoning", SkillCategory.APTITUDE)

VERBAL_EASY = Competency("VERBAL_EASY", "Vocabulary Basics", "Synonyms, antonyms, spellings", SkillCategory.APTITUDE)
VERBAL_MEDIUM = Competency("VERBAL_MEDIUM", "Grammar & Usage", "Sentence correction, fill in blanks, idioms", SkillCategory.APTITUDE)
VERBAL_HARD = Competency("VERBAL_HARD", "Reading Comprehension", "Passage analysis, inference, tone detection", SkillCategory.APTITUDE)

DATA_INTERP = Competency("DATA_INTERP", "Data Interpretation", "Charts, graphs, tables analysis", SkillCategory.APTITUDE)


# Core CS Competencies
OS_BASICS = Competency("OS_BASICS", "OS Fundamentals", "Processes, threads, scheduling basics", SkillCategory.CORE_CS)
OS_MEMORY = Competency("OS_MEMORY", "Memory Management", "Virtual memory, paging, segmentation", SkillCategory.CORE_CS)
OS_SYNC = Competency("OS_SYNC", "Synchronization & Deadlocks", "Mutex, semaphores, deadlock prevention", SkillCategory.CORE_CS)

CN_BASICS = Competency("CN_BASICS", "Network Fundamentals", "OSI/TCP-IP models, IP addressing", SkillCategory.CORE_CS)
CN_TRANSPORT = Competency("CN_TRANSPORT", "Transport Layer", "TCP/UDP, congestion control, flow control", SkillCategory.CORE_CS)
CN_APP = Competency("CN_APP", "Application Layer", "HTTP, DNS, email protocols", SkillCategory.CORE_CS)

DBMS_BASICS = Competency("DBMS_BASICS", "Relational Model & SQL", "ER model, normalization, basic queries", SkillCategory.CORE_CS)
DBMS_ADVANCED = Competency("DBMS_ADVANCED", "Advanced DBMS", "Transactions, indexing, query optimization", SkillCategory.CORE_CS)

OOP_BASICS = Competency("OOP_BASICS", "OOP Principles", "Encapsulation, inheritance, polymorphism", SkillCategory.CORE_CS)
OOP_DESIGN = Competency("OOP_DESIGN", "Design Patterns", "SOLID principles, common patterns", SkillCategory.CORE_CS)

DSA_ARRAYS = Competency("DSA_ARRAYS", "Arrays & Strings", "Manipulation, two pointers, sliding window", SkillCategory.CORE_CS)
DSA_HASHING = Competency("DSA_HASHING", "Hashing", "Hash maps, sets, collision handling", SkillCategory.CORE_CS)
DSA_SORTING = Competency("DSA_SORTING", "Sorting & Searching", "Comparison sorts, binary search", SkillCategory.CORE_CS)
DSA_STACK_QUEUE = Competency("DSA_STACK_QUEUE", "Stacks & Queues", "LIFO/FIFO, monotonic stack/queue", SkillCategory.CORE_CS)
DSA_LINKED_LIST = Competency("DSA_LINKED_LIST", "Linked Lists", "Singly/doubly, cycle detection", SkillCategory.CORE_CS)
DSA_TREES = Competency("DSA_TREES", "Trees & BST", "Traversals, BST operations, balanced trees", SkillCategory.CORE_CS)
DSA_HEAPS = Competency("DSA_HEAPS", "Heaps & Priority Queues", "Min/max heap, heapify, applications", SkillCategory.CORE_CS)
DSA_GRAPHS = Competency("DSA_GRAPHS", "Graph Algorithms", "BFS/DFS, shortest path, MST, topological sort", SkillCategory.CORE_CS)
DSA_DP = Competency("DSA_DP", "Dynamic Programming", "Memoization, tabulation, classic problems", SkillCategory.CORE_CS)
DSA_GREEDY = Competency("DSA_GREEDY", "Greedy Algorithms", "Interval scheduling, Huffman, MST", SkillCategory.CORE_CS)
DSA_RECURSION = Competency("DSA_RECURSION", "Recursion & Backtracking", "Subsets, permutations, N-Queens", SkillCategory.CORE_CS)
DSA_COMPLEXITY = Competency("DSA_COMPLEXITY", "Complexity Analysis", "Time/space complexity, Big-O notation", SkillCategory.CORE_CS)


# Programming Language Competencies
PY_BASICS = Competency("PY_BASICS", "Python Fundamentals", "Syntax, data types, control flow", SkillCategory.PROGRAMMING)
PY_OOP = Competency("PY_OOP", "Python OOP", "Classes, inheritance, magic methods", SkillCategory.PROGRAMMING)
PY_ADVANCED = Competency("PY_ADVANCED", "Advanced Python", "Decorators, generators, context managers, async", SkillCategory.PROGRAMMING)
PY_STDLIB = Competency("PY_STDLIB", "Standard Library", "collections, itertools, functools, pathlib", SkillCategory.PROGRAMMING)

JAVA_BASICS = Competency("JAVA_BASICS", "Java Fundamentals", "Syntax, OOP, collections, exceptions", SkillCategory.PROGRAMMING)
JAVA_ADVANCED = Competency("JAVA_ADVANCED", "Advanced Java", "Streams, concurrency, JVM internals", SkillCategory.PROGRAMMING)
JAVA_SPRING = Competency("JAVA_SPRING", "Spring Framework", "DI, Spring Boot, Data, Security", SkillCategory.BACKEND)

JS_BASICS = Competency("JS_BASICS", "JavaScript Fundamentals", "ES6+, closures, async/await", SkillCategory.PROGRAMMING)
JS_ADVANCED = Competency("JS_ADVANCED", "Advanced JavaScript", "Prototypes, event loop, modules", SkillCategory.PROGRAMMING)
TS_BASICS = Competency("TS_BASICS", "TypeScript Fundamentals", "Types, interfaces, generics", SkillCategory.PROGRAMMING)
TS_ADVANCED = Competency("TS_ADVANCED", "Advanced TypeScript", "Utility types, conditional types, inference", SkillCategory.PROGRAMMING)

CPP_BASICS = Competency("CPP_BASICS", "C++ Fundamentals", "Syntax, memory management, STL", SkillCategory.PROGRAMMING)


# Frontend Competencies
REACT_BASICS = Competency("REACT_BASICS", "React Fundamentals", "Components, props, state, lifecycle", SkillCategory.FRONTEND)
REACT_HOOKS = Competency("REACT_HOOKS", "React Hooks", "useState, useEffect, custom hooks", SkillCategory.FRONTEND)
REACT_STATE = Competency("REACT_STATE", "State Management", "Context, Redux, Zustand, React Query", SkillCategory.FRONTEND)
REACT_PERF = Competency("REACT_PERF", "React Performance", "Memoization, code splitting, profiling", SkillCategory.FRONTEND)
FRONTEND_BASICS = Competency("FRONTEND_BASICS", "HTML/CSS/JS Basics", "Semantic HTML, CSS layout, DOM API", SkillCategory.FRONTEND)
FRONTEND_TOOLING = Competency("FRONTEND_TOOLING", "Build Tools & Testing", "Vite, Webpack, Jest, Cypress", SkillCategory.FRONTEND)


# Backend Competencies
PY_BACKEND_BASICS = Competency("PY_BACKEND_BASICS", "Python Backend Basics", "FastAPI/Flask, routing, middleware", SkillCategory.BACKEND)
PY_BACKEND_DB = Competency("PY_BACKEND_DB", "Database Integration", "SQLAlchemy, migrations, ORM patterns", SkillCategory.BACKEND)
PY_BACKEND_AUTH = Competency("PY_BACKEND_AUTH", "Authentication & Security", "JWT, OAuth, password hashing, CORS", SkillCategory.BACKEND)
PY_BACKEND_TESTING = Competency("PY_BACKEND_TESTING", "Testing & Reliability", "Pytest, integration tests, CI", SkillCategory.BACKEND)

BACKEND_API_DESIGN = Competency("BACKEND_API_DESIGN", "API Design", "REST, GraphQL, versioning, documentation", SkillCategory.BACKEND)
BACKEND_SCALING = Competency("BACKEND_SCALING", "Scalability & Performance", "Caching, load balancing, async processing", SkillCategory.BACKEND)
BACKEND_MICROSERVICES = Competency("BACKEND_MICROSERVICES", "Microservices", "Service discovery, communication, resilience", SkillCategory.BACKEND)


# Database Competencies
SQL_BASICS = Competency("SQL_BASICS", "SQL Fundamentals", "SELECT, JOIN, WHERE, GROUP BY", SkillCategory.DATABASE)
SQL_ADVANCED = Competency("SQL_ADVANCED", "Advanced SQL", "Window functions, CTEs, recursive queries", SkillCategory.DATABASE)
SQL_OPTIMIZATION = Competency("SQL_OPTIMIZATION", "Query Optimization", "Indexes, execution plans, tuning", SkillCategory.DATABASE)
SQL_DESIGN = Competency("SQL_DESIGN", "Database Design", "Normalization, constraints, ER modeling", SkillCategory.DATABASE)
NOSQL_BASICS = Competency("NOSQL_BASICS", "NoSQL Fundamentals", "Document, key-value, wide-column stores", SkillCategory.DATABASE)


# Cloud & DevOps Competencies
CLOUD_BASICS = Competency("CLOUD_BASICS", "Cloud Fundamentals", "IaaS/PaaS/SaaS, regions, availability zones", SkillCategory.CLOUD_DEVOPS)
CONTAINERS = Competency("CONTAINERS", "Containerization", "Docker, images, Dockerfile, Compose", SkillCategory.CLOUD_DEVOPS)
K8S_BASICS = Competency("K8S_BASICS", "Kubernetes Basics", "Pods, services, deployments, configmaps", SkillCategory.CLOUD_DEVOPS)
CI_CD = Competency("CI_CD", "CI/CD Pipelines", "GitHub Actions, GitLab CI, Jenkins", SkillCategory.CLOUD_DEVOPS)
MONITORING = Competency("MONITORING", "Observability", "Logging, metrics, tracing, alerting", SkillCategory.CLOUD_DEVOPS)


# System Design Competencies
SYS_DESIGN_BASICS = Competency("SYS_DESIGN_BASICS", "System Design Fundamentals", "Requirements, capacity estimation, APIs", SkillCategory.SYSTEM_DESIGN)
SCALABILITY = Competency("SCALABILITY", "Scalability Patterns", "Horizontal/vertical scaling, sharding, replication", SkillCategory.SYSTEM_DESIGN)
CACHING = Competency("CACHING", "Caching Strategies", "Redis, CDN, cache invalidation, write-through", SkillCategory.SYSTEM_DESIGN)
DISTRIBUTED = Competency("DISTRIBUTED", "Distributed Systems", "Consensus, CAP theorem, distributed transactions", SkillCategory.SYSTEM_DESIGN)
RELIABILITY = Competency("RELIABILITY", "Reliability Engineering", "SLA/SLO/SLI, circuit breakers, retries", SkillCategory.SYSTEM_DESIGN)


# ============================================================================
# SKILL DEFINITIONS
# ============================================================================

SKILLS: Dict[str, Skill] = {
    "quantitative_aptitude": Skill(
        code="quantitative_aptitude",
        name="Quantitative Aptitude",
        category=SkillCategory.APTITUDE,
        description="Mathematical problem-solving and numerical reasoning",
        competencies=[QUANT_EASY, QUANT_MEDIUM, QUANT_HARD],
        aliases={"quant", "quantitative", "math", "mathematics", "arithmetic", "quant apt"},
    ),
    "logical_reasoning": Skill(
        code="logical_reasoning",
        name="Logical Reasoning",
        category=SkillCategory.APTITUDE,
        description="Analytical and deductive reasoning abilities",
        competencies=[LOGIC_EASY, LOGIC_MEDIUM, LOGIC_HARD],
        aliases={"logic", "reasoning", "analytical reasoning", "lr", "logical"},
    ),
    "verbal_ability": Skill(
        code="verbal_ability",
        name="Verbal Ability",
        category=SkillCategory.APTITUDE,
        description="English language proficiency and comprehension",
        competencies=[VERBAL_EASY, VERBAL_MEDIUM, VERBAL_HARD],
        aliases={"verbal", "english", "language", "verbal ability", "va"},
    ),
    "data_interpretation": Skill(
        code="data_interpretation",
        name="Data Interpretation",
        category=SkillCategory.APTITUDE,
        description="Analyzing and interpreting data from charts and tables",
        competencies=[DATA_INTERP],
        aliases={"di", "data interpretation", "data analysis"},
    ),
    "operating_systems": Skill(
        code="operating_systems",
        name="Operating Systems",
        category=SkillCategory.CORE_CS,
        description="OS concepts: processes, memory, synchronization",
        competencies=[OS_BASICS, OS_MEMORY, OS_SYNC],
        aliases={"os", "operating system", "operating systems"},
    ),
    "computer_networks": Skill(
        code="computer_networks",
        name="Computer Networks",
        category=SkillCategory.CORE_CS,
        description="Networking protocols and architectures",
        competencies=[CN_BASICS, CN_TRANSPORT, CN_APP],
        aliases={"cn", "networks", "computer networks", "networking"},
    ),
    "dbms": Skill(
        code="dbms",
        name="Database Management Systems",
        category=SkillCategory.CORE_CS,
        description="Relational databases, SQL, transaction management",
        competencies=[DBMS_BASICS, DBMS_ADVANCED],
        aliases={"database", "databases", "rdbms", "sql", "dbms"},
    ),
    "oop": Skill(
        code="oop",
        name="Object Oriented Programming",
        category=SkillCategory.CORE_CS,
        description="OOP principles and design patterns",
        competencies=[OOP_BASICS, OOP_DESIGN],
        aliases={"oops", "object oriented", "object-oriented", "oop"},
    ),
    "data_structures_algorithms": Skill(
        code="data_structures_algorithms",
        name="Data Structures & Algorithms",
        category=SkillCategory.CORE_CS,
        description="Fundamental data structures and algorithmic techniques",
        competencies=[
            DSA_ARRAYS, DSA_HASHING, DSA_SORTING, DSA_STACK_QUEUE,
            DSA_LINKED_LIST, DSA_TREES, DSA_HEAPS, DSA_GRAPHS,
            DSA_DP, DSA_GREEDY, DSA_RECURSION, DSA_COMPLEXITY
        ],
        aliases={"dsa", "data structures", "algorithms", "data structures & algorithms", "ds & algo"},
    ),
    "python": Skill(
        code="python",
        name="Python",
        category=SkillCategory.PROGRAMMING,
        description="Python programming language proficiency",
        competencies=[PY_BASICS, PY_OOP, PY_ADVANCED, PY_STDLIB],
        aliases={"py", "python3", "python 3"},
    ),
    "java": Skill(
        code="java",
        name="Java",
        category=SkillCategory.PROGRAMMING,
        description="Java programming language proficiency",
        competencies=[JAVA_BASICS, JAVA_ADVANCED],
        aliases={"java", "java8", "java11", "java17"},
    ),
    "javascript": Skill(
        code="javascript",
        name="JavaScript",
        category=SkillCategory.PROGRAMMING,
        description="JavaScript programming language proficiency",
        competencies=[JS_BASICS, JS_ADVANCED],
        aliases={"js", "javascript", "ecmascript", "es6", "es2020"},
    ),
    "typescript": Skill(
        code="typescript",
        name="TypeScript",
        category=SkillCategory.PROGRAMMING,
        description="TypeScript programming language proficiency",
        competencies=[TS_BASICS, TS_ADVANCED],
        aliases={"ts", "typescript"},
    ),
    "cpp": Skill(
        code="cpp",
        name="C++",
        category=SkillCategory.PROGRAMMING,
        description="C++ programming language proficiency",
        competencies=[CPP_BASICS],
        aliases={"c++", "cpp", "cplusplus"},
    ),
    "react": Skill(
        code="react",
        name="React",
        category=SkillCategory.FRONTEND,
        description="React library for building user interfaces",
        competencies=[REACT_BASICS, REACT_HOOKS, REACT_STATE, REACT_PERF],
        aliases={"react.js", "reactjs", "react.js"},
    ),
    "frontend_fundamentals": Skill(
        code="frontend_fundamentals",
        name="Frontend Fundamentals",
        category=SkillCategory.FRONTEND,
        description="Core frontend technologies: HTML, CSS, JavaScript",
        competencies=[FRONTEND_BASICS, FRONTEND_TOOLING],
        aliases={"frontend", "front-end", "web development", "html", "css"},
    ),
    "python_backend": Skill(
        code="python_backend",
        name="Python Backend Development",
        category=SkillCategory.BACKEND,
        description="Backend development with Python (FastAPI, Flask, Django)",
        competencies=[PY_BACKEND_BASICS, PY_BACKEND_DB, PY_BACKEND_AUTH, PY_BACKEND_TESTING],
        aliases={"python backend", "fastapi", "flask", "django", "backend python"},
    ),
    "java_backend": Skill(
        code="java_backend",
        name="Java Backend Development",
        category=SkillCategory.BACKEND,
        description="Backend development with Java (Spring Boot)",
        competencies=[JAVA_SPRING, BACKEND_API_DESIGN, BACKEND_SCALING],
        aliases={"java backend", "spring", "spring boot", "backend java"},
    ),
    "backend_fundamentals": Skill(
        code="backend_fundamentals",
        name="Backend Fundamentals",
        category=SkillCategory.BACKEND,
        description="Core backend concepts: APIs, databases, auth, scaling",
        competencies=[BACKEND_API_DESIGN, BACKEND_SCALING, BACKEND_MICROSERVICES],
        aliases={"backend", "api", "rest", "graphql", "microservices"},
    ),
    "sql": Skill(
        code="sql",
        name="SQL",
        category=SkillCategory.DATABASE,
        description="Structured Query Language for relational databases",
        competencies=[SQL_BASICS, SQL_ADVANCED, SQL_OPTIMIZATION, SQL_DESIGN],
        aliases={"sql", "postgresql", "mysql", "postgres", "structured query language"},
    ),
    "nosql": Skill(
        code="nosql",
        name="NoSQL Databases",
        category=SkillCategory.DATABASE,
        description="Non-relational database systems",
        competencies=[NOSQL_BASICS],
        aliases={"nosql", "mongodb", "redis", "cassandra", "dynamodb"},
    ),
    "cloud_devops": Skill(
        code="cloud_devops",
        name="Cloud & DevOps",
        category=SkillCategory.CLOUD_DEVOPS,
        description="Cloud platforms, containerization, CI/CD, monitoring",
        competencies=[CLOUD_BASICS, CONTAINERS, K8S_BASICS, CI_CD, MONITORING],
        aliases={"cloud", "devops", "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "ci/cd"},
    ),
    "system_design": Skill(
        code="system_design",
        name="System Design",
        category=SkillCategory.SYSTEM_DESIGN,
        description="Large-scale system architecture and design principles",
        competencies=[SYS_DESIGN_BASICS, SCALABILITY, CACHING, DISTRIBUTED, RELIABILITY],
        aliases={"system design", "architecture", "distributed systems", "scalability"},
    ),
}


# ============================================================================
# NORMALIZATION
# ============================================================================

# Build alias to skill code mapping
_ALIAS_TO_SKILL: Dict[str, str] = {}
for skill_code, skill in SKILLS.items():
    _ALIAS_TO_SKILL[skill_code.lower()] = skill_code
    _ALIAS_TO_SKILL[skill.name.lower()] = skill_code
    for alias in skill.aliases:
        _ALIAS_TO_SKILL[alias.lower()] = skill_code


def normalize_skill(skill_input: str) -> Optional[str]:
    """
    Normalize a free-text skill input to a canonical skill code.
    
    Returns the canonical skill code if found, None otherwise.
    """
    if not skill_input:
        return None
    normalized = skill_input.strip().lower()
    return _ALIAS_TO_SKILL.get(normalized)


def get_skill(skill_code: str) -> Optional[Skill]:
    """Get a Skill by its canonical code."""
    return SKILLS.get(skill_code)


def get_all_skills() -> List[Skill]:
    """Get all canonical skills."""
    return list(SKILLS.values())


def get_skills_by_category(category: SkillCategory) -> List[Skill]:
    """Get all skills in a category."""
    return [s for s in SKILLS.values() if s.category == category]


def get_competency(competency_code: str) -> Optional[Competency]:
    """Get a Competency by its code."""
    for skill in SKILLS.values():
        for comp in skill.competencies:
            if comp.code == competency_code:
                return comp
    return None


def get_competencies_for_skill(skill_code: str) -> List[Competency]:
    """Get all competencies for a skill."""
    skill = SKILLS.get(skill_code)
    return skill.competencies if skill else []


def is_supported_skill(skill_input: str) -> bool:
    """Check if a skill input maps to a supported canonical skill."""
    return normalize_skill(skill_input) is not None


def get_unsupported_skills(skill_inputs: List[str]) -> List[str]:
    """Get list of skill inputs that don't map to any canonical skill."""
    return [s for s in skill_inputs if not is_supported_skill(s)]


# ============================================================================
# ASSESSMENT ROUND MAPPING
# ============================================================================

ROUND_SKILL_MAPPING = {
    "aptitude": [
        "quantitative_aptitude",
        "logical_reasoning",
        "verbal_ability",
        "data_interpretation",
    ],
    "technical": [
        "operating_systems",
        "computer_networks",
        "dbms",
        "oop",
        "data_structures_algorithms",
    ],
    "combined": [
        "quantitative_aptitude",
        "logical_reasoning",
        "verbal_ability",
        "data_interpretation",
        "operating_systems",
        "computer_networks",
        "dbms",
        "oop",
        "data_structures_algorithms",
    ],
    "coding": [
        "data_structures_algorithms",
        "python",
        "java",
        "javascript",
        "typescript",
        "cpp",
    ],
}


def get_skills_for_round(round_type: str) -> List[str]:
    """Get the canonical skill codes assessed in a given round type."""
    return ROUND_SKILL_MAPPING.get(round_type, [])


def get_competencies_for_round(round_type: str) -> List[Competency]:
    """Get all competencies assessed in a given round type."""
    skill_codes = get_skills_for_round(round_type)
    competencies = []
    for code in skill_codes:
        competencies.extend(get_competencies_for_skill(code))
    return competencies