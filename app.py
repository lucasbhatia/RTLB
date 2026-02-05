"""Odds movement dashboard - compare morning→evening movements across books."""

import streamlit as st
from datetime import datetime
import pytz

from database import (
    get_all_dates,
    get_movement_by_book,
    get_snapshot_counts,
    init_database,
)
from collector import collect_snapshot

# Timezone
EST = pytz.timezone("US/Eastern")

# Page config
st.set_page_config(
    page_title="Odds Movement",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean CSS
st.markdown("""
<style>
    .main .block-container { padding: 1rem 2rem; max-width: 1400px; }
    #MainMenu, footer, header { visibility: hidden; }

    .diff-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 13px;
    }
    .diff-high { background: #fef3c7; color: #92400e; }
    .diff-med { background: #e0f2fe; color: #0369a1; }
    .diff-low { background: #f3f4f6; color: #6b7280; }

    .move-up { color: #059669; }
    .move-down { color: #dc2626; }
    .move-none { color: #6b7280; }
</style>
""", unsafe_allow_html=True)


def format_spread(val):
    """Format spread with +/- sign."""
    if val is None:
        return "—"
    return f"+{val}" if val > 0 else str(val)


def format_move(val):
    """Format movement with +/- sign and color class."""
    if val is None:
        return "—", "move-none"
    if val > 0:
        return f"+{val:.1f}", "move-up"
    elif val < 0:
        return f"{val:.1f}", "move-down"
    return "0", "move-none"


def get_diff_class(diff):
    """Get CSS class based on difference magnitude."""
    if diff >= 1.0:
        return "diff-high"
    elif diff >= 0.5:
        return "diff-med"
    return "diff-low"


@st.dialog("Fetch Morning Odds")
def confirm_morning_fetch():
    """Confirmation dialog for morning odds fetch."""
    st.write("Are you sure you want to fetch **morning** odds?")
    st.caption("This will use an API request and overwrite existing morning data for today.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Fetch", use_container_width=True, type="primary"):
            with st.spinner("Fetching morning odds..."):
                try:
                    collect_snapshot(snapshot_type="morning", force=True)
                    st.success("Morning odds fetched!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


@st.dialog("Fetch Evening Odds")
def confirm_evening_fetch():
    """Confirmation dialog for evening odds fetch."""
    st.write("Are you sure you want to fetch **evening** odds?")
    st.caption("This will use an API request and overwrite existing evening data for today.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Fetch", use_container_width=True, type="primary"):
            with st.spinner("Fetching evening odds..."):
                try:
                    collect_snapshot(snapshot_type="evening", force=True)
                    st.success("Evening odds fetched!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


def render_game_card(game, container):
    """Render a game card showing movement by book."""
    books = game["books"]

    # Sort by largest spread movement
    book_list = sorted(
        books.items(),
        key=lambda x: abs(x[1]["spread_move"]) if x[1]["spread_move"] else 0,
        reverse=True
    )

    # Find max movements for highlighting
    max_spread_move = max(
        (abs(d["spread_move"]) for d in books.values() if d["spread_move"] is not None),
        default=0
    )
    max_total_move = max(
        (abs(d["total_move"]) for d in books.values() if d["total_move"] is not None),
        default=0
    )

    league_icon = "🏀" if "nba" in game["league"].lower() else "🏈"
    league_name = "NBA" if "nba" in game["league"].lower() else "NCAAB"

    spread_class = get_diff_class(game["max_abs_spread"])
    total_class = get_diff_class(game["max_abs_total"])

    with container.container(border=True):
        # Header
        h1, h2 = st.columns([3, 2])
        with h1:
            st.caption(f"{league_icon} {league_name}")
            st.markdown(f"**{game['away_team']} @ {game['home_team']}**")
        with h2:
            st.markdown(
                f'<div style="text-align:right;padding-top:4px">'
                f'<span class="diff-badge {spread_class}">Sprd: {game["max_abs_spread"]:.1f}</span> '
                f'<span class="diff-badge {total_class}">Tot: {game["max_abs_total"]:.1f}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Column headers
        cols = st.columns([2, 1.5, 1, 1.5, 1])
        cols[0].markdown("**Book**")
        cols[1].markdown("**Spread**")
        cols[2].markdown("**Δ**")
        cols[3].markdown("**Total**")
        cols[4].markdown("**Δ**")

        # Book rows
        for book_name, data in book_list:
            spread_move = data["spread_move"]
            total_move = data["total_move"]

            # Check if this book has the max movement
            is_max_spread = spread_move is not None and abs(spread_move) == max_spread_move and max_spread_move > 0
            is_max_total = total_move is not None and abs(total_move) == max_total_move and max_total_move > 0

            # Format values
            open_spread = format_spread(data["open_spread"])
            close_spread = format_spread(data["close_spread"])
            open_total = f"{data['open_total']}" if data["open_total"] else "—"
            close_total = f"{data['close_total']}" if data["close_total"] else "—"

            spread_str = f"+{spread_move:.1f}" if spread_move and spread_move > 0 else f"{spread_move:.1f}" if spread_move else "0.0"
            total_str = f"+{total_move:.1f}" if total_move and total_move > 0 else f"{total_move:.1f}" if total_move else "0.0"

            cols = st.columns([2, 1.5, 1, 1.5, 1])
            cols[0].text(book_name)

            # Spread - orange highlight for highest
            if is_max_spread:
                cols[1].markdown(f":orange[**{open_spread} → {close_spread}**]")
                cols[2].markdown(f":orange[**{spread_str}**]")
            else:
                cols[1].text(f"{open_spread} → {close_spread}")
                cols[2].text(spread_str)

            # Total - green highlight for highest
            if is_max_total:
                cols[3].markdown(f":green[**{open_total} → {close_total}**]")
                cols[4].markdown(f":green[**{total_str}**]")
            else:
                cols[3].text(f"{open_total} → {close_total}")
                cols[4].text(total_str)


# Initialize
init_database()

# Always work with today's date only
now = datetime.now(EST)
today = now.strftime("%Y-%m-%d")
current_hour = now.hour

# Auto-fetch today's data if missing (runs once per session)
if "auto_fetched" not in st.session_state:
    st.session_state.auto_fetched = False

if not st.session_state.auto_fetched:
    fetched_something = False

    # Check if today's data exists
    today_counts = get_snapshot_counts(today)
    morning_exists = today_counts.get("morning", 0) > 0
    evening_exists = today_counts.get("evening", 0) > 0

    # Auto-fetch morning if it's past 1 PM and missing
    if current_hour >= 13 and not morning_exists:
        with st.spinner(f"Fetching morning odds for {today}..."):
            try:
                collect_snapshot(snapshot_type="morning", force=True)
                fetched_something = True
            except Exception as e:
                st.error(f"Failed to fetch morning odds: {e}")

    # Auto-fetch evening if it's past 6 PM and missing
    if current_hour >= 18 and not evening_exists:
        with st.spinner(f"Fetching evening odds for {today}..."):
            try:
                collect_snapshot(snapshot_type="evening", force=True)
                fetched_something = True
            except Exception as e:
                st.error(f"Failed to fetch evening odds: {e}")

    st.session_state.auto_fetched = True

    # Rerun to show new data
    if fetched_something:
        st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("### 🔄 Fetch Odds")

    col_m, col_e = st.columns(2)

    with col_m:
        if st.button("☀️ Morning", use_container_width=True, key="sidebar_morning"):
            confirm_morning_fetch()

    with col_e:
        if st.button("🌙 Evening", use_container_width=True, key="sidebar_evening"):
            confirm_evening_fetch()

    st.markdown("---")
    st.markdown("### Filters")

    # Always use today's date
    selected_date = today
    st.caption(f"📅 {datetime.strptime(today, '%Y-%m-%d').strftime('%B %d, %Y')}")

    selected_books = st.multiselect(
        "Sportsbooks",
        options=["FanDuel", "DraftKings", "Caesars"],
        default=["FanDuel", "DraftKings", "Caesars"]
    )

    selected_leagues = st.multiselect(
        "Leagues",
        options=["basketball_nba", "basketball_ncaab"],
        default=["basketball_nba", "basketball_ncaab"],
        format_func=lambda x: "NBA" if "nba" in x else "NCAAB"
    )

# Check data availability for today
snapshot_counts = get_snapshot_counts(today)
morning_count = snapshot_counts.get("morning", 0)
evening_count = snapshot_counts.get("evening", 0)

# Show fetch buttons in main area if data is missing
if morning_count == 0 or evening_count == 0:
    st.markdown("## 📊 Odds Movement")
    st.caption(f"Today: {datetime.strptime(today, '%Y-%m-%d').strftime('%B %d, %Y')}")

    if current_hour < 13:
        st.info("Morning odds will be available after 1 PM EST")
    elif current_hour < 18:
        if morning_count == 0:
            st.warning("Morning odds not yet fetched. Click below to fetch.")
        else:
            st.info("Evening odds will be available after 6 PM EST")
    else:
        st.warning("Need both morning and evening snapshots to compare.")

    st.markdown("### Fetch Odds Data")
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        morning_label = "☀️ Morning" + (" ✓" if morning_count > 0 else "")
        morning_disabled = morning_count > 0 or current_hour < 13
        if st.button(morning_label, use_container_width=True, disabled=morning_disabled, key="missing_morning"):
            confirm_morning_fetch()

    with col2:
        evening_label = "🌙 Evening" + (" ✓" if evening_count > 0 else "")
        evening_disabled = evening_count > 0 or current_hour < 18
        if st.button(evening_label, use_container_width=True, disabled=evening_disabled, key="missing_evening"):
            confirm_evening_fetch()

    with col3:
        st.caption(f"Morning: {morning_count} games | Evening: {evening_count} games")
        st.caption(f"Current time: {now.strftime('%I:%M %p')} EST")

    st.stop()

# Get movement data
movement_data = get_movement_by_book(selected_date, selected_books)

if not movement_data:
    st.info("No games with movement data from multiple books")
    st.stop()

# Filter by league
if selected_leagues:
    movement_data = [g for g in movement_data if g["league"] in selected_leagues]

if not movement_data:
    st.info("No games match filters")
    st.stop()

# Header with sort and fetch buttons
h1, h2, h3, h4 = st.columns([2, 1, 1, 1])
with h1:
    st.markdown("## 📊 Odds Movement")
    st.caption("Morning → Evening • Biggest movers at top")
with h2:
    sort_by = st.selectbox(
        "Sort",
        ["Biggest Movement", "Spread Movement", "Total Movement", "Game Time"],
        label_visibility="collapsed"
    )
with h3:
    if st.button("☀️ Morning", use_container_width=True, key="main_morning"):
        confirm_morning_fetch()
with h4:
    if st.button("🌙 Evening", use_container_width=True, key="main_evening"):
        confirm_evening_fetch()

# Apply sorting
if sort_by == "Biggest Movement":
    movement_data.sort(key=lambda x: x["max_abs_spread"] + x["max_abs_total"], reverse=True)
elif sort_by == "Spread Movement":
    movement_data.sort(key=lambda x: x["max_abs_spread"], reverse=True)
elif sort_by == "Total Movement":
    movement_data.sort(key=lambda x: x["max_abs_total"], reverse=True)
else:
    movement_data.sort(key=lambda x: x["commence_time"] or "")

# Stats
max_spread = max(g["max_abs_spread"] for g in movement_data) if movement_data else 0
max_total = max(g["max_abs_total"] for g in movement_data) if movement_data else 0
sharp_games = sum(1 for g in movement_data if g["max_abs_spread"] >= 1.0 or g["max_abs_total"] >= 1.0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Games", len(movement_data))
c2.metric("Max Spread Move", f"{max_spread:.1f}")
c3.metric("Max Total Move", f"{max_total:.1f}")
c4.metric("Sharp Games (≥1.0)", sharp_games)

st.markdown("---")

# Display games in 2 columns
col1, col2 = st.columns(2)

for idx, game in enumerate(movement_data):
    if idx % 2 == 0:
        render_game_card(game, col1)
    else:
        render_game_card(game, col2)

# Footer
st.markdown("---")
st.caption(f"Data: {selected_date} • {', '.join(selected_books)} • {datetime.now().strftime('%H:%M')}")
