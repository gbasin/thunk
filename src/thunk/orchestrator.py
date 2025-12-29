"""Turn orchestration for thunk."""

import difflib
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
        turn_agents_dir = paths.agents / f"turn-{turn:03d}"
        turn_agents_dir.mkdir(parents=True, exist_ok=True)

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

            # Agent's working plan file (contains synthesis from previous turn)
            plan_id = state.agent_plan_ids[agent_id]
            agent_plan_file = paths.root / f"{plan_id}.md"
            draft_file = turn_agents_dir / f"{agent_id}-draft.md"
            log_file = turn_agents_dir / f"{agent_id}-draft.log"

            # Build prompt - agent reads their own plan file, writes to draft
            prompt = get_draft_prompt(
                task=task,
                turn=turn,
                output_file=str(draft_file),
                plan_file=str(agent_plan_file) if turn > 1 else "",
                user_feedback=user_feedback,
            )

            # Working directory for agent
            workdir = paths.root / "workdir" / agent_id
            workdir.mkdir(parents=True, exist_ok=True)

            # Session file for CLI session continuation across turns
            session_file = paths.agent_session_file(agent_id)
            session_file.parent.mkdir(parents=True, exist_ok=True)

            success, output = adapter.run_sync(
                worktree=workdir,
                prompt=prompt,
                output_file=draft_file,
                log_file=log_file,
                timeout=self.config.timeout,
                session_file=session_file,
            )

            if success:
                drafts[agent_id] = draft_file.read_text() if draft_file.exists() else output
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

        finals: dict[str, str] = {}
        agent_ids = list(drafts.keys())

        for i, agent_id in enumerate(agent_ids):
            adapter = self.adapters.get(agent_id)
            if not adapter:
                continue

            state.agents[agent_id] = AgentStatus.WORKING
            self.manager.save_state(state)

            # Get peer's draft (round-robin)
            peer_id = agent_ids[(i + 1) % len(agent_ids)]
            peer_draft = drafts.get(peer_id, "")

            prompt = get_peer_review_prompt(
                task=task,
                own_draft=drafts[agent_id],
                peer_id=peer_id,
                peer_draft=peer_draft,
            )

            final_file = turn_agents_dir / f"{agent_id}-final.md"
            log_file = turn_agents_dir / f"{agent_id}-final.log"
            workdir = paths.root / "workdir" / agent_id

            # Reuse session file for continuation
            session_file = paths.agent_session_file(agent_id)

            success, output = adapter.run_sync(
                worktree=workdir,
                prompt=prompt,
                output_file=final_file,
                log_file=log_file,
                timeout=self.config.timeout,
                session_file=session_file,
            )

            if success:
                finals[agent_id] = final_file.read_text() if final_file.exists() else output
                state.agents[agent_id] = AgentStatus.DONE
            else:
                # Fall back to draft
                finals[agent_id] = drafts[agent_id]
                state.agents[agent_id] = AgentStatus.ERROR

            self.manager.save_state(state)

        # Phase 3: Synthesis
        state.phase = Phase.SYNTHESIZING
        self.manager.save_state(state)

        synthesis = self._synthesize(task, finals, turn_agents_dir)

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
        turn_agents_dir: Path,
    ) -> str:
        """Synthesize agent plans into unified plan."""
        # If only one agent, just use its output
        if len(agent_plans) == 1:
            return list(agent_plans.values())[0]

        # Use synthesizer agent
        synth_config = self.config.synthesizer
        if synth_config.type == "claude":
            adapter = ClaudeCodeSyncAdapter(synth_config)
        else:
            adapter = CodexCLISyncAdapter(synth_config)

        prompt = get_synthesis_prompt(task, agent_plans)

        synth_file = turn_agents_dir / "synthesis.md"
        log_file = turn_agents_dir / "synthesis.log"
        workdir = turn_agents_dir / "synth-workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        success, output = adapter.run_sync(
            worktree=workdir,
            prompt=prompt,
            output_file=synth_file,
            log_file=log_file,
            timeout=self.config.timeout,
        )

        if success and synth_file.exists():
            return synth_file.read_text()

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
