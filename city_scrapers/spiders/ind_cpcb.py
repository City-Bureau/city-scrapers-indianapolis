import json
import re
from datetime import time
from io import BytesIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import scrapy
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parse as dateutil_parser
from pypdf import PdfReader
from scrapy.selector import Selector


class IndCpcbSpider(CityScrapersSpider):
    name = "ind_cpcb"
    agency = "Citizens' Police Complaint Board"
    timezone = "America/Indiana/Indianapolis"
    custom_settings = {"ROBOTSTXT_OBEY": False}

    source_url = "https://www.indy.gov/activity/citizens-police-complaint-board"
    api_url = (
        "https://api-us-east-1-indy.graphcms.com/v2/ckp3xrh1i657g01xp53az2mv4/master"
    )
    query = """
        query ($slug: String) {
            activity(where: {slug: $slug}) {
                title
                description { markdown }
                accordions { title items { title description { html } } }
            }
        }
    """
    date_re = re.compile(r"([A-Z][a-z]+ \d{1,2}), \d{4}")
    time_re = re.compile(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", re.IGNORECASE)

    # bullet glyphs seen in the notice PDFs; "o" marks a nested bullet
    bullet_re = re.compile(r"^\s*(?:[\u2022\uf0b7\u25aa]|o(?=\s))\s*(.+?)\s*$")
    date_item_re = re.compile(
        r"^on\b|\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|"
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d",
        re.IGNORECASE,
    )
    online_re = re.compile(r"webex|virtual|video conference", re.IGNORECASE)
    location_unknown = {"name": "TBD", "address": ""}
    location_online = {"name": "Online (Webex)", "address": ""}

    time_note_suffix = "Please check the meeting notice attachment for meeting location and start time details."  # noqa

    def start_requests(self):
        yield scrapy.Request(
            self.api_url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "query": self.query,
                    "variables": {"slug": "citizens-police-complaint-board"},
                }
            ),
            callback=self.parse,
        )

    def parse(self, response):
        """Yield a Meeting for every date listed in a "Board Materials" accordion."""
        activity = response.json()["data"]["activity"]
        title = self._parse_title(activity)
        time_notes = self._parse_time_notes(activity)
        meeting_time = self._parse_meeting_time(activity)

        items = [
            item for accordion in activity["accordions"] for item in accordion["items"]
        ]
        for item in items:
            if "Board Materials" not in item["title"]:
                continue
            # the accordion is grouped by year; trust its heading over a
            # mistyped year in a date line
            year_match = re.search(r"\d{4}", item["title"])
            if not year_match:
                self.logger.warning(
                    "Could not find a year in accordion title %r; skipping items"
                    " under it",
                    item["title"],
                )
                continue
            year = year_match.group()
            body = Selector(text=item["description"]["html"])
            for header in body.xpath("//p"):
                match = self.date_re.search(
                    " ".join(header.xpath(".//text()").getall())
                )
                if not match:
                    continue
                docs = header.xpath("following-sibling::*[1][self::ul]")

                meeting = Meeting(
                    title=title,
                    description="",
                    classification=BOARD,
                    start=self._parse_start(match.group(1), year, meeting_time),
                    end=None,
                    all_day=False,
                    time_notes=time_notes,
                    location=self.location_unknown,
                    links=self._parse_links(docs),
                    source=self.source_url,
                )
                # some months read "No Meeting" in place of documents
                notes = " ".join(docs.xpath(".//text()").getall())
                meeting["status"] = self._get_status(
                    meeting, text="cancelled" if "no meeting" in notes.lower() else ""
                )
                meeting["id"] = self._get_id(meeting)

                # The indy.gov API only has the agency's office address; the
                # real location is written in each meeting's notice document.
                notice = self._parse_notice_link(meeting["links"])
                if notice:
                    yield scrapy.Request(
                        notice,
                        callback=self._parse_notice,
                        errback=self._notice_failed,
                        # one notice can cover two meetings
                        dont_filter=True,
                        cb_kwargs={"meeting": meeting},
                    )
                else:
                    yield meeting

    def _parse_notice_link(self, links):
        return next(
            (link["href"] for link in links if "notice" in link["title"].lower()),
            None,
        )

    def _parse_notice(self, response, meeting):
        """Fill in the meeting's location from its notice PDF."""
        try:
            text = self._pdf_text(response.body)
        except Exception:
            self.logger.warning("Could not read notice %s", response.url)
            text = ""
        location = self._parse_notice_location(text)
        if location is None:
            self.logger.warning("No location found in notice %s", response.url)
        else:
            meeting["location"] = location
        yield meeting

    def _notice_failed(self, failure):
        self.logger.warning("Could not fetch notice: %s", failure.value)
        yield failure.request.cb_kwargs["meeting"]

    def _pdf_text(self, body):
        return "\n".join(
            page.extract_text() or "" for page in PdfReader(BytesIO(body)).pages[:1]
        )

    def _parse_notice_location(self, text):
        """Location from a notice's bulleted list, e.g.

            - Monday, May 11, 2026
            - at 6:00 p.m.
            - at the City-County Building
            - 200 E. Washington Street, Indianapolis, IN 46204
            - in Room T-310

        Place and address may share a bullet, older notices omit the room, and
        2021 notices are virtual (Webex). Returns None if nothing is found."""
        start = re.search(r"will hold", text)
        end = re.search(r"For accommodations", text)
        body = text[start.end() : end.start() if end else None] if start else text
        items = []
        for line in body.splitlines():
            match = self.bullet_re.match(line)
            if match:
                items.append(match.group(1))
        items = [
            i
            for i in items
            if not self.date_item_re.search(i)
            and not self.time_re.search(i)
            and not re.match(r"at \d", i, re.IGNORECASE)
        ]
        if items:
            place, *rest = items
            rest = [re.sub(r"^located at\s+", "", i, flags=re.I) for i in rest]
            # "at Place, 123 Main St" shares a bullet
            shared = re.match(r"(.+?),\s*(\d.*)$", place)
            if shared:
                place, rest = shared.group(1), [shared.group(2), *rest]
            address = next((i for i in rest if i[0].isdigit()), "")
            rooms = [i for i in rest if i != address]
            name = self._clean_name(place)
            room = ", ".join(
                self._clean_name(r.split(" \u2013 ")[0].split(" - ")[0]) for r in rooms
            )
            if name and address:
                return {
                    "name": f"{name}, {room}" if room else name,
                    "address": self._clean_address(address),
                }
        if self.online_re.search(text):
            return dict(self.location_online)
        return None

    def _clean_name(self, value):
        value = re.sub(
            r"^(?:(?:at|in|located at)\s+)+(?:the\s+)?", "", value.strip(), flags=re.I
        )
        return value.strip(" ,.")

    def _clean_address(self, value):
        """Street address with the city and state the notices sometimes omit."""
        value = re.sub(r"(\d) (st|nd|rd|th)\b", r"\1\2", value.strip(" ,."))
        if re.search(r"\bIN\b", value):
            return value
        zip_match = re.search(r",?\s*(\d{5})$", value)
        zip_code = zip_match.group(1) if zip_match else ""
        if zip_match:
            value = value[: zip_match.start()]
        return f"{value}, Indianapolis, IN {zip_code}".strip()

    def _parse_title(self, activity):
        return " ".join(activity["title"].split())

    def _parse_start(self, month_day, year, meeting_time):
        """The listed date combined with the meeting's usual start time."""
        return dateutil_parser(f"{month_day} {year} {meeting_time}")

    def _parse_time_notes(self, activity):
        """The sentence in the description that states the meeting time, plus
        a standing reminder to check the notice since that sentence can go
        stale."""
        line = next(
            (
                ln.strip()
                for ln in activity["description"]["markdown"].splitlines()
                if self.time_re.search(ln)
            ),
            "",
        )
        return f"{line} {self.time_note_suffix}" if line else self.time_note_suffix

    def _parse_meeting_time(self, activity):
        """The meeting's usual start time, parsed out of the description;
        defaults to midnight if the description doesn't state one."""
        match = self.time_re.search(activity["description"]["markdown"])
        if not match:
            self.logger.warning(
                "Could not find a meeting start time in the description;"
                " defaulting to 00:00"
            )
            return time(0, 0)
        return match.group(0)

    def _parse_links(self, docs):
        """Document links under one date. Nested <a>s repeat a link with
        tracking params, sometimes with a blank label."""
        titles = {}
        for a in docs.xpath(".//a[@href]"):
            url = urlsplit(a.xpath("@href").get())
            qs = urlencode(
                [kv for kv in parse_qsl(url.query) if not kv[0].startswith("_")]
            )
            href = urlunsplit((*url[:3], qs, ""))
            text = " ".join(" ".join(a.xpath(".//text()").getall()).split())
            titles[href] = titles.get(href) or text
        return [{"href": h, "title": t} for h, t in titles.items()]
