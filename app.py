# MLB HITTING ANALYTICS

import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st

from pybaseball import (
    statcast_batter,
    playerid_lookup
)


# PAGE CONFIGURATION

st.set_page_config(
    page_title="MLB Hitting Analytics",
    page_icon="⚾",
    layout="wide"
)

st.title("MLB Hitting Analysis Database")

st.caption(
    " Portfolio Project Fall 2026 - Paul Schaefer"
)

st.markdown(
    "[⚾ View MLB Pitching Analytics Project]"
    "(https://mlb-pitching-analytics.streamlit.app/)"
)
st.divider()


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

DATA_DIR = "data"

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

DB_PATH = os.path.join(
    DATA_DIR,
    "hitting_statcast.sqlite"
)

REFRESH_OVERLAP_DAYS = 3


# ==========================================
# DATABASE COLUMNS
# ==========================================

DATABASE_COLUMNS = [
    "batter_id",
    "game_pk",
    "game_date",
    "at_bat_number",
    "pitch_number",
    "pitch_type",
    "pitch_name",
    "release_speed",
    "plate_x",
    "plate_z",
    "balls",
    "strikes",
    "description",
    "events",
    "inning",
    "inning_topbot",
    "pitcher",
    "stand",
    "p_throws",
    "home_team",
    "away_team",
    "launch_speed",
    "launch_angle",
    "bb_type",
    "hc_x",
    "hc_y",
    "estimated_woba_using_speedangle",
    "estimated_ba_using_speedangle",
    "woba_value",
    "woba_denom",
    "babip_value",
    "launch_speed_angle",
    "zone",
    "type"
]


# ==========================================
# INITIALIZE DATABASE
# ==========================================

def initialize_database():

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS batter_data (
            batter_id INTEGER,
            game_pk INTEGER,
            game_date TEXT,
            at_bat_number INTEGER,
            pitch_number INTEGER,
            pitch_type TEXT,
            pitch_name TEXT,
            release_speed REAL,
            plate_x REAL,
            plate_z REAL,
            balls INTEGER,
            strikes INTEGER,
            description TEXT,
            events TEXT,
            inning INTEGER,
            inning_topbot TEXT,
            pitcher INTEGER,
            stand TEXT,
            p_throws TEXT,
            home_team TEXT,
            away_team TEXT,
            launch_speed REAL,
            launch_angle REAL,
            bb_type TEXT,
            hc_x REAL,
            hc_y REAL,
            estimated_woba_using_speedangle REAL,
            estimated_ba_using_speedangle REAL,
            woba_value REAL,
            woba_denom REAL,
            babip_value REAL,
            launch_speed_angle INTEGER,
            zone INTEGER,
            type TEXT
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


# ==========================================
# PLAYER LOOKUP
# ==========================================

@st.cache_data(show_spinner=False)
def lookup_statcast_id(
    first_name,
    last_name
):

    lookup = playerid_lookup(
        last_name,
        first_name
    )

    if lookup.empty:

        raise ValueError(
            f"No MLB player found for "
            f"{first_name} {last_name}."
        )

    if "mlb_played_last" in lookup.columns:

        lookup = lookup.sort_values(
            "mlb_played_last",
            ascending=False
        )

    return int(
        lookup.iloc[0]["key_mlbam"]
    )

# SQLite


def get_latest_database_date(player_id, season):

    conn = sqlite3.connect(DB_PATH)

    result = conn.execute(
        """
        SELECT MAX(game_date)
        FROM batter_data
        WHERE batter_id = ?
        AND game_date BETWEEN ? AND ?
        """,
        (
            player_id,
            f"{season}-01-01",
            f"{season}-12-31"
        )
    ).fetchone()[0]

    conn.close()

    return result


def save_statcast_data(df, player_id, start_date, end_date):

    if df.empty:
        return

    df = df.copy()

    df["batter_id"] = player_id

    df["game_date"] = pd.to_datetime(
        df["game_date"]
    ).dt.strftime("%Y-%m-%d")

    available_columns = [
        column
        for column in DATABASE_COLUMNS
        if column in df.columns
    ]

    save_df = df[available_columns].copy()

    conn = sqlite3.connect(DB_PATH)

    # Replace previously cached data for the
    # requested date range to avoid duplicates.

    conn.execute(
        """
        DELETE FROM batter_data
        WHERE batter_id = ?
        AND game_date BETWEEN ? AND ?
        """,
        (
            player_id,
            start_date,
            end_date
        )
    )

    save_df.to_sql(
        "batter_data",
        conn,
        if_exists="append",
        index=False
    )

    conn.commit()
    conn.close()


# STATCAST UPDATE


# ==========================================
# STATCAST UPDATE
# ==========================================

def update_batter_database(
    player_id,
    season,
    force_refresh=False
):

    season_start = f"{season}-03-01"

    current_year = datetime.now().year

    if season < current_year:

        end_date = f"{season}-11-15"

    else:

        end_date = datetime.now().strftime("%Y-%m-%d")

    latest_date = get_latest_database_date(
        player_id,
        season
    )

    if force_refresh or latest_date is None:

        update_start = season_start

    else:

        latest_date = pd.to_datetime(latest_date)

        update_start = (
            latest_date
            - timedelta(days=REFRESH_OVERLAP_DAYS)
        ).strftime("%Y-%m-%d")

        # Do not request dates before the
        # beginning of the selected season.
        update_start = max(update_start, season_start)

    # Prevent invalid date ranges.
    if update_start > end_date:
        return 0

    with st.spinner(
        "Checking Baseball Savant for hitting Statcast data..."
    ):

        new_data = statcast_batter(
            update_start,
            end_date,
            player_id
        )

    if not new_data.empty:

        save_statcast_data(
            new_data,
            player_id,
            update_start,
            end_date
        )

    return len(new_data)

# ==========================================
# LOAD DATABASE DATA
# ==========================================


# ==========================================
# LOAD DATABASE DATA
# ==========================================

def load_batter_data(
    player_id,
    season
):

    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM batter_data
        WHERE batter_id = ?
        AND game_date BETWEEN ? AND ?
        ORDER BY
            game_date,
            game_pk,
            at_bat_number,
            pitch_number
        """,
        conn,
        params=(
            player_id,
            f"{season}-01-01",
            f"{season}-12-31"
        )
    )

    conn.close()

    if not df.empty:

        df["game_date"] = pd.to_datetime(
            df["game_date"]
        )

    return df


# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.title("Player Selection")

st.sidebar.subheader("Hitters")

first_name = st.sidebar.text_input(
    "First Name",
    value=""
)

last_name = st.sidebar.text_input(
    "Last Name",
    value=""
)

mlb_player_id = st.sidebar.text_input(
    "MLB Player ID (optional)",
    value="",
    help=(
        "Enter an MLBAM player ID to bypass "
        "the player-name lookup."
    )
)

season = st.sidebar.selectbox(
    "Season",
    options=[
        2026,
        2025,
        2024,
        2023,
        2022
    ]
)

st.sidebar.divider()

analysis_mode = st.sidebar.radio(
    "View",
    [
        "Season Trends",
        "Game Analysis",
        "Game vs Season Baseline",
        "Contact Quality"
    ]
)

# ==========================================
# LOAD BUTTON
# ==========================================

load_player = st.sidebar.button(
    "Load Hitter",
    type="primary",
    use_container_width=True
)

# ==========================================
# SESSION STATE
# ==========================================


# ==========================================
# SESSION STATE
# ==========================================

if "batter_df" not in st.session_state:
    st.session_state.batter_df = None

if "player_id" not in st.session_state:
    st.session_state.player_id = None

if "loaded_name" not in st.session_state:
    st.session_state.loaded_name = None

if "loaded_season" not in st.session_state:
    st.session_state.loaded_season = None


# ==========================================
# LOAD PLAYER DATA
# ==========================================


# ==========================================
# LOAD PLAYER DATA
# ==========================================

if load_player:

    try:

        if mlb_player_id.strip():

            if not mlb_player_id.strip().isdigit():
                raise ValueError(
                    "MLB Player ID must contain only numbers."
                )

            player_id = int(mlb_player_id.strip())

        else:

            if not first_name.strip() or not last_name.strip():
                raise ValueError(
                    "Enter a first and last name, "
                    "or provide an MLB Player ID."
                )

            player_id = lookup_statcast_id(
                first_name.strip(),
                last_name.strip()
            )

        update_batter_database(
            player_id,
            season
        )

        batter_df = load_batter_data(
            player_id,
            season
        )

        if batter_df.empty:

            st.warning(
                "No Statcast hitting data "
                "was found for this selection."
            )

            st.session_state.batter_df = None

        else:

            st.session_state.batter_df = batter_df

            st.session_state.player_id = player_id

            entered_name = (
                f"{first_name.strip()} "
                f"{last_name.strip()}"
            ).strip()

            st.session_state.loaded_name = (
                entered_name
                if entered_name
                else f"MLB Player ID {player_id}"
            )

            st.session_state.loaded_season = season

    except Exception as error:

        st.error(
            f"Unable to load hitter: {error}"
        )

# ==========================================
# MAIN APPLICATION
# ==========================================


# ==========================================
# MAIN APPLICATION
# ==========================================

batter_df = st.session_state.batter_df

if batter_df is None:

    st.info(
        "Select a hitter and season, "
        "then click **Load Hitter**."
    )

    st.stop()


player_name = st.session_state.loaded_name

loaded_season = st.session_state.loaded_season


# ==========================================
# PLAYER HEADER
# ==========================================

st.header(player_name)

latest_data_date = batter_df["game_date"].max()

latest_data_display = latest_data_date.strftime(
    "%B %d, %Y"
)

st.caption(
    f"{loaded_season} • "
    f"Data through {latest_data_display}"
)


# ==========================================
# PITCH TYPE SELECTION
# ==========================================

pitch_options = (
    batter_df[["pitch_type", "pitch_name"]]
    .dropna()
    .drop_duplicates()
    .sort_values("pitch_name")
)

pitch_dictionary = dict(
    zip(
        pitch_options["pitch_name"],
        pitch_options["pitch_type"]
    )
)

pitch_names = ["All Pitch Types"] + list(
    pitch_dictionary.keys()
)

selected_pitch_name = st.sidebar.selectbox(
    "Pitch Type",
    options=pitch_names
)


# ==========================================
# FILTER SELECTED PITCH TYPE
# ==========================================

if selected_pitch_name == "All Pitch Types":

    selected_batter_df = batter_df.copy()

else:

    selected_pitch_type = pitch_dictionary[
        selected_pitch_name
    ]

    selected_batter_df = batter_df[
        batter_df["pitch_type"] == selected_pitch_type
    ].copy()


# ==========================================
# BATTED BALL DATA
# ==========================================

# Only batted balls with valid exit velocity
# and launch angle are included in these
# contact quality calculations.

batted_ball_df = selected_batter_df[
    selected_batter_df["type"].eq("X")
    & selected_batter_df["launch_speed"].notna()
    & selected_batter_df["launch_angle"].notna()
].copy()


# ==========================================
# CONTACT QUALITY METRICS
# ==========================================

batted_ball_count = len(batted_ball_df)

average_exit_velocity = (
    batted_ball_df["launch_speed"].mean()
)

hard_hit_count = (
    batted_ball_df["launch_speed"] >= 95
).sum()

hard_hit_rate = (
    hard_hit_count / batted_ball_count * 100
    if batted_ball_count > 0
    else None
)


# Statcast launch_speed_angle category 6
# identifies barrels.

barrel_count = (
    batted_ball_df["launch_speed_angle"] == 6
).sum()

barrel_rate = (
    barrel_count / batted_ball_count * 100
    if batted_ball_count > 0
    else None
)


# ==========================================
# DISPLAY SUMMARY METRICS
# ==========================================

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Tracked Batted Balls",
    f"{batted_ball_count:,}"
)

metric2.metric(
    "Average Exit Velocity",
    (
        f"{average_exit_velocity:.1f} mph"
        if pd.notna(average_exit_velocity)
        else "N/A"
    )
)

metric3.metric(
    "Hard-Hit Rate",
    (
        f"{hard_hit_rate:.1f}%"
        if hard_hit_rate is not None
        else "N/A"
    )
)

metric4.metric(
    "Barrel Rate",
    (
        f"{barrel_rate:.1f}%"
        if barrel_rate is not None
        else "N/A"
    )
)

st.caption(
    "Tracked batted-ball events "
    "with valid exit velocity and launch angle. "
    "Hard-hit balls have exit velocity of at least "
    "95 mph. Barrel rate uses Statcast's "
    "classification. "
)

st.divider()


# ==========================================
# SEASON TRENDS
# ==========================================


# ==========================================
# SEASON TRENDS
# ==========================================

if analysis_mode == "Season Trends":

    st.subheader(
        "Average Exit Velocity by Game"
    )

    st.caption(
        f"{selected_pitch_name} • "
        "Each point represents the average exit "
        "velocity of tracked batted balls in one game."
    )

    # --------------------------------------
    # CREATE GAME-BY-GAME SUMMARY
    # --------------------------------------

    season_data = batted_ball_df.copy()

    season_data["hard_hit"] = (
        season_data["launch_speed"] >= 95
    )

    season_summary = (
        season_data
        .groupby(["game_pk", "game_date"])
        .agg(
            average_exit_velocity=(
                "launch_speed", "mean"
            ),
            maximum_exit_velocity=(
                "launch_speed", "max"
            ),
            batted_balls=(
                "launch_speed", "count"
            ),
            hard_hit_balls=(
                "hard_hit", "sum"
            )
        )
        .reset_index()
        .sort_values(["game_date", "game_pk"])
    )

    # --------------------------------------
    # CHECK FOR DATA
    # --------------------------------------

    if season_summary.empty:

        st.warning(
            "No tracked batted-ball data is "
            "available for this selection."
        )

    else:

        # ----------------------------------
        # CALCULATE HARD-HIT RATE
        # ----------------------------------

        season_summary["hard_hit_rate"] = (
            season_summary["hard_hit_balls"]
            / season_summary["batted_balls"]
            * 100
        )

        season_summary["date_display"] = (
            season_summary["game_date"]
            .dt.strftime("%b %d, %Y")
        )

        # ----------------------------------
        # BUILD INTERACTIVE CHART
        # ----------------------------------

        season_fig = go.Figure()

        season_fig.add_trace(
            go.Scatter(
                x=season_summary["game_date"],
                y=season_summary[
                    "average_exit_velocity"
                ],
                mode="lines+markers",
                name="Average Exit Velocity",
                customdata=season_summary[
                    [
                        "date_display",
                        "maximum_exit_velocity",
                        "batted_balls",
                        "hard_hit_rate",
                        "game_pk"
                    ]
                ].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Average EV: %{y:.1f} mph<br>"
                    "Maximum EV: "
                    "%{customdata[1]:.1f} mph<br>"
                    "Tracked Batted Balls: "
                    "%{customdata[2]:.0f}<br>"
                    "Hard-Hit Rate: "
                    "%{customdata[3]:.1f}%<br>"
                    "Game ID: %{customdata[4]}"
                    "<extra></extra>"
                ),
                marker=dict(size=8),
                line=dict(width=2)
            )
        )

        # ----------------------------------
        # CHART LAYOUT
        # ----------------------------------

        season_fig.update_layout(
            xaxis_title="Game Date",
            yaxis_title="Average Exit Velocity (mph)",
            hovermode="closest",
            height=500,
            margin=dict(
                l=20,
                r=20,
                t=20,
                b=20
            ),
            showlegend=False
        )

        st.plotly_chart(
            season_fig,
            use_container_width=True
        )

        # ----------------------------------
        # SAMPLE SIZE NOTE
        # ----------------------------------

        st.caption(
            "Game averages are based on tracked "
            "batted balls with valid exit velocity "
            "and launch angle. Games with only one "
            "qualifying batted ball are included; "
            "interpret small samples cautiously."
        )

        # ----------------------------------
        # GAME DATA TABLE
        # ----------------------------------

        with st.expander("View Game Data"):

            display_season = season_summary[
                [
                    "game_date",
                    "game_pk",
                    "average_exit_velocity",
                    "maximum_exit_velocity",
                    "batted_balls",
                    "hard_hit_rate"
                ]
            ].copy()

            display_season["game_date"] = (
                display_season["game_date"]
                .dt.strftime("%b %d, %Y")
            )

            display_season = display_season.rename(
                columns={
                    "game_date": "Game Date",
                    "game_pk": "Game ID",
                    "average_exit_velocity":
                        "Average Exit Velocity",
                    "maximum_exit_velocity":
                        "Maximum Exit Velocity",
                    "batted_balls":
                        "Tracked Batted Balls",
                    "hard_hit_rate":
                        "Hard-Hit Rate (%)"
                }
            )

            display_season[
                [
                    "Average Exit Velocity",
                    "Maximum Exit Velocity",
                    "Hard-Hit Rate (%)"
                ]
            ] = display_season[
                [
                    "Average Exit Velocity",
                    "Maximum Exit Velocity",
                    "Hard-Hit Rate (%)"
                ]
            ].round(1)

            st.dataframe(
                display_season,
                use_container_width=True,
                hide_index=True
            )

# ==========================================
# GAME ANALYSIS
# ==========================================


# ==========================================
# GAME ANALYSIS
# ==========================================

elif analysis_mode == "Game Analysis":

    st.subheader("Individual Game Hitting Analysis")

    # --------------------------------------
    # BUILD GAME LIST
    # --------------------------------------

    games = (
        selected_batter_df[
            [
                "game_pk",
                "game_date",
                "away_team",
                "home_team"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            ["game_date", "game_pk"],
            ascending=False
        )
        .copy()
    )

    if games.empty:
        st.warning("No games available for this selection.")
        st.stop()

    games["game_label"] = (
        games["game_date"].dt.strftime("%b %d, %Y")
        + " — "
        + games["away_team"].fillna("?")
        + " @ "
        + games["home_team"].fillna("?")
        + " ("
        + games["game_pk"].astype(str)
        + ")"
    )

    game_dictionary = dict(
        zip(games["game_label"], games["game_pk"])
    )

    selected_game_label = st.selectbox(
        "Game",
        options=list(game_dictionary.keys())
    )

    selected_game_pk = game_dictionary[
        selected_game_label
    ]

    # --------------------------------------
    # FILTER SELECTED GAME
    # --------------------------------------

    game_df = selected_batter_df[
        selected_batter_df["game_pk"] == selected_game_pk
    ].copy()

    game_df = (
        game_df
        .sort_values(
            ["inning", "at_bat_number", "pitch_number"]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------
    # INNING SELECTION
    # --------------------------------------

    available_innings = sorted(
        game_df["inning"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    selected_inning = st.selectbox(
        "Inning",
        options=["All Innings"] + available_innings
    )

    if selected_inning != "All Innings":
        game_df = game_df[
            game_df["inning"] == selected_inning
        ].copy()

    # --------------------------------------
    # BATTED BALL EVENTS
    # --------------------------------------

    game_batted_df = game_df[
        game_df["type"].eq("X")
        & game_df["launch_speed"].notna()
        & game_df["launch_angle"].notna()
    ].copy()

    game_batted_df = (
        game_batted_df
        .sort_values(
            ["inning", "at_bat_number", "pitch_number"]
        )
        .reset_index(drop=True)
    )

    game_batted_df["batted_ball_sequence"] = range(
        1, len(game_batted_df) + 1
    )

    # --------------------------------------
    # CONTACT QUALITY CALCULATIONS
    # --------------------------------------

    batted_ball_count = len(game_batted_df)

    average_exit_velocity = (
        game_batted_df["launch_speed"].mean()
    )

    maximum_exit_velocity = (
        game_batted_df["launch_speed"].max()
    )

    average_launch_angle = (
        game_batted_df["launch_angle"].mean()
    )

    hard_hit_count = (
        game_batted_df["launch_speed"] >= 95
    ).sum()

    hard_hit_rate = (
        hard_hit_count / batted_ball_count * 100
        if batted_ball_count > 0
        else None
    )

    classified_balls = game_batted_df[
        game_batted_df["launch_speed_angle"].notna()
    ]

    barrel_count = (
        classified_balls["launch_speed_angle"] == 6
    ).sum()

    barrel_rate = (
        barrel_count / len(classified_balls) * 100
        if len(classified_balls) > 0
        else None
    )

    # --------------------------------------
    # DISPLAY GAME SUMMARY
    # --------------------------------------

    st.markdown(f"### {selected_game_label}")

    inning_display = (
        "All Innings"
        if selected_inning == "All Innings"
        else f"Inning {selected_inning}"
    )

    st.caption(
        f"{selected_pitch_name} • {inning_display}"
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Tracked Batted Balls",
        f"{batted_ball_count:,}"
    )

    metric2.metric(
        "Average Exit Velocity",
        f"{average_exit_velocity:.1f} mph"
        if pd.notna(average_exit_velocity)
        else "N/A"
    )

    metric3.metric(
        "Maximum Exit Velocity",
        f"{maximum_exit_velocity:.1f} mph"
        if pd.notna(maximum_exit_velocity)
        else "N/A"
    )

    metric4.metric(
        "Hard-Hit Rate",
        f"{hard_hit_rate:.1f}%"
        if hard_hit_rate is not None
        else "N/A"
    )

    detail1, detail2 = st.columns(2)

    detail1.metric(
        "Average Launch Angle",
        f"{average_launch_angle:.1f}°"
        if pd.notna(average_launch_angle)
        else "N/A"
    )

    detail2.metric(
        "Barrel Rate",
        f"{barrel_rate:.1f}%"
        if barrel_rate is not None
        else "N/A"
    )

    st.caption(
        "Metrics use tracked batted balls with valid "
        "exit velocity and launch angle. Barrel rate "
        "uses events with an available Statcast "
        "launch_speed_angle classification."
    )

    st.divider()

    # --------------------------------------
    # CHECK FOR BATTED BALL DATA
    # --------------------------------------

    if game_batted_df.empty:
        st.warning(
            "No tracked batted balls with exit velocity "
            "and launch angle were found for this game "
            "and inning selection."
        )
        st.stop()

    # --------------------------------------
    # PREPARE INTERACTIVE CHART DATA
    # --------------------------------------

    game_batted_df["result_display"] = (
        game_batted_df["events"]
        .fillna("Unknown")
        .str.replace("_", " ", regex=False)
        .str.title()
    )

    game_batted_df["pitch_display"] = (
        game_batted_df["pitch_name"]
        .fillna("Unknown")
    )

    game_batted_df["rolling_exit_velocity"] = (
        game_batted_df["launch_speed"]
        .rolling(window=3, min_periods=1)
        .mean()
    )

    # --------------------------------------
    # EXIT VELOCITY BY BATTED BALL
    # --------------------------------------

    st.subheader("Batted-Ball Exit Velocity")

    st.caption(
        "Each point represents one tracked batted ball. "
        "Hover to see launch angle, pitch type, inning, "
        "and plate appearance result."
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=game_batted_df["batted_ball_sequence"],
            y=game_batted_df["launch_speed"],
            mode="markers",
            name="Individual Batted Ball",
            customdata=game_batted_df[
                [
                    "inning",
                    "launch_angle",
                    "pitch_display",
                    "result_display",
                    "at_bat_number"
                ]
            ].to_numpy(),
            hovertemplate=(
                "<b>Batted Ball #%{x}</b><br>"
                "Exit Velocity: %{y:.1f} mph<br>"
                "Launch Angle: %{customdata[1]:.1f}°<br>"
                "Inning: %{customdata[0]}<br>"
                "Pitch: %{customdata[2]}<br>"
                "Result: %{customdata[3]}<br>"
                "At-Bat Number: %{customdata[4]}"
                "<extra></extra>"
            ),
            marker=dict(size=10)
        )
    )

    fig.add_trace(
        go.Scatter(
            x=game_batted_df["batted_ball_sequence"],
            y=game_batted_df["rolling_exit_velocity"],
            mode="lines",
            name="3-Batted-Ball Rolling Average",
            hovertemplate=(
                "Batted Ball %{x}<br>"
                "Rolling Average: %{y:.1f} mph"
                "<extra></extra>"
            ),
            line=dict(width=3)
        )
    )

    fig.update_layout(
        xaxis_title="Batted-Ball Sequence",
        yaxis_title="Exit Velocity (mph)",
        hovermode="closest",
        height=520,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        )
    )

    fig.update_xaxes(dtick=1)

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.caption(
        "The rolling average uses up to three consecutive "
        "tracked batted balls within the selected view. "
        "It is descriptive and may be unstable in small samples."
    )

    # --------------------------------------
    # CONTACT QUALITY BY INNING
    # --------------------------------------

    st.subheader("Contact Quality by Inning")

    full_game_batted_df = selected_batter_df[
        (selected_batter_df["game_pk"] == selected_game_pk)
        & selected_batter_df["type"].eq("X")
        & selected_batter_df["launch_speed"].notna()
        & selected_batter_df["launch_angle"].notna()
    ].copy()

    full_game_batted_df["hard_hit"] = (
        full_game_batted_df["launch_speed"] >= 95
    )

    inning_summary = (
        full_game_batted_df
        .groupby("inning")
        .agg(
            average_exit_velocity=("launch_speed", "mean"),
            maximum_exit_velocity=("launch_speed", "max"),
            batted_balls=("launch_speed", "count"),
            hard_hit_balls=("hard_hit", "sum")
        )
        .reset_index()
        .sort_values("inning")
    )

    if not inning_summary.empty:

        inning_summary["hard_hit_rate"] = (
            inning_summary["hard_hit_balls"]
            / inning_summary["batted_balls"]
            * 100
        )

        inning_fig = go.Figure()

        inning_fig.add_trace(
            go.Scatter(
                x=inning_summary["inning"],
                y=inning_summary["average_exit_velocity"],
                mode="lines+markers",
                name="Average Exit Velocity",
                customdata=inning_summary[
                    [
                        "batted_balls",
                        "maximum_exit_velocity",
                        "hard_hit_rate"
                    ]
                ].to_numpy(),
                hovertemplate=(
                    "Inning %{x}<br>"
                    "Average EV: %{y:.1f} mph<br>"
                    "Batted Balls: %{customdata[0]:.0f}<br>"
                    "Maximum EV: %{customdata[1]:.1f} mph<br>"
                    "Hard-Hit Rate: %{customdata[2]:.1f}%"
                    "<extra></extra>"
                )
            )
        )

        inning_fig.update_layout(
            xaxis_title="Inning",
            yaxis_title="Average Exit Velocity (mph)",
            height=420,
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20)
        )

        inning_fig.update_xaxes(dtick=1)

        st.plotly_chart(
            inning_fig,
            use_container_width=True
        )

        st.caption(
            "Inning averages are calculated across the "
            "entire selected game, regardless of the "
            "inning filter above."
        )

    # --------------------------------------
    # BATTED BALL DATA TABLE
    # --------------------------------------

    with st.expander("View Batted-Ball Data"):

        display_df = game_batted_df[
            [
                "batted_ball_sequence",
                "inning",
                "at_bat_number",
                "pitch_display",
                "launch_speed",
                "launch_angle",
                "bb_type",
                "result_display"
            ]
        ].copy()

        display_df = display_df.rename(
            columns={
                "batted_ball_sequence": "Batted Ball",
                "inning": "Inning",
                "at_bat_number": "At-Bat Number",
                "pitch_display": "Pitch Type",
                "launch_speed": "Exit Velocity",
                "launch_angle": "Launch Angle",
                "bb_type": "Batted-Ball Type",
                "result_display": "Result"
            }
        )

        display_df[
            ["Exit Velocity", "Launch Angle"]
        ] = display_df[
            ["Exit Velocity", "Launch Angle"]
        ].round(1)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )


# ==========================================
# GAME VS SEASON BASELINE
# ==========================================


# ==========================================
# GAME VS SEASON BASELINE
# ==========================================

elif analysis_mode == "Game vs Season Baseline":

    st.subheader("Game vs. Season Hitting Baseline")

    st.caption(
        "Compare individual game contact quality "
        "against the selected hitter's season baseline."
    )

    # --------------------------------------
    # PREPARE BATTED BALL DATA
    # --------------------------------------

    baseline_df = batted_ball_df.copy()

    baseline_df["launch_speed"] = pd.to_numeric(
        baseline_df["launch_speed"],
        errors="coerce"
    )

    baseline_df["launch_angle"] = pd.to_numeric(
        baseline_df["launch_angle"],
        errors="coerce"
    )

    baseline_df["launch_speed_angle"] = pd.to_numeric(
        baseline_df["launch_speed_angle"],
        errors="coerce"
    )

    baseline_df["hard_hit"] = (
        baseline_df["launch_speed"] >= 95
    ).astype(int)

    baseline_df["barrel"] = (
        baseline_df["launch_speed_angle"] == 6
    ).astype(int)

    baseline_df["barrel_eligible"] = (
        baseline_df["launch_speed_angle"].notna()
    ).astype(int)

    if baseline_df.empty:

        st.warning(
            "No tracked batted-ball data is available "
            "for this pitch-type selection."
        )

        st.stop()

    # --------------------------------------
    # BUILD GAME LIST
    # --------------------------------------

    games = (
        selected_batter_df[
            [
                "game_pk",
                "game_date",
                "away_team",
                "home_team"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            ["game_date", "game_pk"],
            ascending=False
        )
        .copy()
    )

    games["game_label"] = (
        games["game_date"].dt.strftime("%b %d, %Y")
        + " — "
        + games["away_team"].fillna("?")
        + " @ "
        + games["home_team"].fillna("?")
        + " ("
        + games["game_pk"].astype(str)
        + ")"
    )

    game_dictionary = dict(
        zip(games["game_label"], games["game_pk"])
    )

    selected_game_label = st.selectbox(
        "Select Game",
        options=list(game_dictionary.keys())
    )

    selected_game_pk = game_dictionary[
        selected_game_label
    ]

    game_df = baseline_df[
        baseline_df["game_pk"] == selected_game_pk
    ].copy()

    # --------------------------------------
    # GAME SUMMARY FUNCTION
    # --------------------------------------

    def calculate_contact_metrics(df):

        count = len(df)

        if count == 0:
            return {
                "batted_balls": 0,
                "average_exit_velocity": None,
                "hard_hit_rate": None,
                "barrel_rate": None,
                "average_launch_angle": None
            }

        classified = df[
            df["barrel_eligible"] == 1
        ]

        return {
            "batted_balls": count,
            "average_exit_velocity":
                df["launch_speed"].mean(),
            "hard_hit_rate":
                df["hard_hit"].mean() * 100,
            "barrel_rate":
                (
                    classified["barrel"].mean() * 100
                    if not classified.empty
                    else None
                ),
            "average_launch_angle":
                df["launch_angle"].mean()
        }

    game_metrics = calculate_contact_metrics(
        game_df
    )

    # --------------------------------------
    # BUILD GAME-LEVEL SEASON BASELINES
    # --------------------------------------

    game_summaries = []

    for game_pk, group in baseline_df.groupby("game_pk"):

        metrics = calculate_contact_metrics(group)

        metrics["game_pk"] = game_pk

        game_summaries.append(metrics)

    season_games = pd.DataFrame(game_summaries)

    # Exclude selected game to avoid comparing
    # the game partly against itself.

    comparison_games = season_games[
        season_games["game_pk"] != selected_game_pk
    ].copy()

    # Require at least one tracked batted ball
    # in each comparison game.

    comparison_games = comparison_games[
        comparison_games["batted_balls"] > 0
    ]

    # --------------------------------------
    # DEFINE METRICS
    # --------------------------------------

    metric_config = {
        "average_exit_velocity": {
            "label": "Average Exit Velocity",
            "unit": "mph"
        },
        "hard_hit_rate": {
            "label": "Hard-Hit Rate",
            "unit": "%"
        },
        "barrel_rate": {
            "label": "Barrel Rate",
            "unit": "%"
        },
        "average_launch_angle": {
            "label": "Average Launch Angle",
            "unit": "°"
        }
    }

    # --------------------------------------
    # CALCULATE BASELINES AND DEVIATIONS
    # --------------------------------------

    results = []

    for metric, config in metric_config.items():

        game_value = game_metrics[metric]

        comparison_values = pd.to_numeric(
            comparison_games[metric],
            errors="coerce"
        ).dropna()

        baseline_value = (
            comparison_values.mean()
            if not comparison_values.empty
            else None
        )

        baseline_std = (
            comparison_values.std(ddof=1)
            if len(comparison_values) >= 2
            else None
        )

        if (
            game_value is not None
            and baseline_value is not None
            and pd.notna(game_value)
            and pd.notna(baseline_value)
        ):

            difference = game_value - baseline_value

        else:

            difference = None

        if (
            difference is not None
            and baseline_std is not None
            and pd.notna(baseline_std)
            and baseline_std > 0
        ):

            z_score = difference / baseline_std

        else:

            z_score = None

        results.append({
            "metric": config["label"],
            "game_value": game_value,
            "season_baseline": baseline_value,
            "difference": difference,
            "z_score": z_score,
            "unit": config["unit"],
            "comparison_games": len(comparison_values)
        })

    results_df = pd.DataFrame(results)

    # --------------------------------------
    # DISPLAY SAMPLE SIZE
    # --------------------------------------

    st.markdown(f"### {selected_game_label}")

    sample1, sample2 = st.columns(2)

    sample1.metric(
        "Selected Game Batted Balls",
        game_metrics["batted_balls"]
    )

    sample2.metric(
        "Other Games with Tracked Contact",
        len(comparison_games)
    )

    if game_metrics["batted_balls"] < 3:

        st.warning(
            "The selected game has fewer than three "
            "tracked batted balls. Individual-game "
            "metrics may be highly variable."
        )

    if len(comparison_games) < 10:

        st.warning(
            "Fewer than ten other games are available "
            "for the baseline. Interpret deviations "
            "and standardized scores cautiously."
        )

    # --------------------------------------
    # FORMAT METRIC VALUES
    # --------------------------------------

    def format_metric(value, unit):

        if value is None or pd.isna(value):
            return "N/A"

        return f"{value:.1f}{unit}"

    # --------------------------------------
    # DISPLAY COMPARISON TABLE
    # --------------------------------------

    st.subheader("Game vs. Season Comparison")

    display_rows = []

    for _, row in results_df.iterrows():

        unit = row["unit"]

        display_rows.append({
            "Metric": row["metric"],
            "Selected Game": format_metric(
                row["game_value"], unit
            ),
            "Other-Game Baseline": format_metric(
                row["season_baseline"], unit
            ),
            "Difference": format_metric(
                row["difference"], unit
            ),
            "Z-Score": (
                f"{row['z_score']:+.2f}"
                if pd.notna(row["z_score"])
                else "N/A"
            ),
            "Comparison Games":
                row["comparison_games"]
        })

    st.dataframe(
        pd.DataFrame(display_rows),
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "**Understanding Z-Scores**\n\n"
        "A Z-score measures how far a hitter's performance "
        "in a selected game differs from their typical "
        "season performance, expressed in standard deviations.\n\n"
        "- **0:** At the season baseline.\n"
        "- **Positive:** Above the season baseline.\n"
        "- **Negative:** Below the season baseline.\n"
        "- **Larger absolute values:** More unusual performances "
        "relative to normal game-to-game variation.\n\n"
        "For example, a Z-score of +2.0 for average exit velocity "
        "means the game's average was two standard deviations "
        "above the hitter's season baseline.\n\n"
        "**Important:** A higher Z-score does not always mean "
        "better performance. Small samples can also produce "
        "large deviations."
    )


    # --------------------------------------
    # COMPARISON CHART
    # --------------------------------------

    st.subheader("Contact Quality Comparison")

    chart_df = results_df.dropna(
        subset=["game_value", "season_baseline"]
    ).copy()

    if not chart_df.empty:

        # Percentage metrics and mph have different
        # scales, so display each metric separately.

        for _, row in chart_df.iterrows():

            st.markdown(f"**{row['metric']}**")

            comparison_fig = go.Figure()

            comparison_fig.add_trace(
                go.Bar(
                    x=["Selected Game", "Other-Game Baseline"],
                    y=[
                        row["game_value"],
                        row["season_baseline"]
                    ],
                    text=[
                        format_metric(
                            row["game_value"], row["unit"]
                        ),
                        format_metric(
                            row["season_baseline"], row["unit"]
                        )
                    ],
                    textposition="auto",
                    marker_color=[
                        "#2E86C1",
                        "#A6ACAF"
                    ],
                    hovertemplate=(
                        "%{x}<br>"
                        "%{y:.1f}" + row["unit"]
                        + "<extra></extra>"
                    )
                )
            )

            comparison_fig.update_layout(
                height=280,
                showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis_title=row["unit"]
            )

            st.plotly_chart(
                comparison_fig,
                use_container_width=True
            )

    # --------------------------------------
    # STANDARDIZED DEVIATIONS
    # --------------------------------------

    st.subheader("Standardized Game Deviations")

    z_df = results_df.dropna(
        subset=["z_score"]
    ).copy()

    if not z_df.empty:

        z_fig = go.Figure()

        z_fig.add_trace(
            go.Bar(
                x=z_df["z_score"],
                y=z_df["metric"],
                orientation="h",
                marker_color=[
                    "#27AE60" if value >= 0
                    else "#C0392B"
                    for value in z_df["z_score"]
                ],
                text=z_df["z_score"].map(
                    lambda value: f"{value:+.2f}"
                ),
                textposition="auto",
                hovertemplate=(
                    "%{y}<br>"
                    "Z-Score: %{x:+.2f}"
                    "<extra></extra>"
                )
            )
        )

        z_fig.add_vline(
            x=0,
            line_dash="dash",
            line_color="gray"
        )

        z_fig.update_layout(
            xaxis_title="Standard Deviations from Baseline",
            height=360,
            margin=dict(l=20, r=20, t=20, b=20)
        )

        st.plotly_chart(
            z_fig,
            use_container_width=True
        )

        st.caption(
            "Positive values indicate above-baseline "
            "measurements; negative values indicate "
            "below-baseline measurements. A higher "
            "launch angle is not necessarily better, "
            "and small-sample deviations may be noisy."
        )

    else:

        st.info(
            "Insufficient comparison-game variation "
            "to calculate standardized deviations."
        )

# ==========================================
# CONTACT QUALITY
# ==========================================

elif analysis_mode == "Contact Quality":

    st.subheader("Statcast Contact Quality")

    st.caption(
        f"{selected_pitch_name} • "
        "Distribution of Statcast batted-ball "
        "contact types."
    )

    contact_labels = {
        1: "Weak",
        2: "Topped",
        3: "Under",
        4: "Flare/Burner",
        5: "Solid Contact",
        6: "Barrel"
    }

    contact_df = batted_ball_df.copy()

    contact_df["launch_speed_angle"] = pd.to_numeric(
        contact_df["launch_speed_angle"],
        errors="coerce"
    )

    contact_df = contact_df[
        contact_df["launch_speed_angle"].isin(
            contact_labels.keys()
        )
    ].copy()

    if contact_df.empty:

        st.warning(
            "No classified batted balls are "
            "available for this selection."
        )

    else:

        contact_df["contact_category"] = (
            contact_df["launch_speed_angle"]
            .map(contact_labels)
        )

        category_counts = (
            contact_df["contact_category"]
            .value_counts()
            .reindex(
                list(contact_labels.values()),
                fill_value=0
            )
        )

        category_summary = (
            category_counts
            .rename_axis("Contact Category")
            .reset_index(name="Batted Balls")
        )

        category_summary["Percentage"] = (
            category_summary["Batted Balls"]
            / len(contact_df)
            * 100
        )

        st.metric(
            "Classified Batted Balls",
            f"{len(contact_df):,}"
        )

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=category_summary["Contact Category"],
                y=category_summary["Percentage"],
                customdata=category_summary[
                    ["Batted Balls"]
                ].to_numpy(),
                text=category_summary[
                    "Percentage"
                ].map(lambda x: f"{x:.1f}%"),
                textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Share: %{y:.1f}%<br>"
                    "Batted Balls: %{customdata[0]}"
                    "<extra></extra>"
                )
            )
        )

        fig.update_layout(
            title="Distribution of Contact Types",
            xaxis_title="Contact Classification",
            yaxis_title="Percentage of Classified Batted Balls",
            yaxis=dict(rangemode="tozero"),
            height=480,
            margin=dict(l=20, r=20, t=50, b=20)
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.caption(
            "Percentages are calculated using only "
            "batted balls with a valid Statcast "
            "launch_speed_angle classification."
        )

        with st.expander("View Contact Quality Data"):

            st.dataframe(
                category_summary.round(1),
                use_container_width=True,
                hide_index=True
            )
