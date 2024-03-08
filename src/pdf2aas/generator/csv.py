import csv
import io
import logging

from .core import Generator

logger = logging.getLogger(__name__)


class CSV(Generator):
    def generate(self, properties: list) -> str:
        csv_str = io.StringIO()
        writer = csv.DictWriter(
            csv_str,
            fieldnames=["name", "property", "value", "unit", "id", "reference"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in properties:
            try:
                writer.writerow(row)
            except:
                logger.warning(
                    f"Couldn't write csv row for property {row['id']}: {row['name']}"
                )
                continue
        return csv_str.getvalue()
