from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional


class TournamentGroup(BaseModel):
    name: str = Field(..., description="Group name, e.g. 'A'")
    teams: List[str] = Field(..., min_length=4, max_length=4, description="List of 4 team names in the group")


class TournamentSimulationRequest(BaseModel):
    groups: Optional[List[TournamentGroup]] = Field(
        None,
        description=(
            "List of groups with custom teams. Required unless use_fifa_2026_groups is true, "
            "in which case the official FIFA World Cup 2026 groups are used instead and this "
            "field is ignored."
        ),
    )
    use_fifa_2026_groups: bool = Field(
        False,
        description=(
            "If true, simulate using the official FIFA World Cup 2026 groups (48 teams, "
            "groups A-L) loaded from reference data instead of the client-submitted 'groups' field."
        ),
    )
    n_simulations: int = Field(10000, ge=100, le=100000, description="Number of Monte Carlo simulations to run")
    use_real_results: bool = Field(
        True,
        description=(
            "If true (default), matchups already played in the real, in-progress 2026 tournament "
            "(per matches_historical.csv) use their real recorded score instead of being simulated; "
            "matches not yet played are always genuinely Monte Carlo simulated regardless of this "
            "flag. Only meaningful when use_fifa_2026_groups is true (custom team labels can never "
            "match a real fixture); set false to simulate the full FIFA 2026 bracket hypothetically "
            "from a blank slate."
        ),
    )

    @model_validator(mode="after")
    def _validate_groups(self) -> "TournamentSimulationRequest":
        if self.use_fifa_2026_groups:
            return self

        if not self.groups:
            raise ValueError("groups must be provided unless use_fifa_2026_groups is true")

        all_teams = [team for group in self.groups for team in group.teams]

        if len(all_teams) != 48:
            raise ValueError(f"Total teams across all groups must equal 48, found {len(all_teams)}")

        seen = set()
        duplicates = set()
        for team in all_teams:
            if team in seen:
                duplicates.add(team)
            seen.add(team)
        if duplicates:
            raise ValueError(f"Duplicate team name(s) found across groups: {sorted(duplicates)}")

        return self


class TeamTournamentStats(BaseModel):
    group: float = Field(..., description="Probability of playing in group stage (always 1.0)")
    r32: float = Field(..., description="Probability of reaching Round of 32")
    r16: float = Field(..., description="Probability of reaching Round of 16")
    qf: float = Field(..., description="Probability of reaching Quarter Finals")
    sf: float = Field(..., description="Probability of reaching Semi Finals")
    third_place: float = Field(..., description="Probability of reaching Third Place Match")
    final: float = Field(..., description="Probability of reaching Final")
    winner: float = Field(..., description="Probability of winning the tournament")


class TournamentSimulationResponse(BaseModel):
    probabilities: Dict[str, TeamTournamentStats] = Field(..., description="Dictionary mapping team names to their tournament probabilities")


class Fifa2026Team(BaseModel):
    code: str = Field(..., description="3-letter FIFA team code, e.g. 'MEX'")
    name: str = Field(..., description="Full country name, e.g. 'Mexico'")


class Fifa2026Group(BaseModel):
    name: str = Field(..., description="Group name, e.g. 'A'")
    teams: List[Fifa2026Team] = Field(..., description="The 4 teams in this group")


class Fifa2026GroupsResponse(BaseModel):
    groups: List[Fifa2026Group] = Field(..., description="The official 12 FIFA World Cup 2026 groups (48 teams)")


class Fifa2026Match(BaseModel):
    match_number: int = Field(..., description="Match number (1-104)")
    date: str = Field(..., description="Match date, ISO format (YYYY-MM-DD)")
    kickoff_time_et: str = Field(..., description="Kickoff time in Eastern Time, as printed on the official schedule")
    venue_city: str = Field(..., description="Host city (stadium names are not published)")
    stage: str = Field(..., description="One of: group_stage, round_of_32, round_of_16, quarter_final, semi_final, third_place, final")
    group: Optional[str] = Field(None, description="Group letter, only set for group_stage matches")
    home_team: str = Field(..., description="Team code, or a placeholder like 'W53'/'L101' for undetermined knockout participants")
    away_team: str = Field(..., description="Team code, or a placeholder like 'W53'/'L101' for undetermined knockout participants")
    uncertain: bool = Field(..., description="True if this fixture's details are inferred rather than read directly from the source chart")


class Fifa2026ScheduleResponse(BaseModel):
    matches: List[Fifa2026Match] = Field(..., description="Official FIFA World Cup 2026 fixtures (optionally filtered)")
