from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndIndygoFinanceSpider(CityScrapersSpider):
    name = "ind_indygo_finance"
    agency = "Indianapolis Indygo Finance Committee"
    timezone = "America/Detroit"
    start_urls = ["https://www.indygo.net/about-indygo/board-of-directors/"]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        meeting_section = response.css(".content-section:nth-child(6)")
        section_title = meeting_section.css("h2::text").get()
        meeting_year = section_title.split(" ")[0]
        meeting_time = (
            (response.css(".content-section:nth-child(6) p strong::text").get())
            .split(":", 1)[1]
            .strip()
        )

        for date_item in meeting_section.css("ul li"):
            meeting = Meeting(
                title="IndyGo Finance Committee",
                description=self._parse_description(date_item),
                classification=BOARD,
                start=self._parse_start(date_item, meeting_year, meeting_time),
                end=self._parse_end(date_item),
                all_day=self._parse_all_day(date_item),
                time_notes=self._parse_time_notes(date_item),
                location=self._parse_location(date_item),
                links=self._parse_links(date_item),
                source=self._parse_source(response),
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_title(self, date_item):
        title = "IndyGo Finance Committee"
        return title

    def _parse_description(self, date_item):
        """Parse or generate meeting description."""

        description = ""
        return description

    def _parse_classification(self, date_item):
        """Parse or generate classification from allowed options."""
        return BOARD

    def _parse_start(self, date_item, meeting_year, meeting_time):
        """Parse start datetime as a naive datetime object."""
        meeting_date = (date_item.css("::text").get()).split("-")[0]
        return parser().parse(meeting_date + " " + meeting_year + " " + meeting_time)

    def _parse_end(self, date_item):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        return None

    def _parse_time_notes(self, date_item):
        """Parse any additional notes on the timing of the meeting"""
        return ""  # noqa

    def _parse_all_day(self, date_item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, date_item):
        """Parse or generate location."""
        return {
            "address": "1501 W. Washington St. Indianapolis, IN 46222",
            "name": "Administrative Office - Board Room",
        }

    def _parse_links(self, date_item):
        """Parse or generate links."""
        return [
            {
                "href": "https://www.indygo.net/about-indygo/board-of-directors/",
                "title": "Meeting Page",
            },
            {
                "href": "https://public.onboardmeetings.com/Group/HrdLpC4rmFdYrgplGJZm82TtkS14OCvw7QLcFFPpPrIA/PBtWHdxtJt6XgVphYPHNTSsJFC992FZbLhKOoPeFrjsA",  # noqa
                "title": "Past Finance Committee packets",
            },
        ]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
