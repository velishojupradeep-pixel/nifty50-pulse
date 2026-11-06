"""
Chart builders and formatting helpers for NIFTY 50 Option Radar.
Includes customized Plotly visualizations for Points Contribution, Heavyweights Tug-of-War, and RVOL.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def format_inr(val: float) -> str:
    """Format number in Indian Rupees format."""
    return f"₹{val:,.2f}"


def format_volume(vol: int) -> str:
    """Format volume into readable Lakhs / Crores or Millions."""
    if vol >= 10_000_000:
        return f"{vol / 10_000_000:.2f} Cr"
    elif vol >= 100_000:
        return f"{vol / 100_000:.2f} L"
    elif vol >= 1_000:
        return f"{vol / 1_000:.1f} K"
    return str(vol)


def create_point_contribution_chart(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """
    Creates a diverging horizontal bar chart of Top N positive contributors
    vs Top N negative draggers in NIFTY 50 points.
    """
    gainers = df[df["points_contribution"] > 0].sort_values(
        by="points_contribution", ascending=True
    ).tail(top_n)
    
    losers = df[df["points_contribution"] < 0].sort_values(
        by="points_contribution", ascending=True
    ).head(top_n)

    plot_df = pd.concat([losers, gainers])

    colors = [
        "#00C853" if p > 0 else "#FF1744" for p in plot_df["points_contribution"]
    ]

    fig = go.Figure(
        go.Bar(
            y=plot_df["symbol_clean"],
            x=plot_df["points_contribution"].round(2),
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{p:+.1f} pts" for p in plot_df["points_contribution"]],
            textposition="auto",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Points Impact: %{x:+.2f} pts<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"<b>NIFTY 50 Points Impact: Top Pullers vs Draggers</b>",
        xaxis_title="Index Points Contributed",
        yaxis_title="",
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20),
        height=450,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.add_vline(x=0, line_width=1.5, line_dash="dash", line_color="rgba(255,255,255,0.4)")
    return fig


def create_heavyweights_tug_of_war_chart(top5_df: pd.DataFrame) -> go.Figure:
    """
    Visualizes the Top 5 heavyweights and their opposing forces on the index.
    """
    df_sorted = top5_df.sort_values(by="points_contribution", ascending=True)

    fig = go.Figure()

    colors = ["#00E676" if x >= 0 else "#FF5252" for x in df_sorted["points_contribution"]]

    fig.add_trace(
        go.Bar(
            x=df_sorted["points_contribution"],
            y=df_sorted["symbol_clean"],
            orientation="h",
            marker=dict(color=colors),
            text=[
                f"{pts:+.1f} pts ({pct:+.2f}%)"
                for pts, pct in zip(df_sorted["points_contribution"], df_sorted["pChange"])
            ],
            textposition="auto",
            hovertemplate=(
                "<b>%{y}</b> (Weight: %{customdata[0]:.1f}%)<br>"
                "Price Change: %{customdata[1]:+.2f}%<br>"
                "Point Impact: %{x:+.2f} pts<br>"
                "RVOL: %{customdata[2]:.2f}x<br>"
                "<extra></extra>"
            ),
            customdata=list(
                zip(df_sorted["weight"], df_sorted["pChange"], df_sorted["rvol"])
            ),
        )
    )

    fig.update_layout(
        title="<b>Top 5 Heavyweights Tug-of-War (Point Impact)</b>",
        xaxis_title="Points Contribution",
        yaxis_title="",
        template="plotly_dark",
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.add_vline(x=0, line_width=1, line_dash="solid", line_color="gray")
    return fig


def create_sector_contribution_chart(sector_df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart of Sector net points contribution to NIFTY.
    """
    if sector_df.empty:
        return go.Figure()

    df_sorted = sector_df.sort_values(by="net_points_contribution", ascending=True)

    colors = [
        "#00C853" if p >= 0 else "#FF1744" for p in df_sorted["net_points_contribution"]
    ]

    fig = go.Figure(
        go.Bar(
            y=df_sorted["sector"],
            x=df_sorted["net_points_contribution"].round(2),
            orientation="h",
            marker=dict(color=colors),
            text=[f"{p:+.1f} pts" for p in df_sorted["net_points_contribution"]],
            textposition="auto",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Net Points Impact: %{x:+.2f} pts<br>"
                "Sector Weight: %{customdata[0]:.1f}%<br>"
                "Advances: %{customdata[1]} | Declines: %{customdata[2]}<br>"
                "<extra></extra>"
            ),
            customdata=list(
                zip(
                    df_sorted["total_weight"],
                    df_sorted["advances"],
                    df_sorted["declines"],
                )
            ),
        )
    )

    fig.update_layout(
        title="<b>Sector Contribution to NIFTY 50</b>",
        xaxis_title="Net Points Contributed",
        yaxis_title="",
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20),
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    return fig


def create_volume_surge_chart(surge_df: pd.DataFrame) -> go.Figure:
    """
    Bubble / Scatter visualization showing RVOL vs % Price Change.
    """
    if surge_df.empty:
        return go.Figure()

    colors = ["#00E676" if p >= 0 else "#FF5252" for p in surge_df["pChange"]]

    fig = go.Figure(
        go.Scatter(
            x=surge_df["rvol"],
            y=surge_df["pChange"],
            mode="markers+text",
            text=surge_df["symbol_clean"],
            textposition="top center",
            marker=dict(
                size=surge_df["weight"] * 3.5 + 8,
                color=colors,
                line=dict(width=1, color="white"),
                opacity=0.85,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "RVOL: %{x:.2f}x<br>"
                "Price Change: %{y:+.2f}%<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="<b>Volume Surge Radar (RVOL vs % Price Change)</b>",
        xaxis_title="Relative Volume (RVOL = Volume / 20D SMA)",
        yaxis_title="% Price Change",
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20),
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.add_vline(x=1.5, line_width=1, line_dash="dash", line_color="orange")
    fig.add_hline(y=0, line_width=1, line_dash="solid", line_color="gray")
    return fig
