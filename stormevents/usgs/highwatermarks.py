from enum import Enum
from functools import lru_cache
from os import PathLike
import re
from typing import Any, Dict, Iterable, List

from matplotlib import pyplot
from matplotlib.axis import Axis
import pandas
import requests
from typepigeon import convert_value

from stormevents.nhc import nhc_storms
from stormevents.utilities import get_logger


class EventType(Enum):
    # TODO fill out other options
    HURRICANE = 2


class EventStatus(Enum):
    # TODO fill out other options
    COMPLETED = 0


class HWMType(Enum):
    # TODO fill out other options
    pass


class HWMQuality(Enum):
    # TODO fill out other options
    EXCELLENT = 1  # +/- 0.05 ft
    GOOD = 2  # +/- 0.10 ft
    FAIR = 3  # +/- 0.20 ft
    POOR = 4  # +/- 0.40 ft
    VERY_POOR = 5  # > 0.40 ft


class HWMEnvironment(Enum):
    # TODO fill out other options
    COASTAL = 'Coastal'
    RIVERINE = 'Riverine'


class HighWaterMarks:
    URL = 'https://stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json'

    def __init__(
        self,
        event_id: int,
        event_type: EventType,
        event_status: EventStatus = None,
        us_states: List[str] = None,
        us_counties: List[str] = None,
        hwm_type: HWMType = None,
        hwm_quality: HWMQuality = None,
        hwm_environment: HWMEnvironment = None,
        survey_completed: bool = True,
        still_water: bool = False,
    ):
        if event_status is None:
            event_status = EventStatus.COMPLETED
        if hwm_environment is None:
            hwm_environment = HWMEnvironment.RIVERINE

        self.event_id = event_id
        self.event_type = event_type
        self.event_status = event_status
        self.us_states = us_states
        self.us_counties = us_counties
        self.hwm_type = hwm_type
        self.hwm_quality = hwm_quality
        self.hwm_environment = hwm_environment
        self.survey_completed = survey_completed
        self.still_water = still_water

        self.__previous_query = self.query
        self.__data = None

    @property
    def event_type(self) -> EventType:
        return self.__event_type

    @event_type.setter
    def event_type(self, event_type: EventType):
        self.__event_type = convert_value(event_type, EventType)

    @property
    def hwm_quality(self) -> HWMQuality:
        return self.__hwm_quality

    @hwm_quality.setter
    def hwm_quality(self, hwm_quality: HWMQuality):
        self.__hwm_quality = convert_value(hwm_quality, HWMQuality)

    @property
    def hwm_type(self) -> HWMType:
        return self.__hwm_type

    @hwm_type.setter
    def hwm_type(self, hwm_type: HWMType):
        self.__hwm_type = convert_value(hwm_type, HWMType)

    @property
    def hwm_environment(self) -> HWMEnvironment:
        return self.__hwm_environment

    @hwm_environment.setter
    def hwm_environment(self, hwm_environment: HWMEnvironment):
        self.__hwm_environment = convert_value(hwm_environment, HWMEnvironment)

    @property
    def query(self) -> Dict[str, Any]:
        event_type = self.event_type
        if isinstance(event_type, Enum):
            event_type = event_type.value
        event_status = self.event_status
        if isinstance(event_status, Enum):
            event_status = event_status.value
        hwm_type = self.hwm_type
        if isinstance(hwm_type, Enum):
            hwm_type = hwm_type.value
        hwm_quality = self.hwm_quality
        if isinstance(hwm_quality, Enum):
            hwm_quality = hwm_quality.value
        hwm_environment = self.hwm_environment
        if isinstance(hwm_environment, Enum):
            hwm_environment = hwm_environment.value

        return {
            'Event': self.event_id,
            'EventType': event_type,
            'EventStatus': event_status,
            'States': self.us_states,
            'County': self.us_counties,
            'HWMType': hwm_type,
            'HWMQuality': hwm_quality,
            'HWMEnvironment': hwm_environment,
            'SurveyComplete': self.survey_completed,
            'StillWater': self.still_water,
        }

    @property
    def data(self) -> pandas.DataFrame:
        if self.__data is None or self.__previous_query != self.query:
            response = requests.get(self.URL, params=self.query)
            data = pandas.DataFrame(response.json())
            data.set_index('hwm_id', inplace=True)
            self.__data = data
            self.__previous_query = self.query
        return self.__data

    @data.setter
    def data(self, data: pandas.DataFrame):
        self.__data = data

    def plot(
        self, axis: Axis = None, show: bool = True, **kwargs,
    ):
        if axis is None:
            fig = pyplot.figure()
            axis = fig.add_subplot(111)

        for hwm_id, hwm in self.data.iterrows():
            axis.scatter(
                hwm['longitude'], hwm['latitude'], c=hwm['elev_ft'], **kwargs,
            )

        if show:
            pyplot.show()

        return axis

    @classmethod
    def from_name(
        cls,
        name: str,
        year: int = None,
        event_type: EventType = None,
        event_status: EventStatus = None,
    ) -> 'HighWaterMarks':
        events = usgs_highwatermark_events()
        events = events[events['usgs_name'] == name]
        if len(events) > 0:
            events = events[events['year'] == year]
        event = events[0]
        return cls(
            event_id=event['usgs_id'], event_type=event_type, event_status=event_status,
        )

    @classmethod
    def from_csv(
        cls,
        filename: PathLike,
        event_id: int = None,
        event_type: EventType = None,
        event_status: EventStatus = None,
    ) -> 'HighWaterMarks':
        data = pandas.read_csv(filename, index_col='hwm_id')
        instance = cls(event_id=event_id, event_type=event_type, event_status=event_status,)
        instance.data = data
        return instance

    def __eq__(self, other: 'HighWaterMarks') -> bool:
        return self.data.equals(other.data)


class StormHighWaterMarks(HighWaterMarks):
    def __init__(
        self,
        name: str,
        year: int,
        us_states: List[str] = None,
        us_counties: List[str] = None,
        hwm_type: HWMType = None,
        hwm_quality: HWMQuality = None,
        hwm_environment: HWMEnvironment = None,
        survey_completed: bool = True,
        still_water: bool = False,
    ):
        if hwm_environment is None:
            hwm_environment = HWMEnvironment.RIVERINE

        storms = usgs_highwatermark_storms(year=year)

        event_id = storms[
            (storms['nhc_name'] == name.upper()) & (storms['year'] == year)
        ].index[0]

        super().__init__(
            event_id=event_id,
            event_status=EventStatus.COMPLETED,
            event_type=EventType.HURRICANE,
            us_states=us_states,
            us_counties=us_counties,
            hwm_type=hwm_type,
            hwm_quality=hwm_quality,
            hwm_environment=hwm_environment,
            survey_completed=survey_completed,
            still_water=still_water,
        )


LOGGER = get_logger(__name__)


@lru_cache(maxsize=None)
def usgs_highwatermark_events(
    event_type: EventType = None, year: int = None, event_status: EventStatus = None,
) -> pandas.DataFrame:
    """
    this function collects all USGS flood events of the given type and status that have high water mark data

    USGS does not standardize event naming, and they should.
    Year, month, and storm type are not always included.
    The order in which the names are in the response is also not standardized.
    This function applies a workaround to fill in gaps in data.
    USGS should standardize their REST server data.

    :param event_type: type of USGS flood event
    :param year: year of event
    :param event_status: status of USGS flood event
    :return: table of flood events
    """

    if event_type is None:
        return pandas.concat(
            [usgs_highwatermark_events(event_type) for event_type in EventType]
        )

    if isinstance(event_type, Enum):
        event_type = event_type.value

    if isinstance(event_status, Enum):
        event_status = event_status.value

    response = requests.get(
        HighWaterMarks.URL,
        params={
            'Event': None,
            'EventType': event_type,
            'EventStatus': event_status,
            'States': None,
            'County': None,
            'HWMType': None,
            'HWMQuality': None,
            'HWMEnvironment': None,
            'SurveyComplete': None,
            'StillWater': None,
        },
    )

    LOGGER.info('building table of USGS high water mark survey events')

    data = response.json()

    events = {}
    for entry in data:
        event_id = entry['event_id']
        if event_id not in events or events[event_id][2] is None:
            name = entry['eventName']
            event = [event_id, name]
            if 'survey_date' in entry:
                event_year = int(entry['survey_date'].split('-')[0])
            elif 'flag_date' in entry:
                event_year = int(entry['flag_date'].split('-')[0])
            else:
                search = re.findall('\d{4}', name)
                if len(search) > 0:
                    event_year = int(search[0])
                else:
                    # otherwise, search the NHC database for the storm year
                    storms = nhc_storms()
                    storm_names = pandas.unique(storms['name'])
                    storm_names.sort()
                    for storm_name in storm_names:
                        if storm_name.lower() in name.lower():
                            years = storms[storms['name'] == storm_name]['year']
                            if len(years) == 1:
                                event_year = years[0]
                            else:
                                LOGGER.warning(
                                    f'could not find year of "{name}" in USGS high water mark database nor in NHC table'
                                )
                                event_year = None
                            break
                    else:
                        event_year = None
            event.append(event_year)
            events[event_id] = event

    events = pandas.DataFrame(list(events.values()), columns=['usgs_id', 'name', 'year'],)
    events.set_index('usgs_id', inplace=True)

    if year is not None:
        if isinstance(year, Iterable) and not isinstance(year, str):
            events = events[events['year'].isin(year)]
        else:
            events = events[events['year'] == int(year)]

    return events


@lru_cache(maxsize=None)
def usgs_highwatermark_storms(year: int = None) -> pandas.DataFrame:
    """
    this function collects USGS high water mark data for storm events and cross-correlates it with NHC storm data
    this is useful if you want to retrieve USGS data for a specific NHC storm code

    :return: table of USGS flood events with NHC storm names

    >>> usgs_highwatermark_storms()
             year                         usgs_name  nhc_name  nhc_code
    usgs_id
    7        2013                FEMA 2013 exercise      None      None
    8        2013                             Wilma      None      None
    18       2012                    Isaac Aug 2012     ISAAC  al092012
    19       2005                              Rita      None      None
    23       2011                             Irene     IRENE  al092011
    ...       ...                               ...       ...       ...
    303      2020  2020 TS Marco - Hurricane  Laura     MARCO  al142020
    304      2020              2020 Hurricane Sally     SALLY  al192020
    305      2020              2020 Hurricane Delta     DELTA  al262020
    310      2021       2021 Tropical Cyclone Henri     HENRI  al082021
    312      2021         2021 Tropical Cyclone Ida       IDA  al092021
    [24 rows x 3 columns]
    """

    events = usgs_highwatermark_events(event_type=EventType.HURRICANE, year=year)

    events.rename(columns={'name': 'usgs_name'}, inplace=True)
    events['nhc_name'] = None
    events['nhc_code'] = None

    storms = nhc_storms(tuple(pandas.unique(events['year'])))

    storm_names = pandas.unique(storms['name'])
    storm_names.sort()
    for storm_name in storm_names:
        event_storms = events[
            events['usgs_name'].str.contains(storm_name, flags=re.IGNORECASE,)
        ]
        for event_id, event in event_storms.iterrows():
            storms_matching = storms[
                (storms['name'] == storm_name) & (storms['year'] == event['year'])
            ]

            for nhc_code, storm in storms_matching.iterrows():
                events.at[event_id, 'nhc_name'] = storm['name']
                events.at[event_id, 'nhc_code'] = storm.name

    return events[['year', 'usgs_name', 'nhc_name', 'nhc_code']]
