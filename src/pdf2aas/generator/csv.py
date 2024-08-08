import csv
import io
import logging

from .core import Generator

logger = logging.getLogger(__name__)

class CSV(Generator):
    header = ["name", "property", "value", "unit", "id", "reference"]

    def dumps(self) -> str:
        csv_str = io.StringIO()
        writer = csv.DictWriter(
            csv_str,
            fieldnames=self.header,
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
            delimiter=';',
            lineterminator='\n'
        )
        writer.writeheader()
        for row in self.properties:
            try:
                writer.writerow(row)
            except AttributeError:
                logger.warning(f"Couldn't write csv row for: {row}")
                continue
        return csv_str.getvalue()
