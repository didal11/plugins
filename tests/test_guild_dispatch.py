from __future__ import annotations


def test_issue_for_targets_emits_explore_when_available_is_below_target_available():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="herb", name="약초", x=1, y=1, max_quantity=10, current_quantity=2, is_discovered=True),
    ]

    dispatcher = GuildDispatcher(entities)
    issues = dispatcher.issue_for_targets(
        target_stock_by_key={"herb": 0},
        target_available_by_key={"herb": 5},
    )

    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("herb", "탐색", 3) in got


def test_issue_for_targets_emits_gather_when_stock_is_below_target_stock_and_caps_by_available():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="ore", name="광석", x=1, y=1, max_quantity=10, current_quantity=2, is_discovered=True),
    ]

    dispatcher = GuildDispatcher(entities, stock_by_key={"ore": 0})
    issues = dispatcher.issue_for_targets(
        target_stock_by_key={"ore": 10},
        target_available_by_key={"ore": 0},
    )

    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("ore", "채광", 2) in got


def test_issue_for_targets_explore_and_gather_are_non_exclusive():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="tree", name="나무", x=1, y=1, max_quantity=10, current_quantity=1, is_discovered=False),
    ]

    dispatcher = GuildDispatcher(entities, stock_by_key={"tree": 0})
    issues = dispatcher.issue_for_targets(
        target_stock_by_key={"tree": 3},
        target_available_by_key={"tree": 4},
    )

    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("tree", "탐색", 3) in got
    assert ("tree", "벌목", 1) in got


def test_issue_for_targets_does_not_emit_explore_when_available_meets_target():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="herb", name="약초", x=1, y=1, max_quantity=10, current_quantity=5, is_discovered=True),
    ]

    dispatcher = GuildDispatcher(entities)
    issues = dispatcher.issue_for_targets(
        target_stock_by_key={"herb": 0},
        target_available_by_key={"herb": 5},
    )

    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("herb", "탐색", 1) not in got


def test_dispatcher_uses_only_registered_resources_for_available_and_issues():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="herb", name="약초", x=1, y=1, max_quantity=10, current_quantity=2, is_discovered=True),
        ResourceEntity(key="tree", name="나무", x=2, y=1, max_quantity=10, current_quantity=3, is_discovered=True),
    ]

    dispatcher = GuildDispatcher(
        entities,
        registered_resource_keys=["herb"],
        stock_by_key={"herb": 0, "tree": 0},
    )

    assert dispatcher.resource_keys == ["herb"]
    assert dispatcher.available_by_key == {"herb": 2}
    assert dispatcher.stock_by_key == {"herb": 0}

    issues = dispatcher.issue_for_targets(
        target_stock_by_key={"herb": 3, "tree": 99},
        target_available_by_key={"herb": 4, "tree": 99},
    )
    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("herb", "탐색", 2) in got
    assert ("herb", "약초채집", 2) in got
    assert all(key != "tree" for key, _, _ in got)


def test_dispatcher_with_explicit_empty_registration_emits_no_issues():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="herb", name="약초", x=1, y=1, max_quantity=10, current_quantity=5, is_discovered=True),
    ]
    dispatcher = GuildDispatcher(entities, registered_resource_keys=[], stock_by_key={})

    assert dispatcher.resource_keys == []
    assert dispatcher.available_by_key == {}
    assert dispatcher.stock_by_key == {}
    assert dispatcher.issue_for_targets({"herb": 9}, {"herb": 9}) == []


def test_dispatcher_can_count_available_from_discovered_only_while_keeping_registered_keys():
    from guild_dispatch import GuildDispatcher
    from ldtk_integration import ResourceEntity

    entities = [
        ResourceEntity(key="herb", name="약초", x=1, y=1, max_quantity=10, current_quantity=5, is_discovered=False),
    ]
    dispatcher = GuildDispatcher(
        entities,
        registered_resource_keys=["herb"],
        stock_by_key={"herb": 0},
        count_available_only_discovered=True,
    )

    assert dispatcher.resource_keys == ["herb"]
    assert dispatcher.available_by_key == {"herb": 0}

    issues = dispatcher.issue_for_targets({"herb": 0}, {"herb": 2})
    got = {(row.resource_key, row.action_name, row.amount) for row in issues}
    assert ("herb", "탐색", 2) in got
