
import math
import unicodedata
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

st.set_page_config(
    page_title="Football Analyzer Pro",
    page_icon="⚽",
    layout="wide",
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(145deg, #08111f 0%, #101d30 100%);
    color: #f1f5f9;
}
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
}
.hero {
    background: linear-gradient(120deg, #123b32, #10243b);
    padding: 28px;
    border-radius: 20px;
    border: 1px solid #2d554d;
    margin-bottom: 24px;
}
.hero h1 {
    color: white;
    margin-bottom: 5px;
}
.hero p {
    color: #c5d7d3;
}
.team-card {
    background: #132238;
    border: 1px solid #2b4059;
    border-radius: 18px;
    padding: 18px;
    text-align: center;
}
.result-card {
    background: #132238;
    border: 1px solid #2b4059;
    border-radius: 16px;
    padding: 20px 10px;
    text-align: center;
}
.result-number {
    color: #57e3a0;
    font-size: 30px;
    font-weight: 800;
}
.small-note {
    color: #a9b8cc;
    font-size: 13px;
}
div.stButton > button[kind="primary"] {
    background: #16a36a;
    border: none;
    color: white;
    border-radius: 10px;
    min-height: 48px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>⚽ FOOTBALL ANALYZER PRO</h1>
    <p>Analiz estatistik, fòm ekip, logo, pousantaj 1-X-2 ak nòt estime.</p>
</div>
""", unsafe_allow_html=True)

API_BASE = "https://api.football-data.org/v4"

LEAGUES = {
    "Premier League": "PL",
    "Champions League": "CL",
    "Europa League": "EL",
    "Bundesliga": "BL1",
    "La Liga": "PD",
    "Serie A": "SA",
    "Ligue 1": "FL1",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
}


def normalize_name(name):
    name = str(name or "").lower().strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(
        c for c in name
        if not unicodedata.combining(c)
    )
    return " ".join(name.split())


def same_team(search_name, api_name):
    target = normalize_name(search_name)
    actual = normalize_name(api_name)

    if not target or not actual:
        return False

    return target == actual or target in actual or actual in target


@st.cache_data(ttl=300)
def get_finished_matches(api_key, league_code):
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=365)

    url = f"{API_BASE}/competitions/{league_code}/matches"
    headers = {"X-Auth-Token": api_key.strip()}
    params = {
        "dateFrom": start_date.isoformat(),
        "dateTo": today.isoformat(),
        "status": "FINISHED",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=25,
    )

    if response.status_code == 401:
        raise ValueError("Kle API a pa kòrèk.")

    if response.status_code == 403:
        raise ValueError(
            "Plan API ou a pa bay aksè ak konpetisyon sa a."
        )

    if response.status_code == 429:
        raise ValueError(
            "Limit demann API a depase. Tann anvan ou eseye ankò."
        )

    response.raise_for_status()

    matches = response.json().get("matches", [])
    finished = []

    for match in matches:
        score = match.get("score", {}).get("fullTime", {})

        if (
            match.get("status") == "FINISHED"
            and score.get("home") is not None
            and score.get("away") is not None
        ):
            finished.append(match)

    return finished


def find_team_matches(team_name, matches):
    found = []

    for match in matches:
        home_name = match.get("homeTeam", {}).get("name", "")
        away_name = match.get("awayTeam", {}).get("name", "")

        if same_team(team_name, home_name) or same_team(team_name, away_name):
            found.append(match)

    found.sort(
        key=lambda m: m.get("utcDate", ""),
        reverse=True,
    )

    return found[:5]


def get_team_logo(team_name, matches):
    for match in matches:
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})

        if same_team(team_name, home.get("name", "")):
            return home.get("crest")

        if same_team(team_name, away.get("name", "")):
            return away.get("crest")

    return None


def team_statistics(team_name, matches):
    scored = []
    conceded = []
    details = []
    wins = 0
    draws = 0
    losses = 0

    for match in matches:
        home = match.get("homeTeam", {}).get("name", "")
        away = match.get("awayTeam", {}).get("name", "")
        score = match.get("score", {}).get("fullTime", {})

        hg = score.get("home")
        ag = score.get("away")

        if hg is None or ag is None:
            continue

        if same_team(team_name, home):
            gf, ga = hg, ag
        elif same_team(team_name, away):
            gf, ga = ag, hg
        else:
            continue

        scored.append(gf)
        conceded.append(ga)

        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1

        details.append({
            "Dat": match.get("utcDate", "")[:10],
            "Match": f"{home} vs {away}",
            "Nòt": f"{hg} - {ag}",
            "Gòl make": gf,
            "Gòl pran": ga,
        })

    if not scored:
        return None

    return {
        "played": len(scored),
        "scored": sum(scored) / len(scored),
        "conceded": sum(conceded) / len(conceded),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "details": details,
    }


def poisson_probability(goals, expected):
    expected = max(0.05, expected)
    return (math.exp(-expected) * expected ** goals) / math.factorial(goals)


def predict_match(home_expected, away_expected):
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    scorelines = []

    for home_goals in range(9):
        ph = poisson_probability(home_goals, home_expected)

        for away_goals in range(9):
            pa = poisson_probability(away_goals, away_expected)
            probability = ph * pa

            scorelines.append(
                (home_goals, away_goals, probability)
            )

            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability

    total = home_win + draw + away_win

    if total <= 0:
        return 0.0, 0.0, 0.0, (0, 0)

    home_win = home_win / total * 100
    draw = draw / total * 100
    away_win = away_win / total * 100

    best_score = max(scorelines, key=lambda item: item[2])

    return (
        home_win,
        draw,
        away_win,
        (best_score[0], best_score[1]),
    )


with st.sidebar:
    st.header("⚙️ Paramèt")

    api_key = st.text_input(
        "Football-Data.org API Token",
        type="password",
    )

    league_name = st.selectbox(
        "Konpetisyon",
        list(LEAGUES.keys()),
    )

    st.caption("Done yo depann de aksè kont API ou a.")


col1, col2 = st.columns(2)

with col1:
    home_team = st.text_input(
        "🏠 Ekip lakay",
        placeholder="Egzanp: Arsenal",
    )

with col2:
    away_team = st.text_input(
        "✈️ Ekip deyò",
        placeholder="Egzanp: Chelsea",
    )

analyze = st.button(
    "⚡ ANALIZE MATCH LA",
    type="primary",
    use_container_width=True,
)

if analyze:
    if not api_key.strip():
        st.error("Antre kle API ou nan meni agoch la.")

    elif not home_team.strip() or not away_team.strip():
        st.error("Antre non toude ekip yo.")

    elif same_team(home_team, away_team):
        st.error("Chwazi de ekip diferan.")

    else:
        try:
            with st.spinner("Ap analize done ekip yo..."):
                matches = get_finished_matches(
                    api_key,
                    LEAGUES[league_name],
                )

                home_matches = find_team_matches(home_team, matches)
                away_matches = find_team_matches(away_team, matches)

                home_stats = team_statistics(home_team, home_matches)
                away_stats = team_statistics(away_team, away_matches)

                home_logo = get_team_logo(home_team, matches)
                away_logo = get_team_logo(away_team, matches)

            st.caption(
                f"Konpetisyon: {league_name} · "
                f"Match fini jwenn: {len(matches)}"
            )

            if home_stats is None or away_stats is None:
                st.warning(
                    "Nou pa jwenn ase match istorik pou youn nan ekip yo. "
                    "Verifye non ekip yo, lig la ak aksè API a."
                )

            else:
                home_col, vs_col, away_col = st.columns([4, 1, 4])

                with home_col:
                    st.markdown('<div class="team-card">', unsafe_allow_html=True)
                    if home_logo:
                        st.image(home_logo, width=100)
                    st.subheader(home_team.strip())
                    st.caption("EKIP LAKAY")
                    st.markdown('</div>', unsafe_allow_html=True)

                with vs_col:
                    st.markdown(" ")
                    st.markdown(" ")
                    st.markdown("## VS")

                with away_col:
                    st.markdown('<div class="team-card">', unsafe_allow_html=True)
                    if away_logo:
                        st.image(away_logo, width=100)
                    st.subheader(away_team.strip())
                    st.caption("EKIP DEYÒ")
                    st.markdown('</div>', unsafe_allow_html=True)

                st.divider()
                st.subheader("📈 Fòm dènye match yo")

                home_col, away_col = st.columns(2)

                with home_col:
                    st.markdown(f"**{home_team.strip()}**")
                    st.metric("Match analize", home_stats["played"])
                    st.metric("Mwayèn gòl make", f'{home_stats["scored"]:.2f}')
                    st.metric("Mwayèn gòl pran", f'{home_stats["conceded"]:.2f}')
                    st.write(
                        f"Viktwa: {home_stats['wins']} · "
                        f"NIL: {home_stats['draws']} · "
                        f"Defèt: {home_stats['losses']}"
                    )

                with away_col:
                    st.markdown(f"**{away_team.strip()}**")
                    st.metric("Match analize", away_stats["played"])
                    st.metric("Mwayèn gòl make", f'{away_stats["scored"]:.2f}')
                    st.metric("Mwayèn gòl pran", f'{away_stats["conceded"]:.2f}')
                    st.write(
                        f"Viktwa: {away_stats['wins']} · "
                        f"NIL: {away_stats['draws']} · "
                        f"Defèt: {away_stats['losses']}"
                    )

                # Estimasyon gòl senp, konbine atak ak defans
                home_expected = (
                    home_stats["scored"] + away_stats["conceded"]
                ) / 2

                away_expected = (
                    away_stats["scored"] + home_stats["conceded"]
                ) / 2

                p_home, p_draw, p_away, best_score = predict_match(
                    home_expected,
                    away_expected,
                )

                st.divider()
                st.subheader("🎯 Pousantaj rezilta estime — 1X2")

                c1, cx, c2 = st.columns(3)

                with c1:
                    st.markdown('<div class="result-card">', unsafe_allow_html=True)
                    st.markdown('<div class="result-number">1</div>', unsafe_allow_html=True)
                    st.markdown(f"**{home_team.strip()} genyen**")
                    st.markdown(f"### {p_home:.1f}%")
                    st.progress(int(round(p_home)))
                    st.markdown('</div>', unsafe_allow_html=True)

                with cx:
                    st.markdown('<div class="result-card">', unsafe_allow_html=True)
                    st.markdown('<div class="result-number">X</div>', unsafe_allow_html=True)
                    st.markdown("**Match nil**")
                    st.markdown(f"### {p_draw:.1f}%")
                    st.progress(int(round(p_draw)))
                    st.markdown('</div>', unsafe_allow_html=True)

                with c2:
                    st.markdown('<div class="result-card">', unsafe_allow_html=True)
                    st.markdown('<div class="result-number">2</div>', unsafe_allow_html=True)
                    st.markdown(f"**{away_team.strip()} genyen**")
                    st.markdown(f"### {p_away:.1f}%")
                    st.progress(int(round(p_away)))
                    st.markdown('</div>', unsafe_allow_html=True)

                st.caption(
                    "1 = viktwa ekip lakay · X = match nil · "
                    "2 = viktwa ekip deyò."
                )

                st.divider()
                st.subheader("🥅 Nòt ki pi posib nan modèl la")

                score_col1, score_col2, score_col3 = st.columns(3)

                with score_col1:
                    st.metric("Gòl estime lakay", f"{home_expected:.2f}")

                with score_col2:
                    st.metric("Gòl estime deyò", f"{away_expected:.2f}")

                with score_col3:
                    st.metric(
                        "Nòt ki gen pi gwo pwobabilite",
                        f"{best_score[0]} - {best_score[1]}",
                    )

                probabilities = {
                    home_team.strip(): p_home,
                    "Match nil": p_draw,
                    away_team.strip(): p_away,
                }

                most_likely = max(probabilities, key=probabilities.get)

                st.divider()
                st.subheader("🏁 Konklizyon estatistik")

                if most_likely == "Match nil":
                    st.info(
                        f"Modèl la bay match nil kòm opsyon ki gen "
                        f"pi gwo pousantaj estime: {p_draw:.1f}%."
                    )
                else:
                    st.success(
                        f"Dapre modèl la, {most_likely} se ekip/oswa "
                        f"opsyon ki gen pi gwo pousantaj estime "
                        f"({probabilities[most_likely]:.1f}%)."
                    )

                st.warning(
                    "Atansyon: pousantaj sa yo soti nan yon modèl Poisson "
                    "senp ki sèvi ak mwayèn gòl senk dènye match yo. "
                    "Yo pa yon pwobabilite kalibre sou rezilta reyèl, "
                    "yo pa enkli tout faktè tankou blesi, premye onz, "
                    "avantaj teren oswa fòs opozan yo. Se pa garanti."
                )

                st.divider()
                st.subheader("🗂️ Dènye match ekip yo")

                with st.expander(f"Match {home_team.strip()}"):
                    st.dataframe(
                        home_stats["details"],
                        use_container_width=True,
                        hide_index=True,
                    )

                with st.expander(f"Match {away_team.strip()}"):
                    st.dataframe(
                        away_stats["details"],
                        use_container_width=True,
                        hide_index=True,
                    )

                st.subheader("🚩 Kònè")
                st.info(
                    "Sous done aktyèl la pa bay estatistik kònè pou analiz sa a. "
                    "Nou bezwen yon sous API ki gen done kònè anvan nou ka "
                    "kalkile pousantaj kònè yo."
                )

        except requests.exceptions.Timeout:
            st.error("API a pran twòp tan pou reponn. Eseye ankò.")

        except requests.exceptions.ConnectionError:
            st.error("Verifye koneksyon entènèt ou.")

        except ValueError as error:
            st.error(str(error))

        except requests.exceptions.HTTPError as error:
            st.error(f"Erè API: {error}")

        except Exception as error:
            st.error(f"Yon erè rive: {error}")

else:
    st.info(
        "Chwazi lig la, antre non ekip yo ak kle API ou, "
        "epi peze ANALIZE MATCH LA."
    )

import unicodedata
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

st.set_page_config(page_title="Football Analyzer", page_icon="⚽", layout="wide")

st.title("⚽ Football Analyzer")
st.caption("Analiz edikatif sou rezilta foutbòl. Prediksyon yo pa garanti.")

API_BASE = "https://api.football-data.org/v4"

LEAGUES = {
    "Premier League": "PL",
    "Champions League": "CL",
    "Europa League": "EL",
    "Bundesliga": "BL1",
    "La Liga": "PD",
    "Serie A": "SA",
    "Ligue 1": "FL1",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
}


def normalize_name(name):
    name = str(name or "").lower().strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(
        char for char in name
        if not unicodedata.combining(char)
    )
    return " ".join(name.split())


def same_team(search_name, api_name):
    target = normalize_name(search_name)
    actual = normalize_name(api_name)

    if not target or not actual:
        return False

    return target == actual or target in actual or actual in target


@st.cache_data(ttl=300)
def get_finished_matches(api_key, league_code):
    url = f"{API_BASE}/competitions/{league_code}/matches"
    headers = {"X-Auth-Token": api_key.strip()}

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=365)

    params = {
        "dateFrom": start_date.isoformat(),
        "dateTo": today.isoformat(),
        "status": "FINISHED",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=25,
    )

    if response.status_code == 401:
        raise ValueError("Kle API a pa kòrèk. Verifye kle ou a.")

    if response.status_code == 403:
        raise ValueError(
            "API a pa bay kont ou aksè ak konpetisyon sa a. "
            "Verifye plan API ou a."
        )

    if response.status_code == 429:
        raise ValueError(
            "Ou depase limit demann API a. Tann yon ti moman."
        )

    response.raise_for_status()

    matches = response.json().get("matches", [])
    finished = []

    for match in matches:
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")

        if (
            match.get("status") == "FINISHED"
            and home_goals is not None
            and away_goals is not None
        ):
            finished.append(match)

    return finished


def find_team_matches(team_name, matches):
    found = []

    for match in matches:
        home_name = match.get("homeTeam", {}).get("name", "")
        away_name = match.get("awayTeam", {}).get("name", "")

        if same_team(team_name, home_name) or same_team(team_name, away_name):
            found.append(match)

    found.sort(
        key=lambda match: match.get("utcDate", ""),
        reverse=True,
    )

    return found[:5]


def team_statistics(team_name, matches):
    scored = []
    conceded = []
    details = []

    for match in matches:
        home_name = match.get("homeTeam", {}).get("name", "")
        away_name = match.get("awayTeam", {}).get("name", "")

        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")

        if home_goals is None or away_goals is None:
            continue

        if same_team(team_name, home_name):
            gf = home_goals
            ga = away_goals
        elif same_team(team_name, away_name):
            gf = away_goals
            ga = home_goals
        else:
            continue

        scored.append(gf)
        conceded.append(ga)

        details.append({
            "Dat": match.get("utcDate", "")[:10],
            "Match": f"{home_name} vs {away_name}",
            "Score": f"{home_goals} - {away_goals}",
            "Gòl ekip la make": gf,
            "Gòl ekip la pran": ga,
        })

    if not scored:
        return None

    return {
        "played": len(scored),
        "scored": sum(scored) / len(scored),
        "conceded": sum(conceded) / len(conceded),
        "details": details,
    }


with st.sidebar:
    st.header("⚙️ Paramèt")

    api_key = st.text_input(
        "Football-Data.org API Token",
        type="password",
        help="Pa pataje kle API ou piblikman.",
    )

    league_name = st.selectbox(
        "Chwazi konpetisyon an",
        list(LEAGUES.keys()),
        key="league_select",
    )

col1, col2 = st.columns(2)

with col1:
    home_team = st.text_input(
        "Ekip lakay",
        placeholder="Egzanp: Arsenal",
    )

with col2:
    away_team = st.text_input(
        "Ekip deyò",
        placeholder="Egzanp: Chelsea",
    )

analyze = st.button(
    "🔍 Analize match la",
    type="primary",
    use_container_width=True,
    key="analyze_match_button",
)

if analyze:
    if not api_key.strip():
        st.error("Antre kle API ou nan meni agoch la.")

    elif not home_team.strip() or not away_team.strip():
        st.error("Antre non toude ekip yo.")

    elif same_team(home_team, away_team):
        st.error("Chwazi de ekip diferan.")

    else:
        try:
            with st.spinner("Ap chèche rezilta istorik yo..."):
                matches = get_finished_matches(
                    api_key,
                    LEAGUES[league_name],
                )

                home_matches = find_team_matches(home_team, matches)
                away_matches = find_team_matches(away_team, matches)

                home_stats = team_statistics(home_team, home_matches)
                away_stats = team_statistics(away_team, away_matches)

            st.caption(
                f"Konpetisyon: {league_name} | "
                f"Match fini jwenn nan API a: {len(matches)}"
            )

            if home_stats is None or away_stats is None:
                st.warning(
                    "Nou pa jwenn ase done pou youn oswa toude ekip yo. "
                    "Verifye non ekip yo, konpetisyon an ak aksè API a."
                )

            else:
                st.subheader(f"{home_team.strip()} vs {away_team.strip()}")

                left, right = st.columns(2)

                with left:
                    st.markdown(f"### 🏠 {home_team.strip()}")
                    st.metric("Match analize", home_stats["played"])
                    st.metric("Mwayèn gòl make", f'{home_stats["scored"]:.2f}')
                    st.metric("Mwayèn gòl pran", f'{home_stats["conceded"]:.2f}')

                with right:
                    st.markdown(f"### ✈️ {away_team.strip()}")
                    st.metric("Match analize", away_stats["played"])
                    st.metric("Mwayèn gòl make", f'{away_stats["scored"]:.2f}')
                    st.metric("Mwayèn gòl pran", f'{away_stats["conceded"]:.2f}')

                expected_home = (
                    home_stats["scored"] + away_stats["conceded"]
                ) / 2

                expected_away = (
                    away_stats["scored"] + home_stats["conceded"]
                ) / 2

                predicted_home = max(0, int(expected_home + 0.5))
                predicted_away = max(0, int(expected_away + 0.5))

                st.divider()
                st.subheader("📊 Estimasyon match la")

                p1, p2, p3 = st.columns(3)

                with p1:
                    st.metric(
                        f"Gòl estime: {home_team.strip()}",
                        f"{expected_home:.2f}",
                    )

                with p2:
                    st.metric(
                        f"Gòl estime: {away_team.strip()}",
                        f"{expected_away:.2f}",
                    )

                with p3:
                    st.metric(
                        "Nòt posib",
                        f"{predicted_home} - {predicted_away}",
                    )

                if expected_home > expected_away + 0.25:
                    st.info(
                        f"Mwayèn yo favorize {home_team.strip()}."
                    )
                elif expected_away > expected_home + 0.25:
                    st.info(
                        f"Mwayèn yo favorize {away_team.strip()}."
                    )
                else:
                    st.info(
                        "Mwayèn yo montre yon match ki sanble sere."
                    )

                st.warning(
                    "Sa yo se estimasyon senp ki baze sou match istorik "
                    "ki disponib yo. Yo pa garanti rezilta match la."
                )

                st.divider()
                st.subheader("🗂️ Dènye match yo")

                st.markdown(f"**{home_team.strip()}**")
                st.dataframe(
                    home_stats["details"],
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown(f"**{away_team.strip()}**")
                st.dataframe(
                    away_stats["details"],
                    use_container_width=True,
                    hide_index=True,
                )

                st.divider()
                st.subheader("🚩 Estatistik kònè")
                st.info(
                    "Done kònè yo pa disponib nan done API sa a. "
                    "Aplikasyon an pa envante chif kònè."
                )

        except requests.exceptions.Timeout:
            st.error(
                "Demann API a pran twòp tan. Verifye entènèt ou."
            )

        except requests.exceptions.ConnectionError:
            st.error(
                "Pa gen koneksyon ak API a. Verifye entènèt ou."
            )

        except ValueError as error:
            st.error(str(error))

        except requests.exceptions.HTTPError as error:
            st.error(f"API a retounen yon erè HTTP: {error}")

        except Exception as error:
            st.error(f"Yon erè inatandi rive: {error}")

else:
    st.info(
        "Antre kle API ou, chwazi konpetisyon an, antre non de ekip "
        "yo epi klike sou Analize match la."
    )

