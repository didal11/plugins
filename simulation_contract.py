#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from enum import Enum
from typing import Any, Callable


class ContractState(str, Enum):
    BOARD_CHECK = "BOARD_CHECK"
    SELECT_WORK = "SELECT_WORK"
    EXECUTE_WORK = "EXECUTE_WORK"
    REPORT_AND_SUBMIT = "REPORT_AND_SUBMIT"


class ContractExecuteState(str, Enum):
    IDLE = "IDLE"
    GO_TO_BOARD = "GO_TO_BOARD"
    CHOOSE_WORK = "CHOOSE_WORK"
    MOVE_TO_WORKSITE = "MOVE_TO_WORKSITE"
    PERFORM_EXPLORE = "PERFORM_EXPLORE"
    PERFORM_CRAFT = "PERFORM_CRAFT"
    PERFORM_GATHER = "PERFORM_GATHER"
    PERFORM_GENERIC = "PERFORM_GENERIC"
    REPORT_AND_SUBMIT = "REPORT_AND_SUBMIT"


class WorkState(str, Enum):
    NONE = "NONE"
    EXPLORE = "EXPLORE"
    CRAFT = "CRAFT"
    GATHER = "GATHER"
    GENERIC = "GENERIC"


class ActionState(str, Enum):
    MEAL = "MEAL"
    SLEEP = "SLEEP"
    WORK = "WORK"



_ALLOWED_CONTRACT_TRANSITIONS = {
    ContractState.BOARD_CHECK: {ContractState.SELECT_WORK, ContractState.BOARD_CHECK},
    ContractState.SELECT_WORK: {ContractState.EXECUTE_WORK, ContractState.BOARD_CHECK, ContractState.SELECT_WORK},
    ContractState.EXECUTE_WORK: {ContractState.REPORT_AND_SUBMIT, ContractState.EXECUTE_WORK},
    ContractState.REPORT_AND_SUBMIT: {ContractState.BOARD_CHECK, ContractState.REPORT_AND_SUBMIT},
}


def transition_contract_state(state: Any, next_state: ContractState, *, reason: str = "") -> None:
    current = getattr(state, "contract_state", ContractState.BOARD_CHECK)
    if not isinstance(current, ContractState):
        try:
            current = ContractState(str(current))
        except Exception:
            current = ContractState.BOARD_CHECK

    if current != next_state and next_state not in _ALLOWED_CONTRACT_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid contract transition: {current.value} -> {next_state.value} ({reason})")
    state.contract_state = next_state


def set_execute_state(state: Any, next_state: ContractExecuteState) -> None:
    state.contract_execute_state = next_state


def _work_state_for_action(action_name: str) -> WorkState:
    action = str(action_name).strip().lower()
    if action == "탐색":
        return WorkState.EXPLORE
    if any(token in action for token in ["제작", "가공", "연금", "단조", "조리"]):
        return WorkState.CRAFT
    if any(token in action for token in ["채집", "벌목", "채광", "수집"]):
        return WorkState.GATHER
    if action:
        return WorkState.GENERIC
    return WorkState.NONE


def _perform_state_for_work(work_state: WorkState) -> ContractExecuteState:
    if work_state == WorkState.EXPLORE:
        return ContractExecuteState.PERFORM_EXPLORE
    if work_state == WorkState.CRAFT:
        return ContractExecuteState.PERFORM_CRAFT
    if work_state == WorkState.GATHER:
        return ContractExecuteState.PERFORM_GATHER
    return ContractExecuteState.PERFORM_GENERIC


def apply_resume_or_go_board(
    *,
    state: Any,
    npc: Any,
    order_row: Any | None,
    board_check_action: str,
    display_action_name: Callable[..., str],
    work_duration_for_action: Callable[[str, Any, Any], int],
) -> None:
    state.action_state = ActionState.WORK
    if order_row is not None:
        if getattr(state, "contract_state", ContractState.BOARD_CHECK) != ContractState.EXECUTE_WORK:
            transition_contract_state(state, ContractState.SELECT_WORK, reason="resume_contract_select")
            set_execute_state(state, ContractExecuteState.CHOOSE_WORK)
            transition_contract_state(state, ContractState.EXECUTE_WORK, reason="resume_contract_execute")
        set_execute_state(state, ContractExecuteState.MOVE_TO_WORKSITE)
        action = order_row.action_name
        state.work_state = _work_state_for_action(action)
        state.action_detail = action
        state.action_display = display_action_name(
            action,
            order_row.resource_key,
            issue_type=order_row.issue_type.value,
            item_key=order_row.item_key,
        )
        state.ticks_remaining = work_duration_for_action(action, npc, state)
        state.path = []
        state.work_path_initialized = False
        return

    transition_contract_state(state, ContractState.BOARD_CHECK, reason="no_contract_go_board")
    set_execute_state(state, ContractExecuteState.GO_TO_BOARD)
    state.work_state = WorkState.NONE
    state.action_detail = board_check_action
    state.action_display = board_check_action
    state.ticks_remaining = work_duration_for_action(board_check_action, npc, state)
    state.path = []
    state.work_path_initialized = False


def apply_assigned_order(
    *,
    state: Any,
    npc: Any,
    assigned: Any | None,
    board_check_action: str,
    display_action_name: Callable[..., str],
    work_duration_for_action: Callable[[str, Any, Any], int],
) -> None:
    if assigned is None:
        transition_contract_state(state, ContractState.BOARD_CHECK, reason="no_assignment")
        set_execute_state(state, ContractExecuteState.IDLE)
        state.work_state = WorkState.NONE
        state.assigned_order_id = ""
        state.action_state = ActionState.WORK
        state.action_detail = board_check_action
        state.action_display = board_check_action
        state.ticks_remaining = 1
        state.path = []
        state.work_path_initialized = False
        return

    state.assigned_order_id = assigned.order_id
    transition_contract_state(state, ContractState.SELECT_WORK, reason="assigned_order_select")
    set_execute_state(state, ContractExecuteState.CHOOSE_WORK)
    action = assigned.action_name
    state.work_state = _work_state_for_action(action)
    transition_contract_state(state, ContractState.EXECUTE_WORK, reason="assigned_order_execute")
    set_execute_state(state, ContractExecuteState.MOVE_TO_WORKSITE)
    state.action_state = ActionState.WORK
    state.action_detail = action
    state.action_display = display_action_name(
        action,
        assigned.resource_key,
        issue_type=assigned.issue_type.value,
        item_key=assigned.item_key,
    )
    state.ticks_remaining = work_duration_for_action(action, npc, state)
    state.path = []
    state.work_path_initialized = False


def perform_execute_state_for_work(work_state: WorkState) -> ContractExecuteState:
    return _perform_state_for_work(work_state)
