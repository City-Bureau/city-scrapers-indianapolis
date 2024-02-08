import json

import pytz
from city_scrapers_core.constants import (
    BOARD,
    CITY_COUNCIL,
    COMMISSION,
    COMMITTEE,
    NOT_CLASSIFIED,
)
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil import parser
from scrapy.selector import Selector


class IndCityCountySpider(CityScrapersSpider):
    name = "ind_city_county"
    agency = "Indianapolis City-County Council"
    timezone = "America/Detroit"
    start_urls = [
        "https://calendar.indy.gov/handlers/query.ashx?get=eventlist&page=0&pageSize=-1&total=-1&view=list.xslt"  # noqa: E501
    ]

    def parse(self, response):
        """
        Parse the HTML content from a JSONP response. This agency includes
        many events that are not meetings, so we avoid parsing any meeting
        with an unknown classification.
        """
        json_response = self.parse_jsonp(response.text)
        html_content = json_response["html"]
        sel = Selector(text=html_content)
        for item in sel.css("article.list-event"):
            title = self._parse_title(item)
            all_day, start, end = self._parse_datetimes(item)
            classification = self._parse_classification(title)
            if classification == NOT_CLASSIFIED:
                continue
            meeting = Meeting(
                title=title,
                description=self._parse_description(item),
                classification=classification,
                start=start,
                end=end,
                all_day=all_day,
                time_notes="",
                location=self._parse_location(item),
                links=self._parse_links(item),
                source=response.url,
            )
            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)
            yield meeting

    def parse_jsonp(self, jsonp_str):
        """Decode a JSONP string and returns a Dict."""
        start = jsonp_str.find("(") + 1
        end = jsonp_str.rfind(")")
        json_str = jsonp_str[start:end]
        return json.loads(json_str)

    def _parse_title(self, item):
        title = item.css('h3[itemprop="name"] a::text').get()
        return title.strip() if title else ""

    def _parse_description(self, item):
        description = item.css('p[itemprop="description"]::text').get()
        return description.strip() if description else ""

    def _parse_classification(self, title):
        """Generates classification from title."""
        clean_title = title.lower()
        if "committee" in clean_title:
            return COMMITTEE
        elif "council" in clean_title:
            return CITY_COUNCIL
        elif "commission" in clean_title:
            return COMMISSION
        elif "board" in clean_title:
            return BOARD
        return NOT_CLASSIFIED

    def _parse_datetimes(self, item):
        """
        Parse the start and end datetimes from the HTML. Values are
        located in time tags in "datetime" attrib. The presence of
        "startDate" and "endDate" in the same "itemprop" attrib
        indicate that the event is all day.

        Returns a tuple of three values:
        - all_day: a boolean indicating whether the event is all day
        - start: the start datetime of the event
        - end: the end datetime of the event or None
        """
        all_day = bool(
            item.css('time[itemprop="startDate endDate"]::attr(datetime)').get()
        )
        start_datetime_str = item.css(
            'time[itemprop*="startDate"]::attr(datetime)'
        ).get()

        # all day – only parse start
        # only a date string should be present as the attribute value string
        # so we don't need to convert timezones.
        if all_day:
            event_datetime = parser.parse(start_datetime_str)
            return all_day, event_datetime, event_datetime

        # not all day – parse start and end
        # A datetime string should be present and includes tz info that must
        # be converted. An end datetime is not guaranteed to be present.
        end_datetime_str = item.css('time[itemprop*="endDate"]::attr(datetime)').get()
        end_datetime = (
            self._parse_datetime(end_datetime_str) if end_datetime_str else None
        )
        start_datetime = self._parse_datetime(start_datetime_str)
        return all_day, start_datetime, end_datetime

    def _parse_datetime(self, datetime_str):
        """Convert the datetime string to the local timezone and
        return a naive datetime object."""
        start_datetime = parser.parse(datetime_str)
        desired_tz = pytz.timezone(self.timezone)
        start_datetime_aware = start_datetime.astimezone(desired_tz)
        return start_datetime_aware.replace(tzinfo=None)

    def _parse_location(self, item):
        """
        Parse the location from the HTML. Address details
        are generally contained in a single span tag, or
        contained in multiple span tags.
        """
        # handle compact location
        compact_location = (
            item.css('span[itemprop="name address"]::text').get(default="").strip()
        )
        if compact_location:
            return {"name": "", "address": compact_location}

        # handle detailed location
        location_name = item.css('span[itemprop="name"]::text').get(default="").strip()
        street_address = item.css('span[itemprop="streetAddress"]::text').get(
            default=""
        )
        additional_info = (
            item.xpath("normalize-space(following-sibling::text()[1])")
            .get(default="")
            .strip()
        )
        locality = item.css('span[itemprop="addressLocality"]::text').get(default="")
        region = item.css('span[itemprop="addressRegion"]::text').get(default="")
        postal_code = item.css('span[itemprop="postalCode"]::text').get(default="")
        address_components = [
            street_address,
            additional_info,
            locality,
            region,
            postal_code,
        ]
        address = ", ".join(filter(None, address_components))

        if not location_name and not address:
            return {"name": "TBD", "address": ""}

        return {"name": location_name, "address": address}

    def _parse_links(self, item):
        event_link = item.css("section.list-event-link a::attr(href)").get()
        return [{"href": event_link, "title": "Event Details"}] if event_link else []
