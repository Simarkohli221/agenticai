import uuid

from sqlalchemy.orm import Session

from app.agent.graph import investigation_graph
from app.models.user import User
from app.tools.audit_tool import create_audit_log
from app.tools.case_tool import set_case_thread_id


def run_investigation(db: Session, user_request: str, actor: User) -> dict:
    """
    Invoke the existing LangGraph investigation workflow for one
    natural-language request, using a fresh per-request thread ID.

    The authenticated actor is not passed into the graph/LLM - it is
    only used here, after the graph returns, to record who initiated
    the investigation in the existing audit trail.
    """
    thread_id = f"investigation-{uuid.uuid4()}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = investigation_graph.invoke(
        {"user_request": user_request},
        config=config,
    )

    case_id = result.get("case_id")

    if case_id is not None:
        # Persist the exact thread ID used above onto the case the
        # graph just created, and record the actor who requested it,
        # as a single atomic local transaction. Both operations run
        # entirely after investigation_graph.invoke() has already
        # returned, so no LLM call or LangGraph interrupt is ever in
        # progress while this transaction is open.
        try:
            set_case_thread_id(db, case_id, thread_id, commit=False)

            create_audit_log(
                db=db,
                case_id=case_id,
                event_type="INVESTIGATION_REQUESTED",
                details=(
                    f"Investigation requested via API by "
                    f"user_id={actor.user_id}, username={actor.username}, "
                    f"role={actor.role}."
                ),
                commit=False,
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

    return result
