"""Article status transitions.

User actions and system events may only move articles along these edges;
anything else is a bug surfaced as a ConflictError at the service layer.
"""

from forge.domain.content.types import ArticleStatus as S

# action → (allowed source statuses, resulting status)
USER_ACTIONS: dict[str, tuple[frozenset[S], S]] = {
    "save": (frozenset({S.DISCOVERED, S.SUGGESTED, S.DISMISSED}), S.UNREAD),
    "start_reading": (frozenset({S.UNREAD, S.REVIEW_DUE}), S.READING),
    # Reading straight from the suggestion feed implies saving first.
    "mark_read": (frozenset({S.UNREAD, S.READING, S.SUGGESTED, S.DISCOVERED}), S.LEARNED),
    "dismiss": (frozenset({S.DISCOVERED, S.SUGGESTED, S.UNREAD}), S.DISMISSED),
    "archive": (
        frozenset({S.UNREAD, S.READING, S.LEARNED, S.REVIEW_DUE, S.MASTERED}),
        S.ARCHIVED,
    ),
}


class InvalidTransition(Exception):
    def __init__(self, action: str, current: S) -> None:
        self.action = action
        self.current = current
        super().__init__(f"cannot {action} an article in status {current}")


def apply_action(action: str, current: S) -> S:
    allowed, target = USER_ACTIONS[action]
    if current == target:
        return target  # idempotent re-application
    if current not in allowed:
        raise InvalidTransition(action, current)
    return target
