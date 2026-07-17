# Memory Stack — Three-Layer Architecture

> From Nexus: EvoKG (relations) + ExperienceBank (samples) + WorldModel (understanding)

## Layer 1: Short-Term (Session Memory)

Scope: Current conversation
Storage: Claude Code context window
Lifecycle: Cleared when session ends
Content: Active file context, recent operations, user intent

## Layer 2: Mid-Term (Cross-Session Knowledge)

Scope: Project-level, persists across sessions
Storage: Memory MCP (`mcp__memory`)
Content:
- `entityType: Project` — project overview, tech stack, conventions
- `entityType: Decision` — architecture decisions, rationale
- `entityType: BugPattern` — encountered bugs and fixes
- `entityType: UserPreference` — user's coding style, preferences
- `entityType: Capability` — what CC can do (tools, skills, MCPs)

### Memory Operations

**Create** (when discovery happens):
```
mcp__memory__create_entities([{
  name: "pattern-name",
  entityType: "BugPattern|Decision|...",
  observations: ["what", "why", "fix", "date"]
}])
```

**Recall** (before acting):
```
mcp__memory__search_nodes(query="relevant keywords")
```

**Connect** (finding relationships):
```
mcp__memory__create_relations([{
  from: "entity-a", to: "entity-b", relationType: "depends_on|causes|improves"
}])
```

## Layer 3: Long-Term (Code Knowledge Graph)

Scope: Cross-project, code-level
Storage: Codebase-memory MCP (Neo4j)
Content: Functions, classes, call graphs, dependency clusters

### Indexed Projects
- grok-build: 83,820 nodes, 532,897 edges
- nexus_agent: 10,331 nodes, 42,192 edges

### Query Patterns
- `search_graph(query="function name")` — find symbols
- `trace_path(function_name="...", direction="outbound")` — find callers/callees
- `query_graph(query="MATCH ...")` — complex Cypher queries
- `get_architecture(aspects=["all"])` — cluster analysis

## Memory Health Rules

1. Mid-term entities should be reviewed monthly (no stale knowledge)
2. Long-term indices should be refreshed after major code changes
3. Bug patterns that occur 3+ times → create permanent skill/check
4. Project entities without activity for 90 days → archive

## From Experience to Pattern

Nexus had ExperienceBank → TrainingSample pipeline.
CC equivalent:

```
Bug encountered
    → Fix applied
        → Memory recorded (BugPattern entity)
            → Pattern recognized next time
                → Skill auto-suggests fix
```
