from __future__ import annotations


def test_issue_bootstrap_for_all_resources_emits_explore_and_gather_per_resource():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="herb", name="약초", x=1, y=1, max_quantity=10, current_quantity=5, is_discovered=True),
        ResourceEntity(key="tree", name="나무", x=2, y=1, max_quantity=10, current_quantity=2, is_discovered=True),
    ]

    dispatcher = GuildDispatcher(entities)
    issues = dispatcher.issue_bootstrap_for_all_resources()

    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("herb", "탐색", 1) in got
    assert ("herb", "약초채집", 1) in got
    assert ("tree", "탐색", 1) in got
    assert ("tree", "벌목", 1) in got


def test_issue_bootstrap_gather_amount_is_capped_by_available():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="ore", name="광석", x=1, y=1, max_quantity=10, current_quantity=0, is_discovered=True),
    ]
    dispatcher = GuildDispatcher(entities)
    issues = dispatcher.issue_bootstrap_for_all_resources()

    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("ore", "탐색", 1) in got
    assert ("ore", "채광", 1) not in got
