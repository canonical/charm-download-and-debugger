# Skill: Juju Charm Codebase Navigation & Support Analysis

## Context & Workspace Scope
This workspace contains unzipped Juju charms downloaded from a live Juju environment. Juju charms are event-driven software packages that automate operational lifecycles (deployment, configuration, scaling, integration, self-healing).

Your role as an AI assistant is to help Juju support engineers rapidly diagnose, trace, and resolve charm failures using this code.

---

## 1. Directory Paradigms & Architecture Detection

When analyzing a charm inside <charm_name>/src/, first identify which of the following three architectural paradigms it uses:

### Paradigm A: Classic Hooks & charmhelpers (e.g., OpenStack / Machine Charms)
Identified by hooks/ and charmhelpers/ directories.

```
<charm_name>/src/
├── metadata.yaml        # Defines relations (provides/requires/peers), interfaces, summary
├── config.yaml          # User-configurable parameters
├── manifest.yaml        # Build manifest & source revision tracking
├── hardening.yaml       # Security hardening profiles (e.g., CIS benchmarks)
├── actions.yaml         # Action definitions (parameters & descriptions)
├── actions/             # Executable scripts for actions (e.g., actions/forget-cluster-node)
├── hooks/               # Core event handlers called by Juju agent (bash or python scripts)
│   ├── install
│   ├── config-changed
│   └── <relation>-relation-changed
├── charmhelpers/        # Legacy Canonical Python library for OS/system automation
├── templates/           # Jinja2 configuration templates rendered during hooks
├── files/               # Static configuration files or binaries copied to host
├── Makefile             # Build targets & tests
└── README.md
```

Execution & Flow:
1. Juju executes scripts in hooks/ directly (e.g., hooks/config-changed or hooks/amqp-relation-changed).
2. Python scripts imported by hooks rely on charmhelpers/ and internal helper modules.
3. Templates in templates/ are populated using values from config.yaml or relation data and written to host paths (e.g., /etc/rabbitmq/).
4. juju run-action executes the script located directly inside actions/<action_name>.

---

### Paradigm B: Modern Operator Framework (ops)
Identified by src/charm.py and charmcraft.yaml.

```
<charm_name>/src/
├── charmcraft.yaml      # Metadata, charm bases, dependencies, relations, actions
├── config.yaml          # Config settings (if not embedded in charmcraft.yaml)
├── src/
│   └── charm.py         # Main entry point class inheriting from ops.charm.CharmBase
├── lib/charms/<charm>/  # Fetchable charm libraries for relation interfaces
├── templates/           # Jinja2 templates (if applicable)
└── tests/               # Scenario or Harness unit/integration tests
```

Execution & Flow:
1. All Juju events route through src/charm.py.
2. Look inside __init__ for self.framework.observe(self.on.<event>, self.<handler>).
3. K8s sidecar container interactions use container.pebble_plan or container.add_layer().

---

### Paradigm C: Reactive Framework
Identified by reactive/ and layer.yaml.

```
<charm_name>/src/
├── layer.yaml           # Reactive layer dependencies
├── reactive/            # Python files with @when, @when_not, @hook decorators
└── hooks/               # Standard boilerplate hooks routing to the reactive engine
```

Execution & Flow:
1. Logic lives in reactive/*.py.
2. Execution is driven by flags set/cleared across relations and lifecycle events.

---

## 2. Error-to-Code Lookup Matrix

Use this matrix to immediately pinpoint source files when given log output or juju status error states:

| Status / Log Error Message | Primary Target to Inspect | What to Search For |
| :--- | :--- | :--- |
| hook failed: "config-changed" | hooks/config-changed or src/charm.py | self.on.config_changed or config_changed() |
| hook failed: "<rel>-relation-changed" | hooks/<rel>-relation-changed or src/charm.py | Relation event observer or lib/charms/<charm>/ |
| blocked status without error | src/charm.py or reactive/*.py | unit.status = BlockedStatus(...) or set_flag('blocked') |
| Action execution failure | actions/ or src/charm.py | Script inside actions/<name> or self.on.<name>_action |
| Jinja2 Template error | templates/ and config.yaml | Unset variables or missing relation keys passed to render() |
| pebble / container errors | src/charm.py | container.pebble_plan, pebble_ready, or layer definition |

---

## 3. Relation Data Exchange Patterns

Charms exchange key-value data across relation interfaces. Use these rules to trace integration bugs:

### Modern Ops Framework (ops)
- Writing Data: Look for event.relation.data[self.app] (app-data) or event.relation.data[self.unit] (unit-data).
- Reading Data: Look for event.relation.data[event.app] or event.relation.data[event.unit].
- Interface Libraries: Check lib/charms/<charm_name>/v<N>/<library_name>.py for data schema definitions and custom events.

### Legacy / Charmhelpers Framework
- Writing Data: Search for relation_set(key=val) or relation_set(relation_id, ...) calls.
- Reading Data: Search for relation_get(key) or relation_get().
- Peer Relations: Check peer_relation_deprecated or config_get() wrappers in hooks/.

---

## 4. AI Operating Directives

To maximize efficiency and accuracy during investigation:

1. Rule of Targeted Search: Do NOT scan all files blindly. Always start by reading metadata.yaml or charmcraft.yaml to establish the charm name, relation interfaces, and container definitions.
2. Top-Down Hook Tracing: When investigating a hook failure, locate the exact file matching that hook name first. Trace imports and function calls downward.
3. Template Verification: If a failure mentions configuration rendering or syntax errors, locate the Jinja2 template in templates/ and map every variable ({{ var }}) back to config.yaml or relation data keys.
4. Distinguish Runtime Context: Determine whether the charm is K8s sidecar (uses Pebble & containers in metadata) or Machine (uses systemd, apt packages, and charmhelpers.fetch).
