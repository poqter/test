"""Position-based exclusions for the unregistered member summary only."""
SENIOR_POSITIONS = ('branch_manager', 'division_head', 'chief_representative')


def unregistered_exclusions(auth, member_ids):
    # The caller passes only members already authorized by sales_members.
    ids = sorted(set(member_ids))
    excluded = set()
    for start in range(0, len(ids), 100):
        rows = auth._request('GET', '/rest/v1/profiles', admin=True, params={
            'id': 'in.(' + ','.join(ids[start:start+100]) + ')',
            'position_code': 'in.(' + ','.join(SENIOR_POSITIONS) + ')',
            'select': 'id',
        })
        excluded.update(row['id'] for row in rows)
    return excluded


def summary_groups(states, labels, excluded):
    groups = {}
    for uid, state in states.items():
        if state == '미등록' and uid in excluded:
            continue
        groups.setdefault(state, []).append(labels[uid])
    return groups
