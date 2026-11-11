"""The scenarios, as data. ``{code}`` is replaced by the run's codename so one
run's facts are not answered by an earlier run's."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    """One thing that happens in a seeded conversation."""

    kind: str  # turn | memory_add | memory_remove | task | crash
    user: str = ""
    assistant: str = ""
    text: str = ""


@dataclass(frozen=True)
class Scenario:
    name: str
    # Each inner tuple is one conversation, in order.
    conversations: tuple[tuple[Step, ...], ...]
    probe: str
    expect: tuple[str, ...] = ()
    # Must not be presented as current: absent, or only on a line marked not current.
    stale: tuple[str, ...] = ()
    # Must not appear at all.
    forbid: tuple[str, ...] = ()
    # An injected item mentioning none of these is counted as irrelevant.
    subject: tuple[str, ...] = ()
    expect_nothing: bool = False
    steps_note: str = field(default="", compare=False)


def turn(user: str, assistant: str) -> Step:
    return Step("turn", user=user, assistant=assistant)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="preference_change",
        conversations=(
            (turn("For project {code}, I always want status reports as long-form prose documents.",
                  "Understood: {code} status reports as long-form prose."),),
            (turn("Change of plan for project {code}: I no longer want prose. Send status reports as a "
                  "five-bullet summary from now on.",
                  "Noted. {code} status reports are now a five-bullet summary; the prose format is retired."),),
        ),
        probe="How should I format the next status report for project {code}?",
        expect=("five-bullet",),
        stale=("long-form prose",),
        subject=("{code}", "status report", "bullet", "prose"),
    ),
    Scenario(
        name="corrected_fact",
        conversations=(
            (turn("The approved budget for the {code} pilot is $8,000.", "Recorded: {code} pilot budget $8,000."),
             turn("Correction: I misread the sheet. The {code} pilot budget is $12,500, not $8,000.",
                  "Corrected: the {code} pilot budget is $12,500. The $8,000 figure was wrong.")),
        ),
        probe="What is the approved budget for the {code} pilot?",
        expect=("12,500",),
        stale=("8,000",),
        subject=("{code}", "budget", "pilot"),
    ),
    Scenario(
        name="interrupted_work",
        conversations=(
            (Step("task", text="Migrate the {code} ledger to Postgres"),
             turn("On the {code} ledger migration: schema and dual-writes are done. The backfill is still pending.",
                  "Status saved: schema done, dual-writes done, backfill pending for the {code} ledger migration."),
             Step("crash")),
        ),
        probe="Let's pick up the {code} ledger migration where we stopped.",
        expect=("Migrate the {code} ledger to Postgres",),
        subject=("{code}", "ledger", "migration", "backfill"),
    ),
    Scenario(
        name="cross_session_decision",
        conversations=(
            (turn("For {code} we compared Memcached and Redis for the session cache. We decided on Redis because "
                  "we need per-key expiry.",
                  "Decision recorded for {code}: Redis for the session cache, chosen for per-key expiry."),),
        ),
        probe="Which session cache did we choose for {code}, and why?",
        expect=("Redis", "expiry"),
        subject=("{code}", "redis", "cache", "memcached"),
    ),
    Scenario(
        name="unrelated_project",
        conversations=(
            (turn("The {code} launch is priced at $49 per seat, billed annually.",
                  "Recorded: {code} launch pricing is $49 per seat, annual billing."),),
        ),
        probe="How do I vertically center a flexbox child in CSS?",
        expect_nothing=True,
        subject=("css", "flexbox", "center"),
    ),
    Scenario(
        name="deletion",
        conversations=(
            (Step("memory_add", text="The {code} door code is 4417-ELM."),
             Step("memory_remove", text="The {code} door code is 4417-ELM.")),
        ),
        probe="What is the {code} door code?",
        forbid=("4417-ELM",),
        subject=("{code}", "door code"),
    ),
)
