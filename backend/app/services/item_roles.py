"""What part each logged item plays in the insight reports."""

from .. import models

ROLES = ("possible_cause", "describes_night", "symptom", "reaction", "habit")
EXCLUDING_ROLES = {"describes_night", "symptom", "reaction", "habit"}
LIFESTYLE_PAGE = "lifestyle_impact"
ACUPUNCTURE_PAGE = "acupuncture_report"

_DEFAULT_BY_CATEGORY = {
    "during sleep": "describes_night",
    "morning / waking feedback": "describes_night",
    "headache issues": "symptom",
}


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def default_role_for_category(category_name: str | None) -> str:
    return _DEFAULT_BY_CATEGORY.get(_norm(category_name), "possible_cause")


def is_before_sleep(category_name: str | None) -> bool:
    return _norm(category_name) == "before sleep"


def effective_role(activity: models.Activity) -> str:
    if activity.report_role:
        return activity.report_role
    category = activity.category
    return default_role_for_category(category.name if category is not None else None)


def is_symptom(activity: models.Activity) -> bool:
    return effective_role(activity) == "symptom"


def role_was_set_by_owner(activity: models.Activity) -> bool:
    return bool(activity.report_role)


def is_hidden_on(activity: models.Activity, page: str) -> bool:
    return page in (activity.hidden_pages or [])
