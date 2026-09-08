INVESTIGATOR = "INVESTIGATOR"
SUPERVISOR = "SUPERVISOR"
ADMIN = "ADMIN"

# Maps a required role to the set of roles allowed to satisfy it.
# ADMIN satisfies every check; SUPERVISOR satisfies INVESTIGATOR and
# SUPERVISOR checks; INVESTIGATOR only satisfies INVESTIGATOR checks.
ROLE_HIERARCHY = {
    INVESTIGATOR: {INVESTIGATOR, SUPERVISOR, ADMIN},
    SUPERVISOR: {SUPERVISOR, ADMIN},
    ADMIN: {ADMIN},
}
