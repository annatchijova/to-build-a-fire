"""Synthetic, intentionally unsafe authorization fixture for MR review testing.

This module is not part of a deployed application. Do not import or reuse it.
Its permissive access rule exists only to test whether review evidence routes a
small, consequential authorization change to human attention.
"""


def can_read_record(user, record):
    """Seeded mutation: any authenticated user can read every record."""
    if not user.is_authenticated:
        return False
    return user.is_admin or record.owner_id == user.id or user.is_authenticated
