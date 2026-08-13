"""
Matches an API-Football fixture to its Sportmonks equivalent.

The two providers don't share fixture IDs, so matching is done on
date + team names. Team names can differ slightly between providers
(e.g. "Manchester United" vs "Man United"), so this uses a manual
alias map plus a fuzzy-match fallback.

If you hit persistent mismatches for specific teams once this runs
for real, add them to TEAM_ALIASES below rather than relying on fuzzy
matching alone - it's more reliable long-term.
"""

import re
import unicodedata

# Add entries as: "sportmonks_name": "api_football_name"
# Populate this as real mismatches turn up during testing - this is the
# most reliable long-term fix for any team that the automatic matching
# below keeps getting wrong.
TEAM_ALIASES = {
    # "man utd": "manchester united",
    # "spurs": "tottenham",
}

# Common suffixes/prefixes that differ between providers but don't help
# distinguish one club from another - strip these before comparing.
NOISE_WORDS = {"fc", "cf", "afc", "united", "city", "town", "hotspur", "athletic"}

# Common shorthand -> full word, applied per-token before comparison.
# Extend this if you spot other recurring abbreviations during testing.
WORD_ALIASES = {
    "man": "manchester",
    "utd": "united",
    "spurs": "tottenham",
    "wolves": "wolverhampton",
    "brighton": "brighton",
}


def normalize(name: str) -> str:
    if not name:
        return ""
    name = name.strip().lower()
    name = TEAM_ALIASES.get(name, name)
    # Transliterate accented characters (e.g. "Alavés" -> "Alaves") before
    # stripping non-alphanumerics, since API-Football and Sportmonks don't
    # consistently agree on accents for the same club.
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    # Word separators (e.g. "Saint-Etienne") must become spaces, not vanish -
    # stripping them outright would mash "Saint-Etienne" into "saintetienne"
    # while the other provider's "Saint Etienne" stays two tokens.
    name = re.sub(r"[-_/]", " ", name)
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _tokens(name: str) -> set[str]:
    raw_tokens = normalize(name).split()
    return {WORD_ALIASES.get(t, t) for t in raw_tokens}


def _team_score(name_a: str, name_b: str) -> float:
    """
    Token-overlap based similarity, robust to abbreviations like
    "Man United" vs "Manchester United" and suffix differences like
    "Tottenham" vs "Tottenham Hotspur".

    1.0  = exact match after normalization
    0.85 = one name's core tokens are a subset of the other's
    else = Jaccard overlap of remaining "identity" tokens (noise words
           like "united"/"city" excluded, since two different clubs can
           both be "* United")
    """
    a, b = normalize(name_a), normalize(name_b)
    if a == b:
        return 1.0

    tokens_a, tokens_b = _tokens(name_a), _tokens(name_b)
    if not tokens_a or not tokens_b:
        return 0.0

    # Substring containment (handles "Tottenham" vs "Tottenham Hotspur")
    if a in b or b in a:
        return 0.85

    # Identity tokens = words that aren't generic club-name noise
    identity_a = tokens_a - NOISE_WORDS or tokens_a
    identity_b = tokens_b - NOISE_WORDS or tokens_b

    overlap = identity_a & identity_b
    union = identity_a | identity_b
    if not union:
        return 0.0
    return len(overlap) / len(union)


def find_match(af_fixture: dict, sm_fixtures: list[dict]) -> dict | None:
    """
    Given one API-Football fixture and a list of Sportmonks fixtures for
    the same date, find the best match by team name similarity.
    Returns the matching Sportmonks fixture dict, or None if no good match.
    """
    af_home = af_fixture["home_team"]
    af_away = af_fixture["away_team"]

    best_match = None
    best_score = 0.0

    for sm in sm_fixtures:
        home_score = _team_score(af_home, sm["home_team"])
        away_score = _team_score(af_away, sm["away_team"])
        combined = (home_score + away_score) / 2

        if combined > best_score:
            best_score = combined
            best_match = sm

    # 0.6 works well with token-overlap scoring since identity-word
    # matches score cleanly (e.g. "tottenham" == "tottenham" -> 1.0
    # even inside "tottenham hotspur"). Tighten if you see false
    # positives during the backfill run; log unmatched pairs to tune.
    if best_score >= 0.6:
        return best_match
    return None
