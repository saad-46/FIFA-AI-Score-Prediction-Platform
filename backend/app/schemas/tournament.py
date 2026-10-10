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
            "Only meaningful with use_fifa_2026_groups. False: a pre-tournament forecast -- all 104 "
            "matches simulated from information available before 11 June 2026. True (default): the "
            "real group-stage results are taken as given and the knockout rounds are simulated on the "
            "bracket they produced, with ratings as of the end of the group stage. Knockout results "
            "are never fed in; the finished tournament itself is served by the bracket endpoints."
        ),
    )
    seed: Optional[int] = Field(
        None, ge=0, le=2**32 - 1,
        description="Random seed. The same request with the same seed returns the same numbers. Omit for the default seed.",
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


class TournamentSimulationMeta(BaseModel):
    """What was simulated, with which model, from which information."""
    model_config = {"protected_namespaces": ()}

    engine: str = Field(..., description="'v3' or 'legacy'")
    mode: str = Field(..., description="pre_tournament | after_group_stage | custom_groups | legacy")
    model_version: str
    information_cutoff: Optional[str] = Field(None, description="No match on or after this date informs the forecast")
    data_through: Optional[str] = Field(None, description="Date of the most recent match used")
    n_simulations: int
    seed: Optional[int] = None
    fixed_matches: int = Field(0, description="Matches whose real result was taken as given")
    champion_probability_sum: Optional[float] = None
    max_champion_standard_error: Optional[float] = Field(
        None, description="Largest Monte Carlo standard error among the champion probabilities")
    knockout_resolution: Optional[Dict[str, int]] = Field(
        None, description="Simulated knockout ties decided in 90 minutes / extra time / penalties")
    tournament_status: Optional[str] = Field(
        None, description="'completed' for the 2026 World Cup, 'hypothetical' for custom groups")
    group_letters: Optional[Dict[str, str]] = Field(
        None, description="Custom group name -> bracket letter, when they differ")
    note: Optional[str] = None


class TournamentSimulationResponse(BaseModel):
    probabilities: Dict[str, TeamTournamentStats] = Field(..., description="Dictionary mapping team names to their tournament probabilities")
    meta: Optional[TournamentSimulationMeta] = Field(None, description="Provenance of this simulation")


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
