#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from enum import Enum
from typing import Any, Callable


class ContractState(str, Enum):
    NO_CONTRACT = "NO_CONTRACT"
    GO_BOARD = "GO_BOARD"
    ACQUIRE_ORDER = "ACQUIRE_ORDER"
    EXECUTING = "EXECUTING"


class ContractExecuteState(str, Enum):
    IDLE = "IDLE"
    MOVE_TO_WORKSITE = "MOVE_TO_WORKSITE"
    PERFORM_ACTION = "PERFORM_ACTION"



_ALLOWED_CONTRACT_TRANSITIONS = {
    ContractState.NO_CONTRACT: {ContractState.GO_BOARD, ContractState.EXECUTING},
    ContractState.GO_BOARD: {ContractState.ACQUIRE_ORDER, ContractState.EXECUTING, ContractState.NO_CONTRACT},
    ContractState.ACQUIRE_ORDER: {ContractState.EXECUTING, ContractState.NO_CONTRACT},
    ContractState.EXECUTING: {ContractState.NO_CONTRACT},
}


def transition_contract_state(state: Any, next_state: ContractState, *, reason: str = "") -> None:
    current = getattr(state, "contract_state", ContractState.NO_CONTRACT)
    if not isinstance(current, ContractState):
        try:
            current = ContractState(str(current))
        except Exception:
            current = ContractState.NO_CONTRACT

    if current != next_state and next_state not in _ALLOWED_CONTRACT_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid contract transition: {current.value} -> {next_state.value} ({reason})")
    state.contract_state = next_state


def set_execute_state(state: Any, next_state: ContractExecuteState) -> None:
    state.contract_execute_state = next_state
def apply_resume_or_go_board(
    *,
    state: Any,
    npc: Any,
    order_row: Any | None,
    board_check_action: str,
    display_action_name: Callable[..., str],
    work_duration_for_action: Callable[[str, Any, Any], int],
) -> None:
    if order_row is not None:
        transition_contract_state(state, ContractState.EXECUTING, reason="resume_contract")
        set_execute_state(state, ContractExecuteState.MOVE_TO_WORKSITE)
        action = order_row.action_name
        state.current_action = action
        state.current_action_display = display_action_name(
            action,
            order_row.resource_key,
            issue_type=order_row.issue_type.value,
            item_key=order_row.item_key,
        )
        state.ticks_remaining = work_duration_for_action(action, npc, state)
        state.path = []
        state.work_path_initialized = False
        return

    transition_contract_state(state, ContractState.GO_BOARD, reason="no_contract_go_board")
    set_execute_state(state, ContractExecuteState.IDLE)
    state.current_action = board_check_action
    state.current_action_display = board_check_action
    state.ticks_remaining = work_duration_for_action(board_check_action, npc, state)
    state.path = []
    state.work_path_initialized = False


def apply_assigned_order(
    *,
    state: Any,
    npc: Any,
    assigned: Any | None,
    display_action_name: Callable[..., str],
    work_duration_for_action: Callable[[str, Any, Any], int],
) -> None:
    if assigned is None:
        transition_contract_state(state, ContractState.NO_CONTRACT, reason="no_assignment")
        set_execute_state(state, ContractExecuteState.IDLE)
        state.assigned_order_id = ""
        state.current_action = "배회"
        state.current_action_display = "배회"
        state.ticks_remaining = 1
        state.path = []
        state.work_path_initialized = False
        return

    state.assigned_order_id = assigned.order_id
    transition_contract_state(state, ContractState.EXECUTING, reason="assigned_order")
    set_execute_state(state, ContractExecuteState.MOVE_TO_WORKSITE)
    action = assigned.action_name
    state.current_action = action
    state.current_action_display = display_action_name(
        action,
        assigned.resource_key,
        issue_type=assigned.issue_type.value,
        item_key=assigned.item_key,
    )
    state.ticks_remaining = work_duration_for_action(action, npc, state)
    state.path = []
    state.work_path_initialized = False
