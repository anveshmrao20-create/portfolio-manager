import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.models.assistant import (
    AssistantAskResponse,
    AssistantEvidence,
    DailySummaryPoint,
    DailySummaryResponse,
)
from backend.app.models.research import ResearchSearchRequest
from backend.app.services import fundamental_service, research_service, sip_service, technical_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUMMARY_DIR = PROJECT_ROOT / "data" / "assistant"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)


def ask_portfolio_assistant(question: str, db: Session) -> AssistantAskResponse:
    q = question.strip()
    ql = q.lower()

    if _has_any(ql, ["strongest momentum", "highest momentum", "momentum strong"]):
        return _answer_strongest_momentum(q, db)
    if _has_any(ql, ["fundamentally weak", "weak fundamentally", "weak fundamental"]):
        return _answer_fundamentally_weak(q, db)
    if _has_any(ql, ["overvalued", "expensive", "high valuation"]):
        return _answer_overvalued(q, db)
    if _has_any(ql, ["why is this etf selected", "why etf selected", "etf selected"]):
        return _answer_why_etf(q, db)
    if _has_any(ql, ["why is this stock rated highly", "why stock rated highly", "stock rated highly"]):
        return _answer_why_stock_rated(q, db)
    if _has_any(ql, ["market crashes", "crash 20%", "if market crashes", "down 20%"]):
        return _answer_crash_scenario(q, db)
    if _has_any(ql, ["what changed today", "changed today", "today change"]):
        return _answer_today_changes(q, db)

    return _answer_general(q, db)


def _answer_strongest_momentum(question: str, db: Session) -> AssistantAskResponse:
    tech = technical_service.get_technical_snapshot(db=db, lookback_days=365)
    bullish = [i for i in tech.items if i.momentum_status == "bullish"]
    pool = bullish if bullish else tech.items
    best = sorted(
        pool,
        key=lambda i: (
            1 if i.trend_strength in {"strong_uptrend", "uptrend"} else 0,
            i.rsi_14 if i.rsi_14 is not None else 0,
            i.macd_histogram if i.macd_histogram is not None else -999,
        ),
        reverse=True,
    )[:3]
    if not best:
        return AssistantAskResponse(
            question=question,
            intent="momentum_ranking",
            answer="I could not compute momentum because technical data is unavailable right now.",
            confidence="low",
            evidence=[],
        )

    lines = [
        f"{idx + 1}. {item.symbol} ({item.trend_strength}, RSI {item.rsi_14}, MACD hist {item.macd_histogram})"
        for idx, item in enumerate(best)
    ]
    return AssistantAskResponse(
        question=question,
        intent="momentum_ranking",
        answer="Strongest momentum names right now are:\n" + "\n".join(lines),
        confidence="high",
        evidence=[
            AssistantEvidence(
                source_type="technical_snapshot",
                reference=item.symbol,
                detail=f"trend={item.trend_strength}, momentum={item.momentum_status}, rsi={item.rsi_14}",
            )
            for item in best
        ],
    )


def _answer_fundamentally_weak(question: str, db: Session) -> AssistantAskResponse:
    fund = fundamental_service.get_fundamental_snapshot(db=db)
    weak = [i for i in fund.items if i.grade == "Weak"][:5]
    if not weak:
        return AssistantAskResponse(
            question=question,
            intent="fundamental_weakness",
            answer="No holdings are currently tagged as fundamentally weak in the latest snapshot.",
            confidence="high",
            evidence=[],
        )
    lines = [f"{i.symbol}: score {i.score} | weaknesses: {', '.join(i.weaknesses[:3])}" for i in weak]
    return AssistantAskResponse(
        question=question,
        intent="fundamental_weakness",
        answer="Fundamentally weak holdings in your latest data:\n" + "\n".join(lines),
        confidence="high",
        evidence=[
            AssistantEvidence(
                source_type="fundamental_snapshot",
                reference=i.symbol,
                detail=f"score={i.score}, confidence={i.confidence_percent}",
            )
            for i in weak
        ],
    )


def _answer_overvalued(question: str, db: Session) -> AssistantAskResponse:
    fund = fundamental_service.get_fundamental_snapshot(db=db)
    expensive = [
        i for i in fund.items if (i.metrics.trailing_pe and i.metrics.trailing_pe > 45) or (i.metrics.peg_ratio and i.metrics.peg_ratio > 2.5)
    ]
    ranked = sorted(
        expensive,
        key=lambda i: (
            i.metrics.trailing_pe if i.metrics.trailing_pe is not None else 0,
            i.metrics.peg_ratio if i.metrics.peg_ratio is not None else 0,
        ),
        reverse=True,
    )[:5]
    if not ranked:
        return AssistantAskResponse(
            question=question,
            intent="valuation_check",
            answer="I do not see strong overvaluation flags from trailing PE/PEG in the latest fundamentals snapshot.",
            confidence="medium",
            evidence=[],
        )
    lines = [
        f"{i.symbol}: PE {i.metrics.trailing_pe}, PEG {i.metrics.peg_ratio}, grade {i.grade}"
        for i in ranked
    ]
    return AssistantAskResponse(
        question=question,
        intent="valuation_check",
        answer="Most expensive names by valuation flags:\n" + "\n".join(lines),
        confidence="medium",
        evidence=[
            AssistantEvidence(
                source_type="fundamental_snapshot",
                reference=i.symbol,
                detail=f"trailing_pe={i.metrics.trailing_pe}, peg={i.metrics.peg_ratio}",
            )
            for i in ranked
        ],
    )


def _answer_why_etf(question: str, db: Session) -> AssistantAskResponse:
    sip = sip_service.get_sip_dip_snapshot(db=db)
    if not sip.etf_weekly_picks:
        return AssistantAskResponse(
            question=question,
            intent="etf_selection_rationale",
            answer="There are no ETF picks in the current recommendation snapshot.",
            confidence="medium",
            evidence=[],
        )
    top = sip.etf_weekly_picks[0]
    return AssistantAskResponse(
        question=question,
        intent="etf_selection_rationale",
        answer=(
            f"{top.symbol} is selected because it ranks highest in combined fundamental + technical score "
            f"({top.combined_score}) in the weekly ETF engine. Suggested allocation is Rs. {top.suggested_amount:,.0f}."
        ),
        confidence="high",
        evidence=[
            AssistantEvidence(
                source_type="sip_engine",
                reference=top.symbol,
                detail=top.reason,
            )
        ],
    )


def _answer_why_stock_rated(question: str, db: Session) -> AssistantAskResponse:
    sip = sip_service.get_sip_dip_snapshot(db=db)
    if not sip.stock_monthly_picks:
        return AssistantAskResponse(
            question=question,
            intent="stock_rating_rationale",
            answer="There are no stock SIP picks available right now to explain.",
            confidence="medium",
            evidence=[],
        )
    top = sip.stock_monthly_picks[0]
    return AssistantAskResponse(
        question=question,
        intent="stock_rating_rationale",
        answer=(
            f"{top.symbol} is currently rated highly by the allocation engine because its combined score is {top.combined_score}. "
            f"Current rationale: {top.reason}."
        ),
        confidence="high",
        evidence=[
            AssistantEvidence(source_type="sip_engine", reference=top.symbol, detail=top.reason)
        ],
    )


def _answer_crash_scenario(question: str, db: Session) -> AssistantAskResponse:
    sip = sip_service.get_sip_dip_snapshot(db=db)
    reserve = sip.reserve_cash_plan
    top_dips = sip.dip_opportunities[:3]
    if not top_dips:
        suggestion = "No dip opportunities are currently open, so focus on raising reserve cash first."
    else:
        suggestion = "Top crash-watch names: " + ", ".join(f"{d.symbol} ({d.conviction})" for d in top_dips)
    answer = (
        f"If the market drops 20%, your reserve cash ratio is {reserve.reserve_ratio_percent:.2f}% "
        f"vs target {reserve.recommended_ratio_percent:.2f}%. Reserve gap is Rs. {reserve.reserve_gap_value:,.0f}. "
        f"{suggestion}"
    )
    confidence = "high" if reserve.reserve_ratio_percent >= reserve.recommended_ratio_percent else "medium"
    evidence = [
        AssistantEvidence(
            source_type="reserve_plan",
            reference="reserve_cash",
            detail=f"current={reserve.current_reserve_value}, target={reserve.target_reserve_value}",
        )
    ]
    evidence.extend(
        AssistantEvidence(
            source_type="dip_engine",
            reference=d.symbol,
            detail=f"dip={d.dip_percent}, conviction={d.conviction}, action={d.suggested_action}",
        )
        for d in top_dips
    )
    return AssistantAskResponse(
        question=question,
        intent="crash_scenario",
        answer=answer,
        confidence=confidence,
        evidence=evidence,
    )


def _answer_today_changes(question: str, db: Session) -> AssistantAskResponse:
    docs = research_service.list_research_documents(db, limit=8)
    if not docs:
        return AssistantAskResponse(
            question=question,
            intent="daily_changes",
            answer="No recent research documents are indexed yet.",
            confidence="low",
            evidence=[],
        )
    lines = [f"{d.file_name} ({d.channel_name})" for d in docs[:5]]
    return AssistantAskResponse(
        question=question,
        intent="daily_changes",
        answer="Most recent research updates in your knowledge base:\n" + "\n".join(lines),
        confidence="medium",
        evidence=[
            AssistantEvidence(
                source_type="research_docs",
                reference=str(d.document_id),
                detail=f"{d.file_name} | symbols={','.join(d.symbols[:3]) if d.symbols else 'none'}",
            )
            for d in docs[:5]
        ],
    )


def _answer_general(question: str, db: Session) -> AssistantAskResponse:
    hits = research_service.search_research(ResearchSearchRequest(query=question, limit=5), db)
    if hits.total_hits == 0:
        return AssistantAskResponse(
            question=question,
            intent="general",
            answer=(
                "I could not find a direct grounded answer yet. Try asking with a stock symbol or one of: "
                "momentum, fundamentals, overvalued, crash scenario, ETF selection, or today changes."
            ),
            confidence="low",
            evidence=[],
        )

    top = hits.hits[:3]
    lines = [f"{h.file_name}: {h.snippet}" for h in top]
    return AssistantAskResponse(
        question=question,
        intent="general_research_search",
        answer="Best grounded matches from your research base:\n" + "\n".join(lines),
        confidence="medium",
        evidence=[
            AssistantEvidence(
                source_type="research_search",
                reference=str(h.document_id),
                detail=f"score={h.score}, symbols={','.join(h.symbols) if h.symbols else 'none'}",
            )
            for h in top
        ],
    )


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def generate_daily_summary(db: Session) -> DailySummaryResponse:
    now = datetime.now()
    summary_date = now.strftime("%Y-%m-%d")
    tech = technical_service.get_technical_snapshot(db=db, lookback_days=365)
    fund = fundamental_service.get_fundamental_snapshot(db=db)
    sip = sip_service.get_sip_dip_snapshot(db=db)
    recent_docs = research_service.list_research_documents(db, limit=5)

    top_momentum = next((i for i in tech.items if i.momentum_status == "bullish"), None)
    weakest = next((i for i in reversed(sorted(fund.items, key=lambda x: x.score)) if i.grade == "Weak"), None)

    points = [
        DailySummaryPoint(
            title="Reserve Cash",
            detail=(
                f"Reserve ratio is {sip.reserve_cash_plan.reserve_ratio_percent:.2f}% vs "
                f"target {sip.reserve_cash_plan.recommended_ratio_percent:.2f}%."
            ),
        ),
        DailySummaryPoint(
            title="Top SIP Stock",
            detail=(
                f"{sip.stock_monthly_picks[0].symbol} leads with score {sip.stock_monthly_picks[0].combined_score}."
                if sip.stock_monthly_picks
                else "No stock SIP picks generated."
            ),
        ),
        DailySummaryPoint(
            title="Top ETF Pick",
            detail=(
                f"{sip.etf_weekly_picks[0].symbol} leads with score {sip.etf_weekly_picks[0].combined_score}."
                if sip.etf_weekly_picks
                else "No ETF picks generated."
            ),
        ),
        DailySummaryPoint(
            title="Momentum Watch",
            detail=(
                f"{top_momentum.symbol} has strongest bullish momentum."
                if top_momentum
                else "No bullish momentum signal found."
            ),
        ),
        DailySummaryPoint(
            title="Fundamental Risk",
            detail=(
                f"{weakest.symbol} is currently weakest by fundamentals with score {weakest.score}."
                if weakest
                else "No weak fundamental holding in latest snapshot."
            ),
        ),
        DailySummaryPoint(
            title="Research Feed",
            detail=(
                f"Latest research: {recent_docs[0].file_name}."
                if recent_docs
                else "No research documents indexed yet."
            ),
        ),
    ]

    headline = "Portfolio is progressing, but reserve cash remains the key constraint."
    response = DailySummaryResponse(
        generated_at=now,
        summary_date=summary_date,
        headline=headline,
        points=points,
    )
    _write_daily_summary(response)
    return response


def get_latest_daily_summary(db: Session) -> DailySummaryResponse:
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = SUMMARY_DIR / f"daily_summary_{today}.json"
    if file_path.exists():
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return DailySummaryResponse(**payload)
    return generate_daily_summary(db)


def _write_daily_summary(summary: DailySummaryResponse) -> None:
    file_path = SUMMARY_DIR / f"daily_summary_{summary.summary_date}.json"
    file_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
