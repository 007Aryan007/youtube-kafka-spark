import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from analytics.business_analysis import (
    prepare_dashboard_df,
    build_category_summary,
    build_top_videos,
    build_recommendations,
    build_channel_leaderboard,
    build_engagement_vs_views_correlation,
    build_view_count_forecast_v2,
)

DELTA_PATH = "storage/delta_tables/youtube_enriched"

def build_reach_trend(dataframe):
    """Build a normalized reach trend from the complete available dataset."""
    if dataframe.empty or "collected_at" not in dataframe.columns:
        return pd.DataFrame()

    columns = ["collected_at", "view_count"]
    if "video_id" in dataframe.columns:
        columns.append("video_id")

    work = dataframe[columns].copy()
    work["collected_at"] = pd.to_datetime(
        work["collected_at"], errors="coerce", utc=True
    )
    work["view_count"] = pd.to_numeric(work["view_count"], errors="coerce")
    work = work.dropna(subset=["collected_at", "view_count"])

    if work.empty:
        return pd.DataFrame()

    # Use all records, but aggregate them into readable 6-hour periods.
    # This prevents thousands of individual collection points from creating
    # a noisy chart.
    work["time_bucket"] = work["collected_at"].dt.floor("6h")

    if "video_id" in work.columns:
        trend = (
            work.groupby("time_bucket", as_index=False)
            .agg(
                average_views=("view_count", "mean"),
                videos_observed=("video_id", "nunique"),
            )
        )
    else:
        trend = (
            work.groupby("time_bucket", as_index=False)
            .agg(
                average_views=("view_count", "mean"),
                videos_observed=("view_count", "count"),
            )
        )

    trend = trend.sort_values("time_bucket")
    trend["smoothed_average_views"] = (
        trend["average_views"].rolling(window=3, min_periods=1).mean()
    )
    return trend

st.set_page_config(page_title="YouTube Business Analytics", layout="wide")
st.title("YouTube Business Analytics Dashboard")
st.caption("A focused view of reach, engagement, content performance, and actionable insights")

@st.cache_data(ttl=300, show_spinner="Loading dashboard data...")
def load_data():
    try:
        import pyarrow.dataset as ds

        dataset = ds.dataset(DELTA_PATH, format="parquet")

        # The Delta table stores collected_at as a string.
        # Read the 7-day table first, then convert it to UTC timestamps.
        table = dataset.to_table()
        df = table.to_pandas()

        if "collected_at" in df.columns:
            df["collected_at"] = pd.to_datetime(
                df["collected_at"],
                errors="coerce",
                utc=True,
            )

            cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=48)
            df = df[df["collected_at"] >= cutoff]

        return df.reset_index(drop=True)

    except Exception as exc:
        st.error(f"Could not load dashboard data: {exc}")
        return pd.DataFrame()

raw_df = load_data()
df = prepare_dashboard_df(raw_df)

if df.empty:
    st.warning("No data available. Run the producer and Spark streaming first.")
    st.stop()

# Filters are applied once, before any analytics are calculated.
st.sidebar.header("Filters")
category_options = ["All"] + sorted(df["category_name"].dropna().astype(str).unique().tolist())
region_options = ["All"] + sorted(df["trending_region"].dropna().astype(str).unique().tolist())

selected_category = st.sidebar.selectbox("Category", category_options)
selected_region = st.sidebar.selectbox("Region", region_options)

if selected_category != "All":
    df = df[df["category_name"] == selected_category]

if selected_region != "All":
    df = df[df["trending_region"] == selected_region]

if df.empty:
    st.warning("No data matched the selected filters.")
    st.stop()

# Calculate only the lightweight analytics needed by the visible section.
# Expensive forecasting is deliberately not run on every filter change.


latest_records = (
    df.sort_values("collected_at")
    .drop_duplicates(subset=["video_id", "trending_region"], keep="last")
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Unique Videos", f"{latest_records['video_id'].nunique():,}")
k2.metric("Total Views", f"{int(latest_records['view_count'].sum()):,}")

avg_eng = pd.to_numeric(latest_records["engagement_rate"], errors="coerce")
avg_eng = avg_eng.replace([float("inf"), -float("inf")], pd.NA).dropna()
avg_eng_value = 0 if avg_eng.empty else avg_eng.mean()
k3.metric("Avg Engagement Rate", f"{avg_eng_value * 100:.2f}%")
k4.metric("Tracked Categories", f"{latest_records['category_name'].nunique():,}")


section = st.radio(
    "Dashboard section",
    ["Performance", "Insights", "Forecast"],
    horizontal=True,
)



if section == "Performance":
    st.subheader("Category Performance")

    summary_df = build_category_summary(df)

    if summary_df.empty:
        st.info("No category summary available.")
    else:
        category_chart = (
            alt.Chart(summary_df)
            .mark_bar()
            .encode(
                x=alt.X("total_views:Q", title="Total Views"),
                y=alt.Y("category_name:N", sort="-x", title="Category"),
                tooltip=[
                    alt.Tooltip("category_name:N", title="Category"),
                    alt.Tooltip("videos:Q", title="Videos"),
                    alt.Tooltip("total_views:Q", title="Total Views", format=","),
                    alt.Tooltip("total_likes:Q", title="Likes", format=","),
                    alt.Tooltip("total_comments:Q", title="Comments", format=","),
                    alt.Tooltip("avg_engagement_rate:Q", title="Avg Engagement", format=".2%"),
                ],
            )
            .properties(height=350)
        )
        st.altair_chart(category_chart, width="stretch")

    reach_trend_df = build_reach_trend(df)

    st.subheader("Average Views per Trending Video")
    st.caption(
        "How the typical video's reach changes over time. "
        "The smoothed line reduces short-term noise while using all available data."
    )

    if reach_trend_df.empty:
        st.info("Not enough timestamped data yet for trend analysis.")
    else:
        base = alt.Chart(reach_trend_df).encode(
            x=alt.X("time_bucket:T", title="Time"),
            y=alt.Y("smoothed_average_views:Q", title="Average Views per Video"),
            tooltip=[
                alt.Tooltip("time_bucket:T", title="Time"),
                alt.Tooltip(
                    "average_views:Q",
                    title="Average Views",
                    format=",",
                ),
                alt.Tooltip(
                    "smoothed_average_views:Q",
                    title="Smoothed Average",
                    format=",",
                ),
                alt.Tooltip(
                    "videos_observed:Q",
                    title="Videos Observed",
                    format=",",
                ),
            ],
        )

        reach_line = (
            base.mark_line(point=True)
            .properties(height=350)
        )

        st.altair_chart(reach_line, width="stretch")

    top_videos_df = build_top_videos(df)

    st.subheader("Top Trending Videos by Reach")
    st.caption(
        "Videos with the highest views in the latest available collection, "
        "with engagement metrics for context."
    )

    if top_videos_df.empty:
        st.info("No video leaderboard data available.")
    else:
        # The source trending_rank is category-specific. It should not be used
        # as a global dashboard rank because every category can have Rank 1.
        # Rank the latest collection by actual view count instead.
        video_work = top_videos_df.copy()

        for column in ["view_count", "like_count", "comment_count"]:
            if column in video_work.columns:
                video_work[column] = pd.to_numeric(
                    video_work[column], errors="coerce"
                ).fillna(0)

        # build_top_videos already represents the latest leaderboard rows.
        # Sort globally by audience reach so categories are compared fairly.
        if "view_count" in video_work.columns:
            video_work = video_work.sort_values(
                "view_count", ascending=False
            ).head(10)

        video_display = video_work.rename(
            columns={
                "title": "Video",
                "channel_title": "Channel",
                "category_name": "Category",
                "view_count": "Views",
                "like_count": "Likes",
                "comment_count": "Comments",
                "like_rate": "Like Rate",
                "comment_rate": "Comment Rate",
            }
        ).copy()

        video_display.insert(0, "Reach Rank", range(1, len(video_display) + 1))

        preferred_columns = [
            "Reach Rank",
            "Video",
            "Channel",
            "Category",
            "Views",
            "Likes",
            "Comments",
            "Like Rate",
            "Comment Rate",
        ]
        display_columns = [
            column for column in preferred_columns if column in video_display.columns
        ]
        video_display = video_display[display_columns]

        if "Video" in video_display.columns:
            video_display["Video"] = (
                video_display["Video"]
                .astype(str)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
                .str.slice(0, 90)
            )

        for column in ["Views", "Likes", "Comments"]:
            if column in video_display.columns:
                video_display[column] = video_display[column].astype("int64")

        for column in ["Like Rate", "Comment Rate"]:
            if column in video_display.columns:
                video_display[column] = (
                    pd.to_numeric(video_display[column], errors="coerce") * 100
                )

        st.dataframe(
            video_display,
            width="stretch",
            hide_index=True,
            column_config={
                "Reach Rank": st.column_config.NumberColumn(
                    "Rank", format="%d"
                ),
                "Video": st.column_config.TextColumn(
                    "Video", width="large"
                ),
                "Channel": st.column_config.TextColumn(
                    "Channel", width="medium"
                ),
                "Category": st.column_config.TextColumn(
                    "Category", width="small"
                ),
                "Views": st.column_config.NumberColumn(
                    "Views", format="%,d"
                ),
                "Likes": st.column_config.NumberColumn(
                    "Likes", format="%,d"
                ),
                "Comments": st.column_config.NumberColumn(
                    "Comments", format="%,d"
                ),
                "Like Rate": st.column_config.NumberColumn(
                    "Like Rate", format="%.2f%%"
                ),
                "Comment Rate": st.column_config.NumberColumn(
                    "Comment Rate", format="%.2f%%"
                ),
            },
        )

    channel_board_df = build_channel_leaderboard(df)

    st.subheader("Top Channels")

    if channel_board_df.empty:
        st.info("Channel leaderboard needs channel-level data.")
    else:
        channel_chart = (
            alt.Chart(channel_board_df.head(15))
            .mark_bar()
            .encode(
                x=alt.X("total_views:Q", title="Total Views"),
                y=alt.Y("channel_title:N", sort="-x", title="Channel"),
                tooltip=[
                    alt.Tooltip("channel_title:N", title="Channel"),
                    alt.Tooltip("videos:Q", title="Videos"),
                    alt.Tooltip("total_views:Q", title="Total Views", format=","),
                    alt.Tooltip("total_engagements:Q", title="Engagements", format=","),
                    alt.Tooltip("avg_engagement_rate:Q", title="Avg Engagement", format=".2%"),
                ],
            )
            .properties(height=450)
        )
        st.altair_chart(channel_chart, width="stretch")


if section == "Insights":
    st.subheader("Engagement vs Views")
    st.caption("Does higher reach correspond to stronger audience engagement?")

    corr_df, corr_scatter_df = build_engagement_vs_views_correlation(df)

    if not corr_scatter_df.empty and len(corr_scatter_df) > 1500:
        corr_scatter_df = corr_scatter_df.sample(1500, random_state=42)

    if corr_scatter_df.empty:
        st.info("No correlation data available.")
    else:
        corr_chart = (
            alt.Chart(corr_scatter_df)
            .mark_circle(opacity=0.65)
            .encode(
                x=alt.X("view_count:Q", title="View Count"),
                y=alt.Y("engagement_rate:Q", title="Engagement Rate"),
                tooltip=[
                    alt.Tooltip("title:N", title="Video"),
                    alt.Tooltip("category_name:N", title="Category"),
                    alt.Tooltip("view_count:Q", title="Views", format=","),
                    alt.Tooltip("engagement_rate:Q", title="Engagement", format=".2%"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(corr_chart, width="stretch")

    if not corr_df.empty:
        st.subheader("Correlation Summary")
        st.dataframe(corr_df, width="stretch")

    st.subheader("Business Insights")
    recommendations_df = build_recommendations(df)

    if recommendations_df.empty:
        st.info("Recommendations need more data.")
    else:
        st.dataframe(recommendations_df, width="stretch")


if section == "Forecast":
    st.subheader("View Forecast")
    st.caption("Forecasts are estimates based on recent observations, not guaranteed future views.")

    if not st.button("Generate forecast"):
        st.info("Forecasting is kept behind a button so normal filter changes stay fast.")
    else:
        with st.spinner("Generating forecast..."):
            video_forecast_df = build_view_count_forecast_v2(df)

        if video_forecast_df.empty:
            st.info("Forecasting needs more observations for currently trending videos.")
        else:
            ranking = (
                video_forecast_df.sort_values("time_bucket")
                .groupby("title", as_index=False)
                .tail(1)
                .sort_values("forecast_views", ascending=False)
                .head(10)["title"]
                .tolist()
            )
            video_forecast_df = video_forecast_df[
                video_forecast_df["title"].isin(ranking)
            ]

            actual = video_forecast_df[video_forecast_df["series"] == "Actual"]
            forecast_df = video_forecast_df[video_forecast_df["series"] == "Forecast"]

            charts = []
            if not actual.empty:
                charts.append(
                    alt.Chart(actual)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("time_bucket:T", title="Time"),
                        y=alt.Y("forecast_views:Q", title="View Count"),
                        color=alt.Color("title:N", title="Video"),
                        tooltip=[
                            alt.Tooltip("title:N", title="Video"),
                            alt.Tooltip("time_bucket:T", title="Time"),
                            alt.Tooltip("forecast_views:Q", title="Views", format=","),
                        ],
                    )
                )

            if not forecast_df.empty:
                charts.append(
                    alt.Chart(forecast_df)
                    .mark_line(point=True, strokeDash=[6, 4])
                    .encode(
                        x=alt.X("time_bucket:T", title="Time"),
                        y=alt.Y("forecast_views:Q", title="Forecast Views"),
                        color=alt.Color("title:N", legend=None),
                        tooltip=[
                            alt.Tooltip("title:N", title="Video"),
                            alt.Tooltip("time_bucket:T", title="Time"),
                            alt.Tooltip("forecast_views:Q", title="Forecast Views", format=","),
                            alt.Tooltip("lower_bound:Q", title="Lower Bound", format=","),
                            alt.Tooltip("upper_bound:Q", title="Upper Bound", format=","),
                        ],
                    )
                )

            if charts:
                combined = charts[0]
                for chart in charts[1:]:
                    combined = combined + chart
                st.altair_chart(combined.properties(height=450), width="stretch")

    st.subheader("Actionable Recommendations")
    recommendations_df = build_recommendations(df)

    if recommendations_df.empty:
        st.info("Recommendations need more data.")
    else:
        st.dataframe(recommendations_df, width="stretch")

with st.expander("Recent dashboard data"):
    st.caption("Showing all available dashboard data from the Delta table; Spark/Delta retains the full history.")
    st.dataframe(df.head(2000), width="stretch")

if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()
