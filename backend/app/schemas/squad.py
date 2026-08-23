"""
Schemas for the WC2026 squad experience.

Every numeric field is Optional on purpose. players.csv populates a statistic
only when it genuinely exists -- 198 of the 1,248 squad members never took the
field, and 78 of the 136 goalkeepers have no goalkeeping columns. Serialising a
missing value as 0 would invent a fact, so absent stays absent and the client
renders "Not available".
"""

from typing import Optional

from pydantic import BaseModel, Field


class PlayerResponse(BaseModel):
    name: str
    team: str
    position: Optional[str] = None
    age: Optional[int] = None
    birth_year: Optional[int] = None
    club: Optional[str] = None
    is_goalkeeper: bool = False

    # Appearances
    games: Optional[int] = None
    games_starts: Optional[int] = None
    minutes: Optional[int] = None

    # Attacking
    goals: Optional[int] = None
    assists: Optional[int] = None
    shots: Optional[int] = None
    shots_on_target: Optional[int] = None
    goals_per90: Optional[float] = None
    assists_per90: Optional[float] = None

    # Creative / discipline
    crosses: Optional[int] = None
    fouled: Optional[int] = None
    offsides: Optional[int] = None
    cards_yellow: Optional[int] = None
    cards_red: Optional[int] = None

    # Defensive
    tackles_won: Optional[int] = None
    interceptions: Optional[int] = None
    fouls: Optional[int] = None

    # Goalkeeping — only ever set on goalkeepers who actually kept goal.
    gk_games: Optional[int] = None
    gk_minutes: Optional[int] = None
    gk_goals_against: Optional[int] = None
    gk_saves: Optional[int] = None
    gk_save_pct: Optional[float] = None
    gk_clean_sheets: Optional[int] = None
    gk_clean_sheets_pct: Optional[float] = None


class TeamSquadResponse(BaseModel):
    team: str
    fifa_code: Optional[str] = None
    wc2026_group: Optional[str] = None
    squad_size: int = Field(..., description="Players on record for this team")
    players_with_appearances: int = Field(
        ..., description="How many of them have at least one appearance"
    )
    captain: Optional[PlayerResponse] = Field(
        None,
        description=(
            "Captain of this team's most recent 2026 match, taken from the "
            "canonical match record. Null when unavailable — never guessed."
        ),
    )
    key_players: list[PlayerResponse] = Field(
        default_factory=list,
        description=(
            "The players the team profile leads with: the captain first, then "
            "the squad ranked by appearances, starts and goal contribution "
            "(saves and clean sheets for goalkeepers). The team's top goalkeeper "
            "is guaranteed a slot if one played, even when his raw ranking score "
            "would place him lower. Players with no appearances are excluded, so "
            "this can be shorter than the target of 8 rather than padded."
        ),
    )
    players: list[PlayerResponse]
    total_goals: int
    total_assists: int
    total_minutes: int
