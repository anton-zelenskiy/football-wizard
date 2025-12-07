from enum import Enum


DEFAULT_SEASON = 2025


class Country(str, Enum):
    ENGLAND = 'England'
    SPAIN = 'Spain'
    GERMANY = 'Germany'
    ITALY = 'Italy'
    FRANCE = 'France'
    NETHERLANDS = 'Netherlands'
    PORTUGAL = 'Portugal'
    RUSSIA = 'Russia'


class League(str, Enum):
    PREMIER_LEAGUE = 'Premier League'
    LA_LIGA = 'LaLiga'
    BUNDESLIGA = 'Bundesliga'
    SERIE_A = 'Serie A'
    LIGUE_1 = 'Ligue 1'
    EREDIVISIE = 'Eredivisie'
    PRIMEIRA_LIGA = 'Primeira Liga'
    RUSSIAN_PREMIER_LEAGUE = 'Premier League'
    FNL = 'FNL'


LEAGUES_OF_INTEREST = {
    Country.ENGLAND: (League.PREMIER_LEAGUE,),
    Country.SPAIN: (League.LA_LIGA,),
    Country.GERMANY: (League.BUNDESLIGA,),
    Country.ITALY: (League.SERIE_A,),
    Country.FRANCE: (League.LIGUE_1,),
    Country.NETHERLANDS: (League.EREDIVISIE,),
    Country.PORTUGAL: (League.PRIMEIRA_LIGA,),
    Country.RUSSIA: (League.RUSSIAN_PREMIER_LEAGUE, League.FNL),
}
