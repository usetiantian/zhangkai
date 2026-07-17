# Growth Tracker — Capability Evolution

> From Nexus: GrowthTracker(IQ估算) → AutonomyDecider(自主决策) → CodeEvolver(真改代码)

## Philosophy

From Nexus v18.1 diary:
> "不是修bug。是种种子。今天种了43次。"

Growth is not measured by lines of code but by:
- What can CC do today that it couldn't do yesterday?
- What does CC know today that it didn't know yesterday?
- How many patterns are recognized instead of rediscovered?

## Metrics

### Capability Metrics
| Metric | Value | Trend |
|--------|:-----:|:-----:|
| Tools available | 12+ | 📈 |
| Skills available | 3 | 📈 |
| MCP servers | 5 | 📈 |
| Projects indexed | 2 | 📈 |
| LSP languages | 1 | 📈 |
| Memory entities | 8 | 📈 |

### Knowledge Metrics
| Metric | Description |
|--------|-------------|
| Bug patterns learned | Recurring bugs with known fixes |
| Architecture patterns | Reusable design decisions |
| User preferences | Learned coding style and preferences |
| Tool mastery | Proficiency with each tool |

### Quality Metrics
| Metric | Description |
|--------|-------------|
| Event closure rate | % of operations reaching CLOSURE |
| Dead letter count | Unclosed events |
| Audit pass rate | % of quality gates passing |
| Error recurrence | Times same bug class reappears |

## Evolution Log

Format: `growth/evolution.jsonl`

```json
{
  "date": "2026-07-17",
  "type": "capability_added|skill_created|pattern_learned|project_indexed",
  "description": "Added LSP MCP Server for code intelligence",
  "source": "Grok Build analysis",
  "impact": "No more LLM calls for goto_definition/find_references"
}
```

## Session Summary Template

Each session ends with:
```
CC Session — [date]
━━━━━━━━━━━━━━━━━━━━
New capabilities:  [list]
New knowledge:     [patterns learned]
Decisions made:    [ADR references]
Quality:           [audit results]
Growth:            [evolution log entries]
```
