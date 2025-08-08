import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# 별칭 → 표준 키
VALORANT_LEAGUE_ALIAS = {
    "masters":  "masters", "MASTER": "masters", "마스터스": "masters",
    "emea": "emea", "EMEA": "emea",
    "pacific": "pacific", "PACIFIC": "pacific", "퍼시픽": "pacific",
    "americas": "americas", "AMERICAS": "americas", "아메리카": "americas",
    "na": "na", "NA": "na",
    "japan": "japan", "JP": "japan",
    "brazil": "brazil", "BR": "brazil",
}

# 표준 키 → 실제 ID 목록
VALORANT_LEAGUE_IDS = {
    "masters":  ["608", "581"],
    "emea":     ["624", "607", "585", "580", "564"],
    "pacific":  ["622", "590", "566"],
    "na":       ["601"],
    "americas": ["625", "584", "565"],
    "japan":    ["623"],
    "brazil":   ["633"],
}

async def fetch_opgg_lol_schedule(league_id: str, year: int, month: int):
    """OP.GG GraphQL: LoL 리그 일정 조회.

    `ListPagedAllMatches` 쿼리를 통해 OP.GG에서 특정 리그/연월의 경기를
    조회합니다. 타임존 보정은 서버 쿼리 변수의 `utcOffset`(분 단위)로 전달합니다.

    Args:
        league_id: OP.GG 리그 ID 문자열. 예) "98"(LPL), "99"(LCK).
        year: 조회 연도. 예) 2025.
        month: 조회 월(1-12).

    Returns:
        dict | None: 성공 시 원본 GraphQL JSON. 실패 시 `None`.
    """
    url = 'https://esports.op.gg/matches/graphql/__query__ListPagedAllMatches'

    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'origin': 'https://esports.op.gg',
        'referer': 'https://esports.op.gg/schedules/lpl',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

        # 전체 GraphQL 쿼리 문자열
    query = """fragment CoreTeam on Team {
    id
    name
    acronym
    imageUrl
    nationality
    foundedAt
    imageUrlDarkMode
    imageUrlLightMode
    youtube
    twitter
    facebook
    instagram
    discord
    website
    __typename
    }

    fragment CoreMatchCompact on Match {
    id
    tournamentId
    name
    scheduledAt
    beginAt
    matchType
    homeTeamId
    homeTeam {
        ...CoreTeam
        __typename
    }
    homeScore
    awayTeamId
    awayTeam {
        ...CoreTeam
        __typename
    }
    awayScore
    winnerTeam {
        ...CoreTeam
        __typename
    }
    status
    draw
    forfeit
    matchVersion
    __typename
    }

    fragment CoreTournament on Tournament {
    id
    name
    beginAt
    endAt
    __typename
    }

    query ListPagedAllMatches($status: String, $leagueId: ID, $teamId: ID, $page: Int, $year: Int, $month: Int, $limit: Int, $utcOffset: Int) {
    pagedAllMatches(
        status: $status
        leagueId: $leagueId
        teamId: $teamId
        page: $page
        year: $year
        month: $month
        limit: $limit
        utcOffset: $utcOffset
    ) {
        ...CoreMatchCompact
        tournament {
        ...CoreTournament
        serie {
            league {
            shortName
            region
            __typename
            }
            year
            season
            __typename
        }
        __typename
        }
        __typename
    }
    }"""

    data = {
        "operationName": "ListPagedAllMatches",
        "variables": {
            "leagueId": league_id,
            "year": year,
            "month": month,
            "teamId": None,
            "utcOffset": 540,
            "page": 0
        },
        "query": query
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                print(f"❌ 롤 일정 크롤링 실패: {response.status}")
                print(f"응답 내용: {response_text}")
                return None


def parse_opgg_matches_list(opgg_response: dict) -> list[dict]:
    """OP.GG GraphQL 응답에서 경기 리스트를 납작한 구조로 파싱.

    홈/원정 팀 정보가 누락된 경우에도 예외 없이 빈 문자열/빈 값으로 보정합니다.

    Args:
        opgg_response: `ListPagedAllMatches` GraphQL 응답 딕셔너리.

    Returns:
        list[dict]: 각 경기마다 다음 키를 포함
            - matchId, startDate, status(BEFORE/STARTED/END),
              team1/2, team1Img/2Img, score1/2
    """
    if not opgg_response or not opgg_response.get("data"):
        return []

    matches = opgg_response.get("data", {}).get("pagedAllMatches") or []
    if not isinstance(matches, list):
        return []

    # 상태 매핑
    status_map = {
        "not_started": "BEFORE",
        "running": "STARTED", 
        "finished": "END"
    }
    
    parsed_matches = []
    for match in matches:
        if not isinstance(match, dict):
            continue

        home_team = match.get("homeTeam") or {}
        away_team = match.get("awayTeam") or {}

        team1 = home_team.get("acronym") or home_team.get("name") or ""
        team2 = away_team.get("acronym") or away_team.get("name") or ""

        team1_img = (
            home_team.get("imageUrl")
            or home_team.get("imageUrlLightMode")
            or home_team.get("imageUrlDarkMode")
            or ""
        )
        team2_img = (
            away_team.get("imageUrl")
            or away_team.get("imageUrlLightMode")
            or away_team.get("imageUrlDarkMode")
            or ""
        )

        parsed_matches.append(
            {
                "matchId": match.get("id"),
                "startDate": match.get("scheduledAt"),
                "status": status_map.get(match.get("status"), match.get("status")),
                "team1": team1,
                "team2": team2,
                "team1Img": team1_img,
                "team2Img": team2_img,
                "score1": match.get("homeScore"),
                "score2": match.get("awayScore"),
            }
        )

    return parsed_matches


async def fetch_valorant_league_schedule(league_input: str):
    """OP.GG Valorant: 별칭 기반 시리즈들에 대한 30일 범위 경기 조회.

    사용자 입력 별칭을 표준 키로 정규화한 뒤, 해당 표준 키에 매핑된 시리즈 ID 목록을
    사용하여 오늘부터 30일 범위의 경기를 조회합니다. 결과는 KST로 변환해 반환합니다.

    Args:
        league_input: 리그 별칭(예: "퍼시픽", "PACIFIC", "masters", "EMEA").

    Returns:
        list[dict] | None: 경기 리스트(각 경기의 시작 시간이 KST ISO 형식). 없으면 `None`.
    """
    # 1. 입력받은 별칭(league_input)으로 표준 키 찾기
    standard_key = VALORANT_LEAGUE_ALIAS.get(league_input.lower())
    if not standard_key:
        # 오류 메시지에서 원래 입력값(league_input)을 사용하도록 수정
        print(f"'{league_input}'에 해당하는 리그를 찾을 수 없습니다.")
        return None
    
    # 2. 찾은 표준 키로 실제 ID 목록 찾기
    serieIds_list = VALORANT_LEAGUE_IDS.get(standard_key)
    if not serieIds_list:
        print(f"오류: 표준 키 '{standard_key}'에 대한 ID 목록을 찾을 수 없습니다.")
        return None
    
    # 3. UTC 기준으로 오늘 ~ 30일 이후 날짜 구하기
    utc_now = datetime.now(timezone.utc)
    from_date_str = utc_now.strftime("%Y-%m-%d")
    to_date_str = (utc_now + timedelta(days=30)).strftime("%Y-%m-%d")
    
    url = "https://esports.op.gg/valorant/graphql/__query__GetMatchesBySeries"
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'origin': 'https://esports.op.gg',
        'referer': 'https://esports.op.gg/valorant',
    }

    query = """
        fragment CoreTeam on Team { id name acronym imageUrl nationality __typename }
        fragment CoreValorantMatchCompact on Match {
            id tournamentId name scheduledAt beginAt matchType
            homeTeamId homeTeam { ...CoreTeam __typename } homeScore
            awayTeamId awayTeam { ...CoreTeam __typename } awayScore
            winnerTeam { ...CoreTeam __typename }
            status draw forfeit matchVersion __typename
        }
        query GetMatchesBySeries($serieIds: [ID]!, $from: Date, $to: Date, $teamId: ID) {
            matchesBySeries(serieIds: $serieIds, from: $from, to: $to, teamId: $teamId) {
                ...CoreValorantMatchCompact serieId __typename
            }
        }
    """
    payload = {
        "operationName": "GetMatchesBySeries",
        "variables": { "serieIds": serieIds_list, "from": from_date_str, "to": to_date_str },
        "query": query
    }

    # 4. 요청 보내기
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()

                matches = data.get('data', {}).get('matchesBySeries')
                if not matches:
                    return None
                
                sorted_matches = sorted(matches, key=lambda x: x.get('scheduledAt'))

                KST = ZoneInfo("Asia/Seoul")

                status_map = {
                    "not_started": "BEFORE",
                    "running": "STARTED",
                    "finished": "END"
                }

                matches_list = []
                for match in sorted_matches:
                    utc_time = datetime.fromisoformat(match.get('scheduledAt').replace('Z', '+00:00'))
                    kst_time = utc_time.astimezone(KST)

                    valorant_match = {
                        "matchId": match.get("id"),
                        "startDate": kst_time.isoformat(),
                        "status": status_map.get(match.get("status"), match.get("status")),
                        "leagueName": None,
                        "blockName": None,
                        "team1": match.get("homeTeam", {}).get("name"),
                        "team2": match.get("awayTeam", {}).get("name"),
                        "team1Img": match.get("homeTeam", {}).get("imageUrl"),
                        "team2Img": match.get("awayTeam", {}).get("imageUrl"),
                        "score1": match.get("homeScore"),
                        "score2": match.get("awayScore"),
                    }
                    matches_list.append(valorant_match)

                return matches_list

            else:
                print(f"❌ 발로란트 일정 크롤링 실패: {response.status}")
                return None
            

if __name__ == "__main__":
    print(asyncio.run(fetch_opgg_lol_schedule("98", 2025, 9)))