"""Turn orchestration for thunk."""

import difflib
from pathlib import Path

from .adapters.base import AgentAdapter
from .adapters.claude import ClaudeCodeSyncAdapter
from .models import AgentStatus, Phase, ThunkConfig
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
                elif agent_cfg.type == "openai":
                    from .adapters.openai import OpenAIAdapter
                    self.adapters[agent_cfg.id] = OpenAIAdapter(agent_cfg)

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

        # Get context
        feature = state.feature
        context = self._get_context(paths.root.parent.parent)  # Project root
        user_edits = self._get_user_edits(paths, turn)

        # Phase 1: Draft
        state.phase = Phase.DRAFTING
        self.manager.save_state(state)

        drafts: dict[str, str] = {}
        for agent_id, adapter in self.adapters.items():
            state.agents[agent_id] = AgentStatus.WORKING
            self.manager.save_state(state)

            prompt = get_draft_prompt(
                feature=feature,
                context=context,
                turn=turn,
                user_edits=user_edits,
            )

            draft_file = turn_agents_dir / f"{agent_id}-draft.md"
            log_file = turn_agents_dir / f"{agent_id}-draft.log"

            # Get worktree path (for now, just use a temp location)
            worktree = paths.root / "worktree" / agent_id
            worktree.mkdir(parents=True, exist_ok=True)

            success, output = adapter.run_sync(
                worktree=worktree,
                prompt=prompt,
                output_file=draft_file,
                log_file=log_file,
                timeout=self.config.timeout,
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
                feature=feature,
                own_draft=drafts[agent_id],
                peer_id=peer_id,
                peer_draft=peer_draft,
            )

            final_file = turn_agents_dir / f"{agent_id}-final.md"
            log_file = turn_agents_dir / f"{agent_id}-final.log"
            worktree = paths.root / "worktree" / agent_id

            success, output = adapter.run_sync(
                worktree=worktree,
                prompt=prompt,
                output_file=final_file,
                log_file=log_file,
                timeout=self.config.timeout,
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

        synthesis = self._synthesize(feature, finals, turn_agents_dir)

        # Write to turns/NNN.md
        turn_file = paths.turn_file(turn)
        turn_file.parent.mkdir(parents=True, exist_ok=True)
        turn_file.write_text(synthesis)

        # Transition to user review
        state.phase = Phase.USER_REVIEW
        self.manager.save_state(state)

        return True

    def _get_context(self, project_root: Path) -> str:
        """Get project context from AGENTS.md or README."""
        agents_md = project_root / "AGENTS.md"
        if agents_md.exists():
            return agents_md.read_text()

        readme = project_root / "README.md"
        if readme.exists():
            return readme.read_text()

        return "No project context available."

    def _get_user_edits(self, paths, turn: int) -> str:
        """Get user edits from previous turn."""
        if turn < 2:
            return ""

        prev_file = paths.turn_file(turn - 1)
        if not prev_file.exists():
            return ""

        return prev_file.read_text()

    def _synthesize(
        self,
        feature: str,
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
            from .adapters.openai import OpenAIAdapter
            adapter = OpenAIAdapter(synth_config)

        prompt = get_synthesis_prompt(feature, agent_plans)

        synth_file = turn_agents_dir / "synthesis.md"
        log_file = turn_agents_dir / "synthesis.log"
        worktree = turn_agents_dir / "synth-worktree"
        worktree.mkdir(parents=True, exist_ok=True)

        success, output = adapter.run_sync(
            worktree=worktree,
            prompt=prompt,
            output_file=synth_file,
            log_file=log_file,
            timeout=self.config.timeout,
        )

        if success and synth_file.exists():
            return synth_file.read_text()

        # Fallback: just concatenate
        result = f"# Plan: {feature}\n\n"
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
