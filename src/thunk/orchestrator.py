"""Turn orchestration for thunk."""

import difflib
import tempfile
from pathlib import Path

from .adapters.base import AgentAdapter
from .adapters.claude import ClaudeCodeSyncAdapter
from .adapters.codex import CodexCLISyncAdapter
from .models import AgentStatus, Phase, ThunkConfig
from .names import generate_unique_name
from .prompts import (
    get_draft_prompt,
    get_peer_review_prompt,
    get_synthesis_prompt,
)
from .session import SessionManager


class TurnOrchestrator:
    """Orchestrates a single turn of planning."""

    def __init__(
        self,
        manager: SessionManager,
        config: ThunkConfig,
    ):
        self.manager = manager
        self.config = config
        self.adapters: dict[str, AgentAdapter] = {}

        # Initialize adapters
        for agent_cfg in config.agents:
            if agent_cfg.enabled:
                if agent_cfg.type == "claude":
                    self.adapters[agent_cfg.id] = ClaudeCodeSyncAdapter(agent_cfg)
                elif agent_cfg.type == "codex":
                    self.adapters[agent_cfg.id] = CodexCLISyncAdapter(agent_cfg)

    def run_turn(self, session_id: str) -> bool:
        """
        Run a complete turn: draft → peer review → synthesis.

        Returns True if successful.
        """
        state = self.manager.load_session(session_id)
        if not state:
            return False

        paths = self.manager.get_paths(session_id)
        turn = state.turn

        # Snapshot dir for debugging this turn
        snapshot_dir = paths.turn_snapshot_dir(turn)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        task = state.task
        user_feedback = self._get_user_feedback(paths, turn)

        # Generate plan IDs for any new agents (lazy initialization)
        # Use collision-aware generator to avoid duplicate plan IDs
        for agent_id in self.adapters:
            if agent_id not in state.agent_plan_ids:
                existing = set(state.agent_plan_ids.values())
                plan_id = generate_unique_name(existing)
                state.agent_plan_ids[agent_id] = plan_id
        self.manager.save_state(state)

        # Phase 1: Draft
        state.phase = Phase.DRAFTING
        self.manager.save_state(state)

        drafts: dict[str, str] = {}
        for agent_id, adapter in self.adapters.items():
            state.agents[agent_id] = AgentStatus.WORKING
            self.manager.save_state(state)

            plan_id = state.agent_plan_ids[agent_id]

            # Persistent plan file (agent reads/writes here)
            plan_file = paths.agent_plan_file(plan_id)

            # Session-wide debug log (append mode)
            session_log = paths.agent_log_file(plan_id)
            session_log.parent.mkdir(parents=True, exist_ok=True)

            # Snapshot file for this turn (for debugging)
            snapshot_file = snapshot_dir / f"{plan_id}-draft.md"

            # Build prompt - agent writes directly to their persistent plan file
            prompt = get_draft_prompt(
                task=task,
                turn=turn,
                output_file=str(plan_file),
                plan_file=str(plan_file) if turn > 1 and plan_file.exists() else "",
                user_feedback=user_feedback,
            )

            # Working directory for agent - use project root so agents can explore
            project_root = self.manager.thunk_dir.parent.resolve()

            # Session file for CLI session continuation across turns
            session_file = paths.agent_session_file(plan_id)
            session_file.parent.mkdir(parents=True, exist_ok=True)

            success, output = adapter.run_sync(
                worktree=project_root,
                prompt=prompt,
                output_file=plan_file,
                log_file=session_log,
                timeout=self.config.timeout,
                session_file=session_file,
                append_log=True,  # Append to session log
            )

            if success:
                content = plan_file.read_text() if plan_file.exists() else output
                drafts[agent_id] = content
                # Save snapshot for debugging
                snapshot_file.write_text(content)
                state.agents[agent_id] = AgentStatus.DONE
            else:
                state.agents[agent_id] = AgentStatus.ERROR
                # Continue with other agents

            self.manager.save_state(state)

        if not drafts:
            state.phase = Phase.ERROR
            self.manager.save_state(state)
            return False

        # Phase 2: Peer Review
        state.phase = Phase.PEER_REVIEW
        self.manager.save_state(state)

        project_root = self.manager.thunk_dir.parent.resolve()

        finals: dict[str, str] = {}
        agent_ids = list(drafts.keys())

        for i, agent_id in enumerate(agent_ids):
            adapter = self.adapters.get(agent_id)
            if not adapter:
                continue

            state.agents[agent_id] = AgentStatus.WORKING
            self.manager.save_state(state)

            plan_id = state.agent_plan_ids[agent_id]

            # Get peer's draft (round-robin)
            peer_idx = (i + 1) % len(agent_ids)
            peer_agent_id = agent_ids[peer_idx]
            peer_plan_id = state.agent_plan_ids[peer_agent_id]
            peer_draft = drafts.get(peer_agent_id, "")

            prompt = get_peer_review_prompt(
                task=task,
                own_draft=drafts[agent_id],
                peer_id=peer_plan_id,  # Use plan_id for anonymity
                peer_draft=peer_draft,
            )

            # Agent writes to their persistent plan file
            plan_file = paths.agent_plan_file(plan_id)
            session_log = paths.agent_log_file(plan_id)
            snapshot_file = snapshot_dir / f"{plan_id}-reviewed.md"

            # Reuse session file for continuation
            session_file = paths.agent_session_file(plan_id)

            success, output = adapter.run_sync(
                worktree=project_root,
                prompt=prompt,
                output_file=plan_file,
                log_file=session_log,
                timeout=self.config.timeout,
                session_file=session_file,
                append_log=True,
            )

            if success:
                content = plan_file.read_text() if plan_file.exists() else output
                finals[agent_id] = content
                snapshot_file.write_text(content)
                state.agents[agent_id] = AgentStatus.DONE
            else:
                # Fall back to draft
                finals[agent_id] = drafts[agent_id]
                state.agents[agent_id] = AgentStatus.ERROR

            self.manager.save_state(state)

        # Phase 3: Synthesis
        state.phase = Phase.SYNTHESIZING
        self.manager.save_state(state)

        synthesis = self._synthesize(task, finals, paths, user_feedback)

        # Write to turns/NNN.md (user-facing canonical file)
        turn_file = paths.turn_file(turn)
        turn_file.parent.mkdir(parents=True, exist_ok=True)
        turn_file.write_text(synthesis)

        # Save snapshot for diffing user edits later
        snapshot_file = turn_file.with_suffix(".snapshot.md")
        snapshot_file.write_text(synthesis)

        # Write synthesis back to each agent's working file
        # This keeps all agents in sync with the canonical state
        for agent_id in self.adapters:
            plan_id = state.agent_plan_ids[agent_id]
            agent_plan_file = paths.root / f"{plan_id}.md"
            agent_plan_file.write_text(synthesis)

        # Transition to user review
        state.phase = Phase.USER_REVIEW
        self.manager.save_state(state)

        return True

    def _get_user_feedback(self, paths, turn: int) -> str:
        """Get user feedback as diff from previous turn.

        Returns a unified diff showing what the user changed in the turn file.
        The turn file starts as the synthesis, user edits it, then we diff.
        """
        if turn < 2:
            return ""

        prev_file = paths.turn_file(turn - 1)
        if not prev_file.exists():
            return ""

        # Check if there's a pre-edit snapshot to diff against
        # (created when synthesis is written, before user edits)
        snapshot_file = prev_file.with_suffix(".snapshot.md")
        if snapshot_file.exists():
            original = snapshot_file.read_text().splitlines()
            edited = prev_file.read_text().splitlines()

            diff_lines = difflib.unified_diff(
                original,
                edited,
                fromfile="synthesis",
                tofile="user-edited",
                lineterm="",
            )
            diff = "\n".join(diff_lines)
            if diff:
                return f"```diff\n{diff}\n```"

        # Fallback: just return the content as "user's current version"
        return f"User's current plan:\n\n{prev_file.read_text()}"

    def _synthesize(
        self,
        task: str,
        agent_plans: dict[str, str],
        paths,
        user_diff: str = "",
    ) -> str:
        """Synthesize agent plans into unified plan.

        Args:
            task: Task description
            agent_plans: Dict mapping agent_id to their reviewed plan
            paths: Session paths
            user_diff: User's changes from previous turn (for turn > 1)
        """
        # If only one agent, just use its output
        if len(agent_plans) == 1:
            return list(agent_plans.values())[0]

        # Use synthesizer agent
        synth_config = self.config.synthesizer
        if synth_config.type == "claude":
            adapter = ClaudeCodeSyncAdapter(synth_config)
        else:
            adapter = CodexCLISyncAdapter(synth_config)

        # Synthesizer writes to a temp file, caller writes to turn file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            synth_file = Path(tmp.name)

        prompt = get_synthesis_prompt(
            task, agent_plans, output_file=str(synth_file), user_diff=user_diff
        )

        log_file = paths.agents / "synthesizer.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Session file for synthesizer continuation across turns
        synth_session_file = paths.agents / "synthesizer" / "cli_session_id.txt"
        synth_session_file.parent.mkdir(parents=True, exist_ok=True)

        project_root = self.manager.thunk_dir.parent.resolve()

        success, output = adapter.run_sync(
            worktree=project_root,
            prompt=prompt,
            output_file=synth_file,
            log_file=log_file,
            timeout=self.config.timeout,
            session_file=synth_session_file,
            append_log=True,
        )

        if success and synth_file.exists():
            result = synth_file.read_text()
            synth_file.unlink()  # Clean up temp file
            return result

        synth_file.unlink(missing_ok=True)

        # Fallback: just concatenate
        result = f"# Plan: {task}\n\n"
        result += "## Combined from agents\n\n"
        for agent_id, plan in agent_plans.items():
            result += f"### From {agent_id}\n\n{plan}\n\n---\n\n"
        return result

    def get_diff(self, session_id: str) -> str:
        """Get diff between previous turn and current turn's user edits."""
        state = self.manager.load_session(session_id)
        if not state or state.turn < 2:
            return ""

        paths = self.manager.get_paths(session_id)
        prev_file = paths.turn_file(state.turn - 1)
        curr_file = paths.turn_file(state.turn)

        if not prev_file.exists() or not curr_file.exists():
            return ""

        prev_lines = prev_file.read_text().splitlines()
        curr_lines = curr_file.read_text().splitlines()

        diff = difflib.unified_diff(
            prev_lines,
            curr_lines,
            fromfile=f"turn-{state.turn - 1:03d}.md",
            tofile=f"turn-{state.turn:03d}.md",
            lineterm="",
        )

        return "\n".join(diff)
