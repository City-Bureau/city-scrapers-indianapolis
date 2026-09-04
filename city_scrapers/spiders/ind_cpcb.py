import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import scrapy
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parse
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
    query = """query ($slug: String) {
  activity(where: {slug: $slug}) {
    title
    description { markdown }
    location { address1 address2 address3 city state zip }
    agencies { location { address1 address2 address3 city state zip } }
    accordions { title items { title description { html } } }
  }
}"""
    date_re = re.compile(r"([A-Z][a-z]+ \d{1,2}), \d{4}")

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
        )

    def parse(self, response):
        """Yield a Meeting for every date listed in a "Board Materials" accordion."""
        activity = response.json()["data"]["activity"]
        title = self._parse_title(activity)
        location = self._parse_location(activity)
        time_notes = self._parse_time_notes(activity)

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
                    start=self._parse_start(match.group(1), year),
                    end=None,
                    all_day=False,
                    time_notes=time_notes,
                    location=location,
                    links=self._parse_links(docs),
                    source=self.source_url,
                )
                # some months read "No Meeting" in place of documents
                notes = " ".join(docs.xpath(".//text()").getall())
                meeting["status"] = self._get_status(
                    meeting, text="cancelled" if "no meeting" in notes.lower() else ""
                )
                meeting["id"] = self._get_id(meeting)
                yield meeting

    def _parse_title(self, activity):
        return " ".join(activity["title"].split())

    def _parse_start(self, month_day, year):
        """The listed date at the 6 p.m. start named in the description."""
        return parse(f"{month_day} {year}").replace(hour=18)

    def _parse_time_notes(self, activity):
        """The sentence in the description that states the meeting frequency."""
        return next(
            (
                ln.strip()
                for ln in activity["description"]["markdown"].splitlines()
                if "6:00" in ln
            ),
            "",
        )

    def _parse_location(self, activity):
        """The activity has no location of its own; use the parent agency's."""
        loc = activity["location"] or activity["agencies"][0]["location"]
        street = ", ".join(
            p.strip() for p in (loc["address2"], loc["address3"]) if p and p.strip()
        )
        region = " ".join(
            p.strip() for p in (loc["state"], loc["zip"]) if p and p.strip()
        )
        return {
            "name": (loc["address1"] or "").strip(),
            "address": ", ".join(
                p for p in (street, (loc["city"] or "").strip(), region) if p
            ),
        }

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
