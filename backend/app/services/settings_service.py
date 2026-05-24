import json
import math
from pathlib import Path

from backend.app.models.settings import (
    GoalProjection,
    GoalScenario,
    GoalSettings,
    GoalVerdict,
    ProjectionPoint,
)
from backend.app.services.portfolio_service import get_summary


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
GOAL_SETTINGS_FILE = DATA_DIR / "goal_settings.json"

DEFAULT_GOAL_SETTINGS = GoalSettings(
    target_portfolio_value=10_000_000,
    time_horizon_years=10,
    monthly_sip_amount=25_000,
    dip_cash_reserve=150_000,
    expected_annual_return_percent=12,
    risk_tolerance="moderate",
    return_volatility_percent=18,
)


def _ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not GOAL_SETTINGS_FILE.exists():
        save_goal_settings(DEFAULT_GOAL_SETTINGS)


def get_goal_settings() -> GoalSettings:
    _ensure_storage()
    payload = json.loads(GOAL_SETTINGS_FILE.read_text(encoding="utf-8-sig"))
    if "risk_tolerance" not in payload:
        payload["risk_tolerance"] = DEFAULT_GOAL_SETTINGS.risk_tolerance
    if "return_volatility_percent" not in payload:
        payload["return_volatility_percent"] = DEFAULT_GOAL_SETTINGS.return_volatility_percent
    return GoalSettings(**payload)


def save_goal_settings(settings: GoalSettings) -> GoalSettings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GOAL_SETTINGS_FILE.write_text(
        json.dumps(settings.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return settings


def get_goal_projection() -> GoalProjection:
    settings = get_goal_settings()
    summary = get_summary()
    current_value = summary.current_value
    months = settings.time_horizon_years * 12

    base_return = settings.expected_annual_return_percent
    conservative_return = max(0.0, base_return - 3.0)
    aggressive_return = min(40.0, base_return + 3.0)

    base_projection = _projection_values(current_value, settings.monthly_sip_amount, base_return, months)
    conservative_projection = _projection_values(current_value, settings.monthly_sip_amount, conservative_return, months)
    aggressive_projection = _projection_values(current_value, settings.monthly_sip_amount, aggressive_return, months)

    required_monthly_sip = _required_monthly_sip(
        target=settings.target_portfolio_value,
        future_value_current=base_projection["future_value_current"],
        sip_factor=base_projection["sip_factor"],
    )
    additional_sip = max(required_monthly_sip - settings.monthly_sip_amount, 0)

    suggested_dip_reserve = _suggested_dip_cash_reserve(current_value, settings.monthly_sip_amount)
    reserve_gap = max(suggested_dip_reserve - settings.dip_cash_reserve, 0)
    projected_value = base_projection["projected_value"]
    gap_to_goal = max(settings.target_portfolio_value - projected_value, 0)

    realistic_target = round(settings.target_portfolio_value * 0.9, 2)
    aggressive_target = round(settings.target_portfolio_value * 1.15, 2)
    success_probability = _goal_success_probability(
        target=settings.target_portfolio_value,
        expected_final_value=projected_value,
        annual_volatility=settings.return_volatility_percent,
        years=settings.time_horizon_years,
    )

    scenarios = [
        _build_scenario("conservative", conservative_return, conservative_projection["projected_value"], settings.target_portfolio_value, conservative_projection["future_value_current"], conservative_projection["sip_factor"]),
        _build_scenario("realistic", base_return, projected_value, settings.target_portfolio_value, base_projection["future_value_current"], base_projection["sip_factor"]),
        _build_scenario("aggressive", aggressive_return, aggressive_projection["projected_value"], settings.target_portfolio_value, aggressive_projection["future_value_current"], aggressive_projection["sip_factor"]),
    ]

    points = _build_projection_points(
        current_value=current_value,
        monthly_sip=settings.monthly_sip_amount,
        years=settings.time_horizon_years,
        conservative_return=conservative_return,
        realistic_return=base_return,
        aggressive_return=aggressive_return,
    )

    return GoalProjection(
        target_portfolio_value=round(settings.target_portfolio_value, 2),
        current_portfolio_value=round(current_value, 2),
        time_horizon_years=settings.time_horizon_years,
        months_remaining=months,
        expected_annual_return_percent=round(base_return, 2),
        monthly_sip_amount=round(settings.monthly_sip_amount, 2),
        projected_value=round(projected_value, 2),
        future_value_of_current_portfolio=round(base_projection["future_value_current"], 2),
        future_value_of_sips=round(base_projection["future_value_sips"], 2),
        gap_to_goal=round(gap_to_goal, 2),
        required_monthly_sip=round(required_monthly_sip, 2),
        additional_monthly_sip_required=round(additional_sip, 2),
        dip_cash_reserve=round(settings.dip_cash_reserve, 2),
        suggested_dip_cash_reserve=round(suggested_dip_reserve, 2),
        dip_cash_reserve_gap=round(reserve_gap, 2),
        status=_projection_status(projected_value, settings.target_portfolio_value),
        realistic_target_value=realistic_target,
        aggressive_target_value=aggressive_target,
        success_probability_percent=round(success_probability, 2),
        scenarios=scenarios,
        projection_points=points,
    )


def get_goal_verdict() -> GoalVerdict:
    projection = get_goal_projection()
    summary = get_summary()
    key_findings = [
        f"Projected value is {_money(projection.projected_value)} against target {_money(projection.target_portfolio_value)}.",
        f"Estimated success probability is {projection.success_probability_percent:.1f}% under current assumptions.",
        f"Required monthly SIP is {_money(projection.required_monthly_sip)} (extra {_money(projection.additional_monthly_sip_required)}).",
    ]
    warnings = [
        "Projections are model-based, not guaranteed returns.",
        "Data coverage and broker statement delays can affect current value accuracy.",
    ]
    recommended_actions: list[str] = []

    if projection.status == "on_track":
        headline = "Goal trajectory is healthy."
        verdict = "Current SIP and return assumptions are sufficient. Focus on consistency and downside control."
        recommended_actions.append("Keep SIP discipline and review drawdown risk monthly.")
    elif projection.status == "needs_attention":
        headline = "Goal trajectory is fragile."
        verdict = "You are near target path but with thin margin. Small mistakes or poor markets can derail outcomes."
        recommended_actions.append("Increase SIP or extend horizon slightly to improve probability.")
    else:
        headline = "Goal trajectory is off track."
        verdict = "Current plan is unlikely to hit target. You need higher SIP, more time, or lower target."
        recommended_actions.append(f"Raise SIP toward {_money(projection.required_monthly_sip)} if target and timeline are fixed.")

    if projection.dip_cash_reserve_gap > 0:
        recommended_actions.append(
            f"Build reserve cash by {_money(projection.dip_cash_reserve_gap)} to reach recommended safety buffer."
        )
    if not summary.holdings:
        warnings.append("No holdings loaded; projections use goal assumptions only.")

    return GoalVerdict(
        status=projection.status,
        headline=headline,
        verdict=verdict,
        key_findings=key_findings,
        recommended_actions=recommended_actions,
        warnings=warnings,
        projection=projection,
    )


def _projection_values(current_value: float, monthly_sip: float, annual_return: float, months: int) -> dict[str, float]:
    monthly_return = annual_return / 100 / 12
    growth_factor = (1 + monthly_return) ** months
    future_value_current = current_value * growth_factor
    sip_factor = _future_value_annuity_factor(monthly_return, months)
    future_value_sips = monthly_sip * sip_factor
    return {
        "future_value_current": future_value_current,
        "future_value_sips": future_value_sips,
        "projected_value": future_value_current + future_value_sips,
        "sip_factor": sip_factor,
    }


def _build_scenario(
    name: str,
    annual_return_percent: float,
    projected_value: float,
    target: float,
    future_value_current: float,
    sip_factor: float,
) -> GoalScenario:
    return GoalScenario(
        name=name,
        annual_return_percent=round(annual_return_percent, 2),
        projected_value=round(projected_value, 2),
        required_monthly_sip=round(_required_monthly_sip(target, future_value_current, sip_factor), 2),
        status=_projection_status(projected_value, target),
    )


def _build_projection_points(
    current_value: float,
    monthly_sip: float,
    years: int,
    conservative_return: float,
    realistic_return: float,
    aggressive_return: float,
) -> list[ProjectionPoint]:
    points: list[ProjectionPoint] = []
    for year in range(0, years + 1):
        months = year * 12
        c = _projection_values(current_value, monthly_sip, conservative_return, months)["projected_value"]
        r = _projection_values(current_value, monthly_sip, realistic_return, months)["projected_value"]
        a = _projection_values(current_value, monthly_sip, aggressive_return, months)["projected_value"]
        points.append(
            ProjectionPoint(
                year=year,
                conservative_value=round(c, 2),
                realistic_value=round(r, 2),
                aggressive_value=round(a, 2),
            )
        )
    return points


def _goal_success_probability(target: float, expected_final_value: float, annual_volatility: float, years: int) -> float:
    if expected_final_value <= 0 or target <= 0:
        return 0.0
    sigma_terminal = (annual_volatility / 100) * math.sqrt(max(years, 1))
    if sigma_terminal <= 0:
        return 100.0 if expected_final_value >= target else 0.0
    z = math.log(target / expected_final_value) / sigma_terminal
    return max(0.0, min(100.0, (1 - _norm_cdf(z)) * 100))


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _future_value_annuity_factor(monthly_return: float, months: int) -> float:
    if months <= 0:
        return 0
    if monthly_return == 0:
        return months
    return ((1 + monthly_return) ** months - 1) / monthly_return


def _required_monthly_sip(target: float, future_value_current: float, sip_factor: float) -> float:
    if future_value_current >= target or sip_factor <= 0:
        return 0
    return (target - future_value_current) / sip_factor


def _suggested_dip_cash_reserve(current_value: float, monthly_sip_amount: float) -> float:
    return max(monthly_sip_amount * 6, current_value * 0.05)


def _projection_status(projected_value: float, target: float) -> str:
    if projected_value >= target:
        return "on_track"
    if projected_value >= target * 0.85:
        return "needs_attention"
    return "off_track"


def _money(value: float) -> str:
    return f"Rs. {value:,.0f}"
