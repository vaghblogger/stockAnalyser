"""Backtest graph: single node that runs backtest via shared core logic."""

from langgraph.graph import END, START, StateGraph

from src.api.routes.backtest import BacktestRequest, run_backtest_core

from src.graph.state import BacktestState, GraphContext


def build_backtest_graph(ctx: GraphContext):
    """Build the compiled backtest graph (single node: run_backtest)."""

    def run_backtest_node(state: BacktestState) -> BacktestState:
        body = BacktestRequest(
            symbol=state.get("symbol"),
            symbols=state.get("symbols"),
            strategy_assignments=state.get("strategy_assignments"),
            start=state["start"],
            end=state["end"],
            lookback_days=state.get("lookback_days"),
            hold_days=state.get("hold_days"),
            step_days=state.get("step_days"),
            strategy_id=state.get("strategy_id"),
            params=state.get("params"),
        )
        try:
            result = run_backtest_core(
                config=ctx.config,
                cache_dir=ctx.cache_dir,
                data_provider=ctx.data_provider,
                sentiment_provider=ctx.sentiment_provider,
                body=body,
            )
            return {
                "metrics": result.get("metrics"),
                "rows": result.get("rows"),
                "strategy": result.get("strategy"),
                "by_symbol": result.get("by_symbol"),
                "run_id": result.get("run_id"),
            }
        except Exception as e:
            return {"error": str(e)}

    graph = StateGraph(BacktestState)
    graph.add_node("run_backtest", run_backtest_node)
    graph.add_edge(START, "run_backtest")
    graph.add_edge("run_backtest", END)

    return graph.compile()
