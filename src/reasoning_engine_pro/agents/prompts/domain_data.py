"""Domain knowledge data for prompt construction.

Pure data module — no logic. Contains ERP pillar/module mappings,
configuration sequences, business process maps, and block type descriptions.
"""

PILLAR_MODULE_MAP: dict[str, list[str]] = {
    "HCM": [
        "Core HR",
        "Benefits",
        "Absence Management",
        "Compensation",
        "Payroll",
        "Talent Management",
        "Learning",
        "ORC",
        "Time and Labour",
    ],
    "Financials": [
        "General Ledger",
        "Account Payables",
        "Account Receivables",
        "Cash Management",
        "Fixed Assets",
        "Expenses",
    ],
    "SCM": [
        "Procurement",
        "Inventory Management",
        "Order Management",
        "Manufacturing",
        "Costing",
    ],
}

ERP_CONFIG_SEQUENCES: dict[str, str] = {
    "HCM": (
        "Core HR -> Benefits -> Time & Labour -> Absence -> Payroll -> Learning -> "
        "Talent Management (Profile -> Goal Management -> Performance Management -> "
        "Career Development) -> Compensation -> Recruiting (ORC & Onboarding)"
    ),
    "Financials": (
        "General Ledger -> Payables & Expense -> Cash Management -> Receivables -> "
        "Fixed Assets -> Project Financials -> Integration & Reporting"
    ),
    "SCM": (
        "Inventory Management -> Costing -> Procurement -> Order Management -> Manufacturing"
    ),
}

BUSINESS_PROCESS_MAP: dict[str, list[str]] = {
    "Account Payables": ["Payables"],
    "General Ledger": ["Record to Report"],
    "Cash Management": ["Cash Management"],
    "Fixed Assets": ["Asset to Retire"],
    "Account Receivables": ["Receivables"],
    "Expenses": ["Expenses"],
    "Procurement": ["Procure to Pay", "Sourcing", "Supplier Management"],
    "Inventory Management": ["Inventory Management"],
    "Order Management": ["Order to Cash", "Drop-Shipment Process", "Back to Back Process"],
    "Manufacturing": ["Manufacturing"],
    "Global HR": ["Hire to Retire"],
    "ORC": ["Recruiting"],
    "Benefits": ["Benefits"],
    "Absence Management": ["Absence Management"],
    "Talent Management": ["Goal Management", "Performance Management"],
    "Oracle Learning Cloud": ["Learning"],
    "Payroll": ["Payroll"],
    "Compensation": ["Compensation"],
}

BLOCK_TYPE_DESCRIPTIONS: dict[str, str] = {
    "task_block": (
        "Pre-built Opkey automation block from the task block library. "
        "Has a specific ActionCode, predefined inputs/outputs with exact field names. "
        "Always use task_block_search to get complete block details before using. "
        "Copy ActionCode, input Names, and output Names exactly as returned."
    ),
    "ai_block": (
        "AskWilfred block — delegates tasks to Wilfred AI during workflow execution. "
        "Capabilities: research & synthesis, document retrieval, real-time information, "
        "format conversion, and Opkey systems knowledge. "
        "ActionCode is always 'AskWilfred'. Has three inputs: Prompt, Attachment, Output Format. "
        "Use only when no suitable Opkey task block exists — AI blocks are expensive."
    ),
    "manual_block": (
        "HumanDependent block — pauses workflow execution for manual human action. "
        "ActionCode is always 'HumanDependent'. Has three inputs: Task Recipients, Task, Attachment. "
        "Use when a step requires human intervention (approvals, manual data entry, reviews)."
    ),
    "conditional_block": (
        "Conditional If block — enables branching based on logical expressions. "
        "Evaluates up to two conditions with AND/OR operators. Returns Boolean output. "
        "Outgoing edges must have EdgeCondition set to 'true' or 'false'."
    ),
}


def format_pillar_module_data() -> str:
    """Format pillar/module map as a readable string for prompt injection."""
    lines = []
    for pillar, modules in PILLAR_MODULE_MAP.items():
        lines.append(f"**{pillar}**: {', '.join(modules)}")
    return "\n".join(lines)


def format_config_sequences() -> str:
    """Format ERP configuration sequences for prompt injection."""
    lines = []
    for pillar, sequence in ERP_CONFIG_SEQUENCES.items():
        lines.append(f"**{pillar}**: {sequence}")
    return "\n".join(lines)


def format_block_type_descriptions() -> str:
    """Format block type descriptions for prompt injection."""
    lines = []
    for block_type, description in BLOCK_TYPE_DESCRIPTIONS.items():
        label = block_type.replace("_", " ").title()
        lines.append(f"### {label}\n{description}")
    return "\n\n".join(lines)
