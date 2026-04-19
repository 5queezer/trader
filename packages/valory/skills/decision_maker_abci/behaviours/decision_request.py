# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2026 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This module contains the behaviour of the skill which is responsible for requesting a decision from the mech."""

import csv
import json
from dataclasses import asdict
from typing import Any, Dict, Generator, List, Optional
from uuid import uuid4

from packages.valory.skills.decision_maker_abci.behaviours.base import (
    DecisionMakerBaseBehaviour,
)
from packages.valory.skills.decision_maker_abci.payloads import DecisionRequestPayload
from packages.valory.skills.decision_maker_abci.states.decision_request import (
    DecisionRequestRound,
)
from packages.valory.skills.market_manager_abci.bets import BINARY_N_SLOTS
from packages.valory.skills.mech_interact_abci.states.base import MechMetadata


class DecisionRequestBehaviour(DecisionMakerBaseBehaviour):
    """A behaviour in which the agents prepare a tx to initiate a request to a mech to determine the answer to a bet."""

    matching_round = DecisionRequestRound

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Behaviour."""
        super().__init__(**kwargs)
        self._metadata: Optional[MechMetadata] = None
        self._metadata_list: List[MechMetadata] = []

    @property
    def metadata(self) -> Dict[str, str]:
        """Get the metadata as a dictionary."""
        return asdict(self._metadata)  # type: ignore[arg-type]

    @property
    def n_slots_supported(self) -> bool:
        """Whether the behaviour supports the current number of slots as it currently only supports binary decisions."""
        return self.params.slot_count == BINARY_N_SLOTS

    def setup(self) -> None:
        """Setup behaviour."""
        if not self.n_slots_supported or self.benchmarking_mode.enabled:
            return

        sampled_bet = self.sampled_bet
        prompt_params = dict(
            question=sampled_bet.title, yes=sampled_bet.yes, no=sampled_bet.no
        )
        prompt = self.params.prompt_template.substitute(prompt_params)
        primary_tool = self.synchronized_data.mech_tool
        request_context = sampled_bet.to_request_context()

        # Determine ensemble tools. Chatui override wins over skill-YAML default
        # so users can tune it at runtime via the "Change Agent Behavior" prompt.
        chatui_ensemble_size = getattr(
            self.shared_state.chatui_config, "ensemble_size", None
        )
        ensemble_size = (
            chatui_ensemble_size
            if isinstance(chatui_ensemble_size, int) and chatui_ensemble_size >= 1
            else self.params.ensemble_size
        )
        if ensemble_size > 1 and self.synchronized_data.is_policy_set:
            policy = self.synchronized_data.policy
            top_tools = policy.select_n_tools(ensemble_size)
            # Ensure the consensus-agreed primary tool is included
            if primary_tool not in top_tools:
                top_tools = [primary_tool] + top_tools[: ensemble_size - 1]
        else:
            top_tools = [primary_tool]

        # Create metadata for each tool in the ensemble
        self._metadata_list = []
        for tool in top_tools:
            nonce = str(uuid4())
            metadata = MechMetadata(
                prompt, tool, nonce, request_context=request_context
            )
            self._metadata_list.append(metadata)

        # Keep backwards compatibility: _metadata points to the first (primary) entry
        self._metadata = self._metadata_list[0] if self._metadata_list else None

        msg = f"Prepared {len(self._metadata_list)} metadata entries for ensemble request (tools: {[t for t in top_tools]})."
        self.context.logger.info(msg)

    def initialize_bet_id_row_manager(self) -> Dict[str, List[int]]:
        """Initialization of the dictionary used to traverse mocked tool responses."""
        bets_mapping: Dict[str, List[int]] = {}
        dataset_filepath = (
            self.params.store_path / self.benchmarking_mode.dataset_filename
        )

        with open(dataset_filepath, mode="r") as file:
            reader = csv.DictReader(file)
            for row_number, row in enumerate(reader, start=1):
                question_id = row[self.benchmarking_mode.question_id_field]
                if question_id not in bets_mapping:
                    bets_mapping[question_id] = []
                bets_mapping[question_id].append(row_number)
        return bets_mapping

    def async_act(self) -> Generator:
        """Do the action."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            self.shared_state.mech_timed_out = False
            payload_content = None
            mocking_mode: Optional[bool] = self.benchmarking_mode.enabled
            if self._metadata_list and self.n_slots_supported:
                mech_requests = [asdict(m) for m in self._metadata_list]
                payload_content = json.dumps(mech_requests, sort_keys=True)
            if not self.n_slots_supported:
                mocking_mode = None

            if self.benchmarking_mode.enabled:
                # check if the bet_id_row_manager has been loaded already
                if len(self.shared_state.bet_id_row_manager) == 0:
                    bets_mapping = self.initialize_bet_id_row_manager()
                    self.shared_state.bet_id_row_manager = bets_mapping

            agent = self.context.agent_address
            payload = DecisionRequestPayload(agent, payload_content, mocking_mode)
        yield from self.finish_behaviour(payload)
