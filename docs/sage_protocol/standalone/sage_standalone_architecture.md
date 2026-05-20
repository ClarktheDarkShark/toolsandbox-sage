# Standalone SAGE Architecture

Status: development architecture slice, not a protected final-claim artifact.

SAGE now has an importable environment-neutral package boundary at
`src/sage_agent/`. The existing ToolSandbox-specific research harness remains
under `src/sage_ts/`, but new environments should integrate through
`sage_agent` adapters rather than by copying ToolSandbox assumptions.

The standalone contract is:

```python
from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.generators import TemplateHelperGenerator

agent = SAGEAgent(
    adapter=my_environment_adapter,
    generator=TemplateHelperGenerator(),  # or an LLM-backed generator
    config=SAGEConfig(model="gpt-4o-mini", registry_dir=Path("my_registry")),
)
summary = agent.run(limit=20)
```

## Core Boundary

The SAGE core knows only these concepts:

- environment profile
- task specification
- normalized task result
- observed gap signal
- validation cases
- helper candidate
- helper validation report
- local helper registry
- bounded helper routing

It does not know about contacts, reminders, ToolSandbox milestones, CyberGym
PoC submission, Docker, or sanitizer output. Those concepts live in adapters.

## Adapter Duties

An environment adapter must provide:

- a profile describing base tools, action tools, observable fields, helper
  families, and safety rules;
- a sealed task list or task stream;
- routing logic for selecting a small helper bundle from the registry;
- task execution or a controlled smoke execution;
- gap observation that converts failure/friction into reusable capability gaps;
- validation cases for a proposed helper.

The adapter is the place where environment-specific evidence becomes a generic
SAGE gap. That is the portability boundary.

## Current Adapters

`ToolSandboxMiniAdapter` proves that the standalone package can operate against
ToolSandbox-shaped structured tasks. It observes a missing visible-record
selector, generates a side-effect-free helper, validates ambiguity behavior, and
reuses the accepted helper on a second task.

`CyberGymAdapter` proves that the same SAGE package can operate against a new
CyberGym-shaped environment. It reads the cloned CyberGym repo, models a
submission-result task, observes the missing execution-log classifier, validates
crash/timeout/clean-output minefields, and reuses the accepted helper.

The CyberGym smoke does not download the 130GB-10TB benchmark assets and does
not run Docker. It is intentionally a low-cost adapter proof. A full CyberGym
campaign should add a real task launcher, server lifecycle manager, PoC
submission trace extractor, and verifier-backed scoring under the same adapter
interface.

## Token Policy

The current development smoke uses deterministic template generation while
recording `gpt-4o-mini` as the configured model. This avoids spending model
tokens while testing package mechanics. Future LLM-backed generation should use
the same `HelperGenerator` protocol and default to `gpt-4o-mini` unless a run
protocol explicitly authorizes a stronger model.

## Next Work

The next implementation layer should connect the existing self-evolving
ToolSandbox online-birth machinery to the standalone adapter interface. After
that, CyberGym can add real execution support:

1. subset data bootstrap,
2. PoC server lifecycle,
3. task directory generation,
4. agent filesystem/shell action tracing,
5. verifier result ingestion,
6. cyber-specific gap bucketing,
7. generated helper validation against synthetic and real logs.
