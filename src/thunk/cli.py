"""CLI entry points for thunk."""

import json
import sys
from pathlib import Path

import click

from .models import Phase, ThunkConfig
from .orchestrator import TurnOrchestrator
from .session import SessionManager


def output_json(data: dict, pretty: bool = False) -> None:
    """Output JSON to stdout."""
    if pretty:
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(json.dumps(data))


@click.group()
@click.option(
    "--thunk-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to .thunk directory (default: .thunk in current dir)",
)
@click.option("--pretty", is_flag=True, help="Pretty print JSON output")
@click.pass_context
def main(ctx: click.Context, thunk_dir: Path | None, pretty: bool) -> None:
    """Thunk: Multi-agent ensemble planning CLI."""
    ctx.ensure_object(dict)
    ctx.obj["manager"] = SessionManager(thunk_dir)
    ctx.obj["pretty"] = pretty


@main.command()
@click.argument("feature")
@click.pass_context
def init(ctx: click.Context, feature: str) -> None:
    """Start a new planning session."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    state = manager.create_session(feature)

    # Update to drafting phase (in real impl, this would spawn agents)
    state.phase = Phase.DRAFTING
    manager.save_state(state)

    output_json(
        {
            "session_id": state.session_id,
            "turn": state.turn,
            "phase": state.phase.value,
            "hint": "call wait to block until turn complete",
        },
        pretty,
    )


@main.command("list")
@click.pass_context
def list_sessions(ctx: click.Context) -> None:
    """List all planning sessions."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    sessions = manager.list_sessions()

    output_json(
        {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "feature": s.feature,
                    "turn": s.turn,
                    "phase": s.phase.value,
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in sessions
            ]
        },
        pretty,
    )


@main.command()
@click.option("--session", "session_id", required=True, help="Session ID")
@click.pass_context
def status(ctx: click.Context, session_id: str) -> None:
    """Check session status without blocking."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    state = manager.load_session(session_id)
    if not state:
        output_json({"error": f"Session {session_id} not found"}, pretty)
        sys.exit(1)

    paths = manager.get_paths(session_id)
    turn_file = paths.turn_file(state.turn)

    output_json(
        {
            "session_id": state.session_id,
            "turn": state.turn,
            "phase": state.phase.value,
            "file": str(turn_file) if turn_file.exists() else None,
            "has_questions": manager.has_questions(session_id),
            "agents": {k: v.value for k, v in state.agents.items()},
        },
        pretty,
    )


@main.command()
@click.option("--session", "session_id", required=True, help="Session ID")
@click.option("--timeout", type=int, default=None, help="Timeout in seconds")
@click.pass_context
def wait(ctx: click.Context, session_id: str, timeout: int | None) -> None:
    """Block until current turn is complete."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    state = manager.load_session(session_id)
    if not state:
        output_json({"error": f"Session {session_id} not found"}, pretty)
        sys.exit(1)

    paths = manager.get_paths(session_id)
    turn_file = paths.turn_file(state.turn)

    # If already in user_review or approved, just return status
    if state.phase == Phase.USER_REVIEW:
        output_json(
            {
                "turn": state.turn,
                "phase": state.phase.value,
                "file": str(turn_file),
                "has_questions": manager.has_questions(session_id),
                "hint": "User should edit file, then call continue or approve",
            },
            pretty,
        )
        return

    if state.phase == Phase.APPROVED:
        output_json(
            {
                "turn": state.turn,
                "phase": state.phase.value,
                "file": str(paths.root / "PLAN.md"),
                "hint": "Planning complete",
            },
            pretty,
        )
        return

    # If in drafting/peer_review/synthesizing phase, run the turn
    if state.phase in (Phase.DRAFTING, Phase.INITIALIZING, Phase.PEER_REVIEW, Phase.SYNTHESIZING):
        config = ThunkConfig.default()
        if timeout:
            config.timeout = timeout
        orchestrator = TurnOrchestrator(manager, config)

        success = orchestrator.run_turn(session_id)

        # Reload state after orchestrator completes
        state = manager.load_session(session_id)
        if not state:
            output_json({"error": "Session disappeared during turn"}, pretty)
            sys.exit(1)

        if success:
            output_json(
                {
                    "turn": state.turn,
                    "phase": state.phase.value,
                    "file": str(turn_file),
                    "has_questions": manager.has_questions(session_id),
                    "hint": "User should edit file, then call continue or approve",
                },
                pretty,
            )
        else:
            output_json(
                {
                    "turn": state.turn,
                    "phase": state.phase.value,
                    "error": "Turn failed",
                    "hint": "Check agent logs in .thunk/sessions/<id>/agents/",
                },
                pretty,
            )
            sys.exit(1)
        return

    # Error or unknown phase
    output_json(
        {
            "turn": state.turn,
            "phase": state.phase.value,
            "error": f"Unexpected phase: {state.phase.value}",
        },
        pretty,
    )
    sys.exit(1)


@main.command("continue")
@click.option("--session", "session_id", required=True, help="Session ID")
@click.pass_context
def continue_session(ctx: click.Context, session_id: str) -> None:
    """User done editing, start next turn."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    state = manager.load_session(session_id)
    if not state:
        output_json({"error": f"Session {session_id} not found"}, pretty)
        sys.exit(1)

    if state.phase != Phase.USER_REVIEW:
        output_json(
            {
                "error": f"Cannot continue from phase {state.phase.value}",
                "hint": "Wait for user_review phase before continuing",
            },
            pretty,
        )
        sys.exit(1)

    # Start next turn
    state.turn += 1
    state.phase = Phase.DRAFTING
    manager.save_state(state)

    output_json(
        {
            "turn": state.turn,
            "phase": state.phase.value,
            "hint": "call wait to block until turn complete",
        },
        pretty,
    )


@main.command()
@click.option("--session", "session_id", required=True, help="Session ID")
@click.pass_context
def approve(ctx: click.Context, session_id: str) -> None:
    """Lock current plan as final."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    state = manager.load_session(session_id)
    if not state:
        output_json({"error": f"Session {session_id} not found"}, pretty)
        sys.exit(1)

    if state.phase != Phase.USER_REVIEW:
        output_json(
            {
                "error": f"Cannot approve from phase {state.phase.value}",
                "hint": "Wait for user_review phase before approving",
            },
            pretty,
        )
        sys.exit(1)

    # Check for unanswered questions
    if manager.has_questions(session_id):
        output_json(
            {
                "error": "Cannot approve with unanswered questions",
                "hint": "Answer all questions in the plan file first",
            },
            pretty,
        )
        sys.exit(1)

    # Create symlink to approved turn
    paths = manager.get_paths(session_id)
    turn_file = paths.turn_file(state.turn)
    plan_link = paths.root / "PLAN.md"

    if plan_link.exists():
        plan_link.unlink()
    plan_link.symlink_to(turn_file.relative_to(paths.root))

    state.phase = Phase.APPROVED
    manager.save_state(state)

    output_json(
        {
            "phase": state.phase.value,
            "final_turn": state.turn,
            "plan_path": str(plan_link),
            "hint": "Planning complete. Plan is ready for implementation.",
        },
        pretty,
    )


@main.command()
@click.option("--session", "session_id", required=True, help="Session ID")
@click.pass_context
def clean(ctx: click.Context, session_id: str) -> None:
    """Remove session and its data."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    if manager.clean_session(session_id):
        output_json({"cleaned": True, "session_id": session_id}, pretty)
    else:
        output_json({"error": f"Session {session_id} not found"}, pretty)
        sys.exit(1)


@main.command()
@click.option("--session", "session_id", required=True, help="Session ID")
@click.pass_context
def diff(ctx: click.Context, session_id: str) -> None:
    """Show changes between turns."""
    manager: SessionManager = ctx.obj["manager"]
    pretty: bool = ctx.obj["pretty"]

    state = manager.load_session(session_id)
    if not state:
        output_json({"error": f"Session {session_id} not found"}, pretty)
        sys.exit(1)

    if state.turn < 2:
        output_json({"error": "Need at least 2 turns to show diff"}, pretty)
        sys.exit(1)

    paths = manager.get_paths(session_id)
    prev_file = paths.turn_file(state.turn - 1)
    curr_file = paths.turn_file(state.turn)

    if not prev_file.exists() or not curr_file.exists():
        output_json({"error": "Turn files not found"}, pretty)
        sys.exit(1)

    # Simple line-based diff
    prev_lines = prev_file.read_text().splitlines()
    curr_lines = curr_file.read_text().splitlines()

    import difflib

    diff_lines = list(
        difflib.unified_diff(
            prev_lines,
            curr_lines,
            fromfile=f"turn-{state.turn - 1:03d}.md",
            tofile=f"turn-{state.turn:03d}.md",
            lineterm="",
        )
    )

    output_json(
        {
            "from_turn": state.turn - 1,
            "to_turn": state.turn,
            "diff": "\n".join(diff_lines),
        },
        pretty,
    )


if __name__ == "__main__":
    main()
