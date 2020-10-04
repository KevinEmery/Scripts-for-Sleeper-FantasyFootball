# Dependencies:
#   sleeper-api-wrapper, https://pypi.org/project/sleeper-api-wrapper/
#       Used to facilitate all Sleeper API requests

from sleeper_wrapper import League, User
from typing import Callable, List

import argparse
import sys

# Map storing the user id and username, to avoid multiple server calls for
# the same information
user_id_to_username = {}


class WeeklyScore:
    """Contains basic information about a specific users single-week score

    Attributes
    ----------
    username : str
        Sleeper username
    league_name : str
        Official name of the league in Sleeper
    week : str
        The week in which the score occured
    points : str
        The total number of points the user has for the given week
    """
    def __init__(self, username: str, league_name: str, week: int,
                 points: int):
        self.username = username
        self.league_name = league_name
        self.week = week
        self.points = points

    def __str__(self):
        try:
            template = "{username:.<20}{points:06.2f}, Week {week} ({league_name})"
            return template.format(league_name=self.league_name,
                                   username=self.username,
                                   week=self.week,
                                   points=self.points)
        except:
            # In exceptional cases there may be an empty object here, with one
            # observed example being test leagues with no schedule. In those cases
            # just return empty string.
            return ""


class SeasonScore:
    """Contains basic information about a specific users season-long score

    Attributes
    ----------
    username : str
        Sleeper username
    league_name : str
        Official name of the league in Sleeper
    points_for : str
        The total number of points the user has scored this year
    """
    def __init__(self, username: str, league_name: str, points_for: int):
        self.username = username
        self.league_name = league_name
        self.points_for = points_for

    def __str__(self):
        template = "{username:.<20}{points_for:06.2f} ({league_name})"
        return template.format(league_name=self.league_name,
                               username=self.username,
                               points_for=self.points_for)


def add_users_to_user_map(users: List[User]):
    for user in users:
        user_id_to_username[user.get("user_id")] = user.get("display_name")


def get_username_from_user_id(user_id: str) -> str:
    try:
        return user_id_to_username[user_id]
    except KeyError:
        print("Error retrieving user: " + str(user_id))
        return "No User"


def is_league_inactive(rosters) -> bool:
    """Determines if a league is inactive based on the rosters

    This is used as a mildly hacky helper method. It looks through the
    rosters of every time, and if there are any players on any of them
    it classifies the league as active. However if all the player
    lists are empty, it says the league is inactive and returns True

    """
    for roster in rosters:
        if roster.get("players"):
            return False

    return True


def get_weekly_scores_for_league_and_week(league: League,
                                          week: int) -> List[WeeklyScore]:
    """Retrieves all of the weekly scores for the league in a given week

    This parses through all of the league matchups, transforming the API
    matchup and roster objects into a WeeklyScore report that can be parsed
    later on

    Parameters
    ----------
    league : League
        The League object being analyzed
    week : int
        The week for which to pull matchups

    Returns
    -------
    List[WeeklyScore]
        A list of the individual weekly scores
    """
    rosters = league.get_rosters()

    # Short circuit to avoid problems if the league is empty
    if is_league_inactive(rosters):
        return []

    roster_id_to_username = {}
    weekly_scores = []

    # Create a mapping of the roster id to the username
    for roster in rosters:
        roster_id_to_username[roster.get(
            "roster_id")] = get_username_from_user_id(roster.get("owner_id"))

    # Each "matchup" represents a single teams performance
    weekly_matchups = league.get_matchups(week)
    for matchup in weekly_matchups:
        weekly_scores.append(
            WeeklyScore(roster_id_to_username[matchup.get("roster_id")],
                        league.get_league().get("name"), week,
                        matchup.get("points")))

    return weekly_scores


def get_pf_for_entire_league(league: League) -> List[SeasonScore]:
    """Retrieves all of the season scores for the league

    This parses through all of the league rosters, trasnforming what's
    available on the roster object into a SeasonScore object for each team

    Parameters
    ----------
    league : League
        The League object being analyzed

    Returns
    -------
    List[SeasonScore]
        A list of the Season-long scores for each team in the league
    """
    rosters = league.get_rosters()

    # Short circuit to avoid problems if the league is empty
    if is_league_inactive(rosters):
        return []

    season_scores = []

    for roster in rosters:
        total_points_for = float(roster.get("settings").get("fpts"))
        try:
            total_points_for += float(
                roster.get("settings").get("fpts_decimal")) / 100
        except Exception:
            # Decimal field may not be pressent, skip
            total_points_for += 0.00

        season_scores.append(
            SeasonScore(get_username_from_user_id(roster.get("owner_id")),
                        league.get_league().get("name"), total_points_for))

    return season_scores


def print_non_empty_list_with_header(list: list, header_text: str, count: int):
    """Prints out the provided list with a single-line header

    This serves as a uniform way to display the output tables. Nothing will
    display if the list is empty, and the length is capped by the size of
    the list or by count, whichever is smaller.

    Parameters
    ----------
    list : list
        The list set to be printed out
    header_text : str
        The single-line header for the provided list
    count : int
        The maximum number of items to be returned
    """

    if not list:
        return

    print(header_text)
    for i in range(0, count):
        if i < len(list):
            print(list[i])
        else:
            break
    print("")


def parse_user_provided_flags() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "-wc",
        "--weekly_count",
        help="number of weekly data points to display (default: 5)",
        type=int,
        default=5)
    parser.add_argument(
        "-sc",
        "--season_count",
        help="number of season data points to display (default: 5)",
        type=int,
        default=5)
    parser.add_argument("-y",
                        "--year",
                        help="year to run the analysis on",
                        type=int,
                        default=2020)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--max",
                       dest="max",
                       action="store_true",
                       help="Include the 'max' statistics (default)")
    group.add_argument("--no-max", dest="max", action="store_false")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--min",
                       dest="min",
                       action="store_true",
                       help="Include the 'min' statistics (default)")
    group.add_argument("--no-min", dest="min", action="store_false")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--season",
                       dest="season",
                       action="store_true",
                       help="Include the 'season' statistics (default)")
    group.add_argument("--no-season", dest="season", action="store_false")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--weekly",
                       dest="weekly",
                       action="store_true",
                       help="Include the 'weekly' statistics (default)")
    group.add_argument("--no-weekly", dest="weekly", action="store_false")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--current-week",
                       dest="current_week",
                       action="store_true",
                       help="Include the 'current week' statistics (default)")
    group.add_argument("--no-current-week",
                       dest="current_week",
                       action="store_false")
    parser.add_argument("username",
                        help="User account used to pull all of the leagues",
                        type=str)
    parser.add_argument(
        "start",
        help="the starting week for data collection (default: 1)",
        type=int,
        default=1,
        nargs='?')
    parser.add_argument("end",
                        help="the ending week for data collection",
                        type=int)

    parser.set_defaults(max=True,
                        min=True,
                        season=True,
                        weekly=True,
                        current_week=True)

    return parser.parse_args()


def main(argv):
    # Parse all of the user-provided flags
    args = parse_user_provided_flags()

    # Convert the computed args into our more-verbose local fields
    account_username = args.username
    league_year = args.year
    starting_week = args.start
    ending_week = args.end
    weekly_score_output_count = args.weekly_count
    seasonal_score_output_count = args.season_count
    find_weekly = args.weekly
    print_max_this_week = args.weekly and args.max and args.current_week
    print_min_this_week = args.weekly and args.min and args.current_week
    print_max_weekly = args.weekly and args.max
    print_min_weekly = args.weekly and args.min
    find_seasonal = args.season
    print_max_seasonal = args.season and args.max
    print_min_seasonal = args.season and args.min

    # Lists containing all of the collated data
    weekly_scores = []
    seasonal_scores = []

    # Retrieve all of the leagues
    admin_user = User(account_username)
    all_leagues = admin_user.get_all_leagues("nfl", league_year)

    # Iterate over all the leagues in the account
    for league_object in all_leagues:
        league = League(league_object.get("league_id"))
        add_users_to_user_map(league.get_users())

        # Iterate over each indiviudal week, since we need to grab the max weekly score for the league
        if find_weekly:
            for week_num in range(starting_week, ending_week + 1):
                weekly_scores.extend(
                    get_weekly_scores_for_league_and_week(league, week_num))

        if find_seasonal:
            # Grab the points-for in each league
            seasonal_scores.extend(get_pf_for_entire_league(league))

    # Sublists used for sorted results
    max_weekly_scores = []
    min_weekly_scores = []
    max_scores_this_week = []
    min_scores_this_week = []
    max_seasonal_points_for = []
    min_seasonal_points_for = []

    # Sort all of the lists
    if find_seasonal:
        max_seasonal_points_for = seasonal_scores.copy()
        max_seasonal_points_for.sort(
            key=lambda annual_score: annual_score.points_for, reverse=True)
        min_seasonal_points_for = seasonal_scores.copy()
        min_seasonal_points_for.sort(
            key=lambda annual_score: annual_score.points_for)
    if find_weekly:
        max_weekly_scores = weekly_scores.copy()
        max_weekly_scores.sort(key=lambda weekly_score: weekly_score.points,
                               reverse=True)
        min_weekly_scores = weekly_scores.copy()
        min_weekly_scores.sort(key=lambda weekly_score: weekly_score.points)
        max_scores_this_week = list(
            filter(lambda weekly_score: weekly_score.week == ending_week,
                   max_weekly_scores.copy()))
        min_scores_this_week = list(
            filter(lambda weekly_score: weekly_score.week == ending_week,
                   min_weekly_scores.copy()))

    # Print out the results
    this_week_template = "{main_header}, Week {week_num}"
    if print_max_this_week:
        print_non_empty_list_with_header(
            max_scores_this_week,
            this_week_template.format(main_header="HIGHEST SCORES THIS WEEK",
                                      week_num=ending_week),
            weekly_score_output_count)
    if print_min_this_week:
        print_non_empty_list_with_header(
            min_scores_this_week,
            this_week_template.format(main_header="LOWEST SCORES THIS WEEK",
                                      week_num=ending_week),
            weekly_score_output_count)
    if print_max_weekly:
        print_non_empty_list_with_header(max_weekly_scores,
                                         "HIGHEST WEEKLY SCORES THIS SEASON",
                                         weekly_score_output_count)
    if print_min_weekly:
        print_non_empty_list_with_header(min_weekly_scores,
                                         "LOWEST WEEKLY SCORES THIS SEASON",
                                         weekly_score_output_count)
    if print_max_seasonal:
        print_non_empty_list_with_header(max_seasonal_points_for,
                                         "HIGHEST POINTS-FOR THIS SEASON",
                                         seasonal_score_output_count)
    if print_min_seasonal:
        print_non_empty_list_with_header(min_seasonal_points_for,
                                         "LOWEST POINTS-FOR THIS SEASON",
                                         seasonal_score_output_count)


if __name__ == "__main__":
    main(sys.argv[1:])