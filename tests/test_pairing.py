from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func

import tasks
from models import Group, GroupsAndUsersAssociation, Pair, User


def make_group(db, size, name="pairing-test", sitting_out=0):
    """A group of `size` participating members, plus `sitting_out` who aren't."""
    group = Group(name=name)
    db.session.add(group)
    members = []
    for i in range(size + sitting_out):
        user = User(username=f"{name}-{i}"[:20], email=f"{name}-{i}@santa.io")
        db.session.add(user)
        db.session.add(
            GroupsAndUsersAssociation(
                group=group, user=user, participating=i < size
            )
        )
        members.append(user)
    db.session.commit()
    return group, members[:size], members[size:]


def save_draw(db, group, edges, timestamp):
    for giver, receiver in edges:
        db.session.add(
            Pair(group=group, giver=giver, receiver=receiver, timestamp=timestamp)
        )
    db.session.commit()


def latest_draw(db, group_id):
    """(giver_id, receiver_id) pairs from the group's most recent draw."""
    # The draw commits through its own session; don't serve stale objects
    db.session.expire_all()
    drawn_at = (
        db.session.query(func.max(Pair.timestamp))
        .filter(Pair.group_id == group_id)
        .scalar()
    )
    return {
        (pair.giver_id, pair.receiver_id)
        for pair in Pair.query.filter_by(group_id=group_id, timestamp=drawn_at)
    }


def draw(group_id):
    result = tasks._make_pairs_graph_based(pipe={"group_id": group_id})
    assert result["final_pairs"], result


def assert_one_gift_loop(edges, member_ids):
    """Everyone gives once and receives once, never to themselves, in a single loop."""
    givers = Counter(giver for giver, _ in edges)
    receivers = Counter(receiver for _, receiver in edges)
    assert set(givers) == set(receivers) == set(member_ids)
    assert set(givers.values()) == set(receivers.values()) == {1}
    assert all(giver != receiver for giver, receiver in edges)

    gives_to = dict(edges)
    start = next(iter(member_ids))
    current, loop_length = gives_to[start], 1
    while current != start:
        current, loop_length = gives_to[current], loop_length + 1
    assert loop_length == len(member_ids)


def test_first_draw_is_one_gift_loop(database):
    group, members, _ = make_group(database, 6)

    draw(group.id)

    assert_one_gift_loop(latest_draw(database, group.id), {m.id for m in members})


def test_no_one_gives_to_the_same_person_as_last_draw(database):
    group, members, _ = make_group(database, 6)
    member_ids = {m.id for m in members}
    # Last year: 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 0
    save_draw(
        database,
        group,
        [(members[i], members[(i + 1) % 6]) for i in range(6)],
        datetime.now() - timedelta(days=365),
    )

    # Each draw becomes the "last draw" for the next one
    previous = latest_draw(database, group.id)
    for _ in range(25):
        draw(group.id)
        current = latest_draw(database, group.id)

        assert_one_gift_loop(current, member_ids)
        assert not current & previous
        previous = current


def test_only_last_draw_is_avoided_and_only_in_its_direction(database):
    group, members, _ = make_group(database, 3)
    a, b, c = members
    # Two draws ago a -> b; last draw a -> c -> b -> a. The only loop that avoids last
    # draw is a -> b -> c -> a: it repeats the older a -> b and reverses all of last draw
    save_draw(
        database, group, [(a, b), (b, c), (c, a)], datetime.now() - timedelta(days=730)
    )
    save_draw(
        database, group, [(a, c), (c, b), (b, a)], datetime.now() - timedelta(days=365)
    )

    draw(group.id)

    assert latest_draw(database, group.id) == {(a.id, b.id), (b.id, c.id), (c.id, a.id)}


def test_members_sitting_out_are_not_drawn(database):
    group, members, sitting_out = make_group(database, 4, sitting_out=2)

    draw(group.id)

    current = latest_draw(database, group.id)
    assert_one_gift_loop(current, {m.id for m in members})
    drawn = {user_id for edge in current for user_id in edge}
    assert not drawn & {m.id for m in sitting_out}


def test_group_of_two_can_only_repeat(database):
    group, (a, b), _ = make_group(database, 2)
    save_draw(database, group, [(a, b), (b, a)], datetime.now() - timedelta(days=365))

    draw(group.id)

    assert latest_draw(database, group.id) == {(a.id, b.id), (b.id, a.id)}


def test_find_gift_cycle_returns_none_when_there_is_no_cycle():
    # 1 -> 2 -> 3 with no way back to 1
    graph = {1: [(2, 0.5)], 2: [(3, 0.5)], 3: [(2, 0.5)]}

    assert tasks._find_gift_cycle(graph, [1, 2, 3]) is None
